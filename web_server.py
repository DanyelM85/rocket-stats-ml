import eel
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import threading
import socket
import json
import time

eel.init('web')

_capture_thread = None
_validate_fn = None

_current_port = 49123
_current_send_rate = 30.0
_current_path = ""

# Buffer en memoria para telemetría
_telemetry_buffer = []
_last_disk_flush = 0.0
_last_state_write = 0.0

def save_telemetry_payload(payload):
    global _last_disk_flush, _last_state_write, _telemetry_buffer
    try:
        now = time.time()
        _telemetry_buffer.append(json.dumps(payload) + "\n")
        
        # Reducción de Escritura en Disco 150x: Guardamos logs acumulados cada 5 segundos o 150 paquetes
        if now - _last_disk_flush > 5.0 or len(_telemetry_buffer) >= 150:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            log_file = data_dir / "telemetry_log.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.writelines(_telemetry_buffer)
            _telemetry_buffer.clear()
            _last_disk_flush = now
            
        # Reducción de Escritura en Disco 30x: Guardamos el archivo latest_state.json solo una vez por segundo
        if now - _last_state_write > 1.0:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            latest_file = data_dir / "latest_state.json"
            with open(latest_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            _last_state_write = now
    except Exception as e:
        print(f"Error al guardar la telemetría en disco: {e}")

class RLConnectionThread(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = False
        self.socket = None
        self.daemon = True

    def run(self):
        self.running = True
        while self.running:
            try:
                eel.on_status_change("connecting", f"Intentando conectar a 127.0.0.1:{self.port}...")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(3.0)
                self.socket.connect(("127.0.0.1", self.port))
                self.socket.settimeout(None)
                eel.on_status_change("connected", f"¡Conectado al socket de Rocket League en el puerto {self.port}!")
                buffer = ""
                while self.running:
                    data = self.socket.recv(8192)
                    if not data:
                        print("[SOCKET] Conexión cerrada por el host (Rocket League).")
                        eel.on_log_event("⚠️ Conexión cerrada por Rocket League.")
                        break
                    
                    decoded = data.decode('utf-8', errors='ignore')
                    buffer += decoded
                    
                    # Decodificar objetos JSON consecutivos directamente del stream usando raw_decode
                    decoder = json.JSONDecoder()
                    buffer = buffer.strip()
                    while buffer:
                        try:
                            payload, idx = decoder.raw_decode(buffer)
                            eel.on_telemetry_data(payload)
                            save_telemetry_payload(payload)
                            buffer = buffer[idx:].strip()
                        except json.JSONDecodeError:
                            # Si el JSON está incompleto, rompemos para esperar más datos en el socket
                            break
            except Exception as e:
                if self.running:
                    eel.on_status_change("disconnected", f"Sin conexión: {str(e)}. Reintentando en 3 segundos...")
                    time.sleep(3)
            finally:
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

@eel.expose
def browse_directory():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    directory = filedialog.askdirectory(title="Selecciona la carpeta raíz de Rocket League")
    root.destroy()
    return str(Path(directory).as_posix()) if directory else ""

@eel.expose
def validate_path(path_str):
    if _validate_fn:
        is_valid, error = _validate_fn(path_str)
        return {"valid": is_valid, "error": error}
    return {"valid": False, "error": "Función de validación no definida"}

@eel.expose
def get_current_state():
    global _current_path, _current_port, _current_send_rate
    from config_manager import find_rl_installation, RELATIVE_INI_PATH, read_ini_values
    detected_path = _current_path or find_rl_installation()
    if detected_path:
        detected_path = str(detected_path)
    ini_path = Path(detected_path) / RELATIVE_INI_PATH if detected_path else None
    port = _current_port
    send_rate = _current_send_rate
    has_existing = False
    if ini_path and ini_path.exists():
        port, send_rate = read_ini_values(ini_path)
        has_existing = True
    return {
        "path": detected_path or "",
        "port": port,
        "send_rate": send_rate,
        "has_existing": has_existing,
        "capture_active": _capture_thread is not None and _capture_thread.is_alive()
    }

@eel.expose
def save_and_apply_settings(path_str, port, send_rate):
    global _current_path, _current_port, _current_send_rate
    from config_manager import setup_stats_api, save_installation_path
    _current_path = path_str.strip('"\' ')
    _current_port = int(port)
    _current_send_rate = float(send_rate)
    is_valid, err = _validate_fn(_current_path)
    if not is_valid:
        return {"success": False, "error": f"Ruta inválida: {err}"}
    save_installation_path(_current_path)
    import config_manager
    from pathlib import Path
    old_get_valid_ini_path = config_manager.get_valid_ini_path
    config_manager.get_valid_ini_path = lambda: Path(_current_path) / config_manager.RELATIVE_INI_PATH
    try:
        success = setup_stats_api(send_rate=_current_send_rate, port=_current_port)
    finally:
        config_manager.get_valid_ini_path = old_get_valid_ini_path
    if not success:
        return {"success": False, "error": "Error al guardar el archivo de configuración (.ini). Verifica los permisos."}
    global _capture_thread
    if _capture_thread and _capture_thread.is_alive():
        _capture_thread.stop()
        _capture_thread = RLConnectionThread(_current_port)
        _capture_thread.start()
    return {"success": True}

@eel.expose
def toggle_live_capture(active):
    global _capture_thread, _current_port
    if active:
        if _capture_thread and _capture_thread.is_alive():
            _capture_thread.stop()
        _capture_thread = RLConnectionThread(_current_port)
        _capture_thread.start()
        return {"active": True}
    else:
        if _capture_thread:
            _capture_thread.stop()
            _capture_thread = None
        eel.on_status_change("disconnected", "Captura de datos en vivo detenida.")
        return {"active": False}

def run_config_ui(validate_fn, submit_fn):
    global _validate_fn
    _validate_fn = validate_fn
    try:
        eel.start('index.html', mode='chrome', size=(1000, 780), block=True)
    except (SystemExit, MemoryError):
        pass
    finally:
        global _capture_thread
        if _capture_thread:
            _capture_thread.stop()
