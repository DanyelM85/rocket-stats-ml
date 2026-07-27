import eel
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import threading
import socket
import json
import time

# Inicializar Eel apuntando a la carpeta donde está el HTML
eel.init('web')

# Variables globales para control de hilos
_capture_thread = None
_simulation_thread = None
_validate_fn = None

# Variables de estado actual
_current_port = 49123
_current_send_rate = 30.0
_current_path = ""

# Funciones de utilidad para hilos de fondo
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
                self.socket.settimeout(None) # Bloqueante para recibir datos
                eel.on_status_change("connected", f"¡Conectado al socket de Rocket League en el puerto {self.port}!")
                
                buffer = ""
                while self.running:
                    data = self.socket.recv(8192)
                    if not data:
                        break # Conexión cerrada por el host
                    
                    buffer += data.decode('utf-8', errors='ignore')
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                payload = json.loads(line)
                                eel.on_telemetry_data(payload)
                            except Exception:
                                # En caso de que sea un fragmento parcial no JSON
                                pass
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

class RLSimulationThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = False
        self.daemon = True

    def run(self):
        self.running = True
        blue_score = 0
        orange_score = 0
        match_time = 300 # 5 mins
        
        players = [
            {"name": "Danny_Rocket", "team": 0, "boost": 100, "score": 150, "goals": 1, "saves": 0, "shots": 2, "speed": 42},
            {"name": "Octane_King", "team": 0, "boost": 45, "score": 50, "goals": 0, "saves": 1, "shots": 0, "speed": 28},
            {"name": "Fennec_Pro", "team": 1, "boost": 85, "score": 120, "goals": 1, "saves": 0, "shots": 1, "speed": 35},
            {"name": "Dominus_Lord", "team": 1, "boost": 15, "score": 30, "goals": 0, "saves": 0, "shots": 1, "speed": 12},
        ]
        
        import random
        eel.on_status_change("simulating", "Modo Simulación Activo: Generando telemetría realista...")
        
        while self.running:
            match_time -= 1
            if match_time <= 0:
                match_time = 300
                blue_score = 0
                orange_score = 0
                for p in players:
                    p["score"] = 0
                    p["goals"] = 0
                    p["saves"] = 0
                    p["shots"] = 0
            
            for p in players:
                # Modificaciones aleatorias de boost y velocidad
                p["boost"] = max(0, min(100, p["boost"] + random.randint(-20, 25)))
                p["speed"] = max(0, min(85, p["speed"] + random.randint(-15, 20)))
                
                # Simular jugadas aleatorias
                chance = random.random()
                if chance < 0.04:
                    p["shots"] += 1
                    p["score"] += 10
                    eel.on_log_event(f"🎯 Tiro a puerta de {p['name']}")
                elif chance < 0.02:
                    p["saves"] += 1
                    p["score"] += 50
                    eel.on_log_event(f"🛡️ ¡Salvada salvaje de {p['name']}!")
                elif chance < 0.01:
                    p["goals"] += 1
                    p["score"] += 100
                    if p["team"] == 0:
                        blue_score += 1
                        eel.on_log_event(f"⚽ GOL del Equipo Azul anotado por {p['name']} (Azul {blue_score} - {orange_score} Naranja)")
                    else:
                        orange_score += 1
                        eel.on_log_event(f"⚽ GOL del Equipo Naranja anotado por {p['name']} (Azul {blue_score} - {orange_score} Naranja)")

            ball_speed = random.randint(15, 130)
            
            telemetry_data = {
                "event": "UpdateState",
                "data": {
                    "game": {
                        "time": match_time,
                        "blue_score": blue_score,
                        "orange_score": orange_score,
                        "ball_speed": ball_speed
                    },
                    "players": players
                }
            }
            eel.on_telemetry_data(telemetry_data)
            time.sleep(1)

    def stop(self):
        self.running = False


# Exponer funciones a JavaScript
@eel.expose
def browse_directory():
    """Abre el explorador de archivos nativo de Windows."""
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
    """Devuelve la configuración y el estado actual de los hilos."""
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
        "capture_active": _capture_thread is not None and _capture_thread.is_alive(),
        "simulation_active": _simulation_thread is not None and _simulation_thread.is_alive()
    }

@eel.expose
def save_and_apply_settings(path_str, port, send_rate):
    """Guarda los ajustes usando config_manager e inicia/reinicia la captura si es necesario."""
    global _current_path, _current_port, _current_send_rate
    from config_manager import setup_stats_api, save_installation_path
    
    _current_path = path_str.strip('"\' ')
    _current_port = int(port)
    _current_send_rate = float(send_rate)
    
    # 1. Validar la ruta primero
    is_valid, err = _validate_fn(_current_path)
    if not is_valid:
        return {"success": False, "error": f"Ruta inválida: {err}"}
        
    # 2. Guardar la ruta en app_config.json
    save_installation_path(_current_path)
        
    # 3. Escribir archivo INI a través de config_manager
    # Modificar temporalmente la función get_valid_ini_path para que retorne nuestra ruta elegida
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
        
    # Si la captura de datos en vivo está activa, reiniciamos el hilo de escucha con el nuevo puerto
    global _capture_thread
    if _capture_thread and _capture_thread.is_alive():
        _capture_thread.stop()
        _capture_thread = RLConnectionThread(_current_port)
        _capture_thread.start()
        
    return {"success": True}

@eel.expose
def toggle_live_capture(active):
    """Activa o desactiva la escucha del socket de Rocket League."""
    global _capture_thread, _current_port
    
    if active:
        if _capture_thread and _capture_thread.is_alive():
            _capture_thread.stop()
        
        # Desactivar simulación para evitar colisiones
        global _simulation_thread
        if _simulation_thread and _simulation_thread.is_alive():
            _simulation_thread.stop()
            _simulation_thread = None
            
        _capture_thread = RLConnectionThread(_current_port)
        _capture_thread.start()
        return {"active": True, "simulation_disabled": True}
    else:
        if _capture_thread:
            _capture_thread.stop()
            _capture_thread = None
        eel.on_status_change("disconnected", "Captura de datos en vivo detenida.")
        return {"active": False}

@eel.expose
def toggle_simulation(active):
    """Activa o desactiva la simulación de telemetría."""
    global _simulation_thread
    
    if active:
        if _simulation_thread and _simulation_thread.is_alive():
            _simulation_thread.stop()
            
        # Desactivar captura en vivo para evitar colisiones
        global _capture_thread
        if _capture_thread and _capture_thread.is_alive():
            _capture_thread.stop()
            _capture_thread = None
            
        _simulation_thread = RLSimulationThread()
        _simulation_thread.start()
        return {"active": True, "capture_disabled": True}
    else:
        if _simulation_thread:
            _simulation_thread.stop()
            _simulation_thread = None
        eel.on_status_change("disconnected", "Simulación detenida.")
        return {"active": False}


def run_config_ui(validate_fn, submit_fn):
    """
    Inicia la interfaz de Eel y mantiene el control.
    """
    global _validate_fn
    _validate_fn = validate_fn
    
    try:
        # Lanzar Eel con un tamaño agradable para ver el dashboard completo
        eel.start('index.html', mode='chrome', size=(1000, 780), block=True)
    except (SystemExit, MemoryError):
        pass
    finally:
        # Limpiar hilos al cerrar la ventana
        global _capture_thread, _simulation_thread
        if _capture_thread:
            _capture_thread.stop()
        if _simulation_thread:
            _simulation_thread.stop()

