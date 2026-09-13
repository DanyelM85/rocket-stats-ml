import eel
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import threading
import socket
import json
import time
import datetime
import ctypes
from ctypes import wintypes

eel.init('web')

MATCHES_DIR = Path("data/matches")

def _build_match_summary(last_update_data: dict, match_ended_data: dict) -> dict:
    """Arma un resumen liviano de la partida a partir del último UpdateState
    visto (que ya trae los contadores acumulados del propio motor de RL:
    Score/Goals/Assists/Saves/etc.) y del evento MatchEnded que confirma
    quién ganó (incluyendo si la partida se resolvió en tiempo extra)."""
    last_update_data = last_update_data or {}
    game = last_update_data.get("Game") or last_update_data.get("game") or {}
    players = last_update_data.get("Players") or last_update_data.get("players") or []
    teams = game.get("Teams") or game.get("teams") or []
    return {
        "match_guid": match_ended_data.get("MatchGuid", ""),
        "ended_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "arena": game.get("Arena", ""),
        "playlist_id": game.get("PlaylistId"),
        "overtime": bool(game.get("bOvertime", False)),
        "winner_team_num": match_ended_data.get("WinnerTeamNum"),
        "teams": [
            {
                "team_num": t.get("TeamNum", t.get("team")),
                "name": t.get("Name", t.get("name")),
                "score": t.get("Score", t.get("score")),
                "color_primary": t.get("ColorPrimary"),
                "color_secondary": t.get("ColorSecondary")
            } for t in teams
        ],
        "players": [
            {
                "name": p.get("Name", p.get("name")),
                "team_num": p.get("TeamNum", p.get("team")),
                "score": p.get("Score", p.get("score")),
                "goals": p.get("Goals", p.get("goals")),
                "assists": p.get("Assists", p.get("assists")),
                "saves": p.get("Saves", p.get("saves")),
                "shots": p.get("Shots", p.get("shots")),
                "touches": p.get("Touches", p.get("touches")),
                "demos": p.get("Demos", p.get("demos")),
                "boost_at_end": p.get("Boost", p.get("boost"))
            } for p in players
        ]
    }

def _save_match_summary(summary: dict) -> str:
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    guid_part = (summary.get("match_guid") or "")[:8]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"match_{timestamp}{'_' + guid_part if guid_part else ''}.json"
    filepath = MATCHES_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return str(filepath)

def _fire(js_call):
    # eel solo libera la entrada en _call_return_values cuando alguien consume
    # el retorno de la llamada; sin esto, cada eel.on_xxx(...) sin ()() deja una
    # entrada huérfana para siempre y la RAM crece sin límite en sesiones largas.
    js_call(lambda *_: None)

_capture_thread = None
_validate_fn = None

_current_port = 49124
_current_send_rate = 30.0
_current_path = ""

# --- ESTRUCTURAS DE LLAMADA DIRECTA A XINPUT EN WINDOWS (SIN DEPENDENCIAS) ---
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]

_xinput_dll = None
for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
    try:
        _xinput_dll = ctypes.windll.LoadLibrary(dll_name)
        break
    except Exception:
        continue

def get_active_gamepad_state():
    """Lee de forma directa el puerto de control XInput de Windows."""
    if not _xinput_dll:
        return {}
    state = XINPUT_STATE()
    # Consultamos el control 0 (Jugador Principal)
    res = _xinput_dll.XInputGetState(0, ctypes.byref(state))
    if res == 0:  # ERROR_SUCCESS
        gp = state.Gamepad
        rt = int((gp.bRightTrigger / 255.0) * 100)
        lt = int((gp.bLeftTrigger / 255.0) * 100)
        
        lx = gp.sThumbLX
        if abs(lx) < 3000:
            steer = 0
        else:
            steer = int((lx / 32767.0) * 100)
            
        return {
            "Throttle": rt - lt,  # Rango [-100, 100]
            "Steer": steer,        # Rango [-100, 100]
            "Handbrake": bool(gp.wButtons & 0x4000),
            "BoostButton": bool(gp.wButtons & 0x2000),
            "JumpButton": bool(gp.wButtons & 0x1000)
        }
    return {}



class RLConnectionThread(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = False
        self.socket = None
        self.daemon = True
        self.last_update_data = None

    def run(self):
        self.running = True
        while self.running:
            try:
                _fire(eel.on_status_change("connecting", f"Intentando conectar a 127.0.0.1:{self.port}..."))
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(3.0)
                self.socket.connect(("127.0.0.1", self.port))
                self.socket.settimeout(None)
                _fire(eel.on_status_change("connected", f"¡Conectado al socket de Rocket League en el puerto {self.port}!"))
                buffer = ""
                while self.running:
                    data = self.socket.recv(8192)
                    if not data:
                        if self.running:
                            _fire(eel.on_status_change("disconnected", "Rocket League cerró la conexión. Reintentando en 3 segundos..."))
                            time.sleep(3)
                        break
                    
                    decoded = data.decode('utf-8', errors='ignore')
                    buffer += decoded
                    
                    decoder = json.JSONDecoder()
                    buffer = buffer.strip()
                    while buffer:
                        try:
                            payload, idx = decoder.raw_decode(buffer)
                            gp_state = get_active_gamepad_state()
                            if gp_state:
                                data_field = payload.get("Data") or payload.get("data")
                                if isinstance(data_field, dict):
                                    data_field["GamepadInput"] = gp_state
                                elif isinstance(data_field, str):
                                    try:
                                        parsed = json.loads(data_field)
                                        parsed["GamepadInput"] = gp_state
                                        if "Data" in payload:
                                            payload["Data"] = parsed
                                        else:
                                            payload["data"] = parsed
                                    except:
                                        pass

                            event_name = payload.get("Event") or payload.get("event")
                            data_field = payload.get("Data") or payload.get("data")
                            if isinstance(data_field, str):
                                try:
                                    data_field = json.loads(data_field)
                                except:
                                    data_field = None

                            if event_name == "UpdateState" and isinstance(data_field, dict):
                                self.last_update_data = data_field
                            elif event_name == "MatchEnded" and isinstance(data_field, dict):
                                try:
                                    summary = _build_match_summary(self.last_update_data, data_field)
                                    saved_path = _save_match_summary(summary)
                                    print(f"[OK] Resumen de partida guardado en: {saved_path}")
                                    _fire(eel.on_match_saved(summary))
                                except Exception as e:
                                    print(f"[ERROR] No se pudo guardar el resumen de partida: {e}")
                                self.last_update_data = None

                            _fire(eel.on_telemetry_data(payload))
                            buffer = buffer[idx:].strip()
                        except json.JSONDecodeError:
                            break
            except Exception as e:
                if self.running:
                    _fire(eel.on_status_change("disconnected", f"Sin conexión: {str(e)}. Reintentando en 3 segundos..."))
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
        # Sincronizar con el .ini real: si no se hace, "Escuchar Socket Local" se
        # conecta con el puerto por defecto en memoria en vez del que ya está
        # configurado en el juego, y la conexión se cae apenas se abre.
        _current_port = port
        _current_send_rate = send_rate
        if detected_path:
            _current_path = detected_path
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
def get_team_config():
    from config_manager import load_team_config
    return load_team_config()

@eel.expose
def set_team_config(blue_name, orange_name, blue_logo=None, orange_logo=None):
    from config_manager import save_team_config, load_team_config, DEFAULT_TEAM_CONFIG
    current_cfg = load_team_config()
    b_logo = blue_logo if blue_logo is not None and blue_logo != "" else current_cfg.get("blue_logo", "")
    o_logo = orange_logo if orange_logo is not None and orange_logo != "" else current_cfg.get("orange_logo", "")
    cfg = {
        "blue_name": (blue_name or "").strip()[:32] or DEFAULT_TEAM_CONFIG["blue_name"],
        "orange_name": (orange_name or "").strip()[:32] or DEFAULT_TEAM_CONFIG["orange_name"],
        "blue_logo": b_logo,
        "orange_logo": o_logo
    }
    save_team_config(cfg)
    _fire(eel.on_team_config_update(cfg))
    return {"success": True}

@eel.expose
def get_series_config():
    from config_manager import load_series_config
    return load_series_config()

@eel.expose
def set_series_config(phase, series_format, blue_series_score, orange_series_score):
    from config_manager import save_series_config, DEFAULT_SERIES_CONFIG
    cfg = {
        "phase": (phase or "").strip()[:40],
        "format": series_format if series_format in ("bo1", "bo3", "bo5", "bo7") else DEFAULT_SERIES_CONFIG["format"],
        "blue_series_score": max(0, int(blue_series_score or 0)),
        "orange_series_score": max(0, int(orange_series_score or 0))
    }
    save_series_config(cfg)
    _fire(eel.on_series_config_update(cfg))
    return {"success": True, "config": cfg}

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
        _fire(eel.on_status_change("disconnected", "Captura de datos en vivo detenida."))
        return {"active": False}

@eel.expose
def get_saved_matches():
    """Retorna la lista de archivos JSON de partidas guardadas en data/matches."""
    try:
        if not MATCHES_DIR.exists():
            return []
        files = sorted(list(MATCHES_DIR.glob("*.json")), key=lambda f: f.stat().st_mtime, reverse=True)
        result = []
        for f in files[:30]:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                result.append({
                    "filename": f.name,
                    "filepath": str(f.as_posix()),
                    "mtime": datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": data
                })
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"Error al listar partidas JSON: {e}")
        return []

@eel.expose
def get_match_json_content(filename):
    """Lee y retorna el objeto JSON completo de una partida específica."""
    try:
        clean_name = Path(filename).name
        filepath = MATCHES_DIR / clean_name
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error al leer JSON de la partida {filename}: {e}")
    return None

def kill_process_on_port(port: int):
    """Mata cualquier proceso huérfano de Python/Eel que esté ocupando el puerto en Windows.
    PROTECCIÓN: Nunca mata el proceso de Rocket League."""
    import subprocess
    import os
    try:
        current_pid = os.getpid()
        output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True, errors='ignore')
        pids_to_kill = set()
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and 'LISTENING' in line:
                try:
                    pid = int(parts[-1])
                    if pid != current_pid and pid > 0:
                        pids_to_kill.add(pid)
                except ValueError:
                    pass
        for pid in pids_to_kill:
            try:
                task_out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /FO CSV /NH', shell=True, text=True, errors='ignore')
                proc_name = task_out.split(',')[0].replace('"', '').lower()
                if any(rl in proc_name for rl in ["rocketleague", "tagame"]):
                    print(f"[i] Ignorando PID {pid} ({proc_name}) porque es el juego Rocket League.")
                    continue
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    except Exception:
        pass

def _on_window_close(page, sockets):
    print("\n[i] Ventana del navegador cerrada por el usuario. Cerrando main.py...")
    global _capture_thread
    if _capture_thread:
        try:
            _capture_thread.stop()
        except Exception:
            pass
        _capture_thread = None
    import os
    os._exit(0)

def run_config_ui(validate_fn, submit_fn):
    global _validate_fn
    _validate_fn = validate_fn
    kill_process_on_port(8000)
    try:
        eel.start(
            'index.html',
            mode='chrome',
            host='localhost',
            port=8000,
            size=(1080, 800),
            close_callback=_on_window_close,
            block=True
        )
    except (SystemExit, MemoryError, KeyboardInterrupt):
        pass
    finally:
        global _capture_thread
        if _capture_thread:
            try:
                _capture_thread.stop()
            except Exception:
                pass
            _capture_thread = None
        import os
        os._exit(0)
