import json
from pathlib import Path

DEFAULT_PATHS = [
    Path(r"C:\Program Files\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\rocketleague"),
    Path(r"C:\Program Files\Steam\steamapps\common\rocketleague"),
]

RELATIVE_INI_PATH = Path("TAGame/Config/DefaultStatsAPI.ini")
CONFIG_JSON_PATH = Path("app_config.json")

DEFAULT_TEAM_CONFIG = {
    "blue_name": "Azul",
    "orange_name": "Naranja",
    "blue_logo": "",
    "orange_logo": ""
}

def _load_app_config() -> dict:
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_app_config(data: dict):
    with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_saved_path() -> str | None:
    return _load_app_config().get("rl_installation_path")

def save_installation_path(path_str: str):
    try:
        data = _load_app_config()
        data["rl_installation_path"] = path_str
        _save_app_config(data)
    except Exception as e:
        print(f"Error al guardar la ruta de instalación en JSON: {e}")

def load_team_config() -> dict:
    cfg = _load_app_config().get("team_config", {})
    return {**DEFAULT_TEAM_CONFIG, **cfg}

def save_team_config(team_config: dict):
    data = _load_app_config()
    data["team_config"] = team_config
    _save_app_config(data)

DEFAULT_SERIES_CONFIG = {
    "phase": "",
    "format": "bo3",
    "blue_series_score": 0,
    "orange_series_score": 0
}

def load_series_config() -> dict:
    cfg = _load_app_config().get("series_config", {})
    return {**DEFAULT_SERIES_CONFIG, **cfg}

def save_series_config(series_config: dict):
    data = _load_app_config()
    data["series_config"] = series_config
    _save_app_config(data)

def find_rl_installation() -> Path | None:
    saved = load_saved_path()
    if saved and Path(saved).exists():
        return Path(saved)
    for path in DEFAULT_PATHS:
        ini_candidate = path / RELATIVE_INI_PATH
        if ini_candidate.exists() or path.exists():
            save_installation_path(str(path))
            return path
    return None

def validate_rl_path(path_str: str) -> tuple[bool, str]:
    try:
        cleaned_path = path_str.strip('"\' ')
        if not cleaned_path:
            return False, "La ruta no puede estar vacía."
        path = Path(cleaned_path)
        if not path.exists():
            return False, "La ruta especificada no existe en el disco."
        has_tagame = (path / "TAGame").exists()
        has_binaries = (path / "Binaries").exists()
        has_ini_dir = (path / RELATIVE_INI_PATH.parent).exists()
        if has_tagame or has_binaries or has_ini_dir:
            return True, ""
        return False, "La carpeta existe, pero no parece ser la raíz de Rocket League (debe contener 'TAGame' o 'Binaries')."
    except Exception as e:
        return False, f"Ruta inválida o inaccesible: {e}"

def get_valid_ini_path() -> Path:
    base_path = find_rl_installation()
    if base_path:
        return base_path / RELATIVE_INI_PATH
    return Path("")

def read_ini_values(ini_path: Path) -> tuple[int, float]:
    port = 49124
    send_rate = 30.0
    if not ini_path.exists():
        return port, send_rate
    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_exporter_section = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_name = stripped[1:-1].strip()
                if section_name in ["TAGame.MatchStatsExporter_TA", "DefaultStatsAPI"]:
                    in_exporter_section = True
                else:
                    in_exporter_section = False
            if in_exporter_section:
                if stripped.startswith("Port="):
                    try:
                        port = int(stripped.split("=")[1].strip())
                    except:
                        pass
                elif stripped.startswith("PacketSendRate="):
                    try:
                        send_rate = float(stripped.split("=")[1].strip())
                    except:
                        pass
    except Exception as e:
        print(f"Error al leer valores del .ini: {e}")
    return port, send_rate

def _write_values_to_ini(ini_path: Path, send_rate: float, port: int) -> bool:
    default_content = f"""; Archivo de configuración de Rocket League Stats API
[TAGame.MatchStatsExporter_TA]

; Port the client will listen for connections on
Port={port}

; How many times per second the game sends the update state (capped at 120, 0 disables this feature)
PacketSendRate={send_rate}
"""
    if not ini_path.exists():
        try:
            ini_path.parent.mkdir(parents=True, exist_ok=True)
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(default_content)
            print(f" [✓] Archivo creado con éxito en:\n    {ini_path}")
            return True
        except PermissionError:
            print(f"[X] Error de permisos al crear {ini_path}.")
            return False
        except Exception as e:
            print(f"[X] Error al crear .ini: {e}")
            return False
    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        in_exporter_section = False
        port_updated = False
        rate_updated = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_name = stripped[1:-1].strip()
                if section_name == "TAGame.MatchStatsExporter_TA":
                    in_exporter_section = True
                else:
                    in_exporter_section = False
            if in_exporter_section:
                if stripped.startswith("Port="):
                    prefix = line.split("Port=")[0]
                    new_lines.append(f"{prefix}Port={port}\n")
                    port_updated = True
                    continue
                elif stripped.startswith("PacketSendRate="):
                    prefix = line.split("PacketSendRate=")[0]
                    val = int(send_rate) if send_rate.is_integer() else send_rate
                    new_lines.append(f"{prefix}PacketSendRate={val}\n")
                    rate_updated = True
                    continue
            new_lines.append(line)
        if not port_updated:
            new_lines.append(f"Port={port}\n")
        if not rate_updated:
            val = int(send_rate) if send_rate.is_integer() else send_rate
            new_lines.append(f"PacketSendRate={val}\n")
        with open(ini_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f" [✓] Archivo configurado con éxito en:\n    {ini_path}")
        return True
    except PermissionError:
        print(f"[X] Error de permisos al escribir en {ini_path}. Intenta ejecutar el script como Administrador.")
        return False
    except Exception as e:
        print(f"[X] Error inesperado: {e}")
        return False

def setup_stats_api(send_rate: float = 30.0, port: int = 49124) -> bool:
    success = False
    ini_path = get_valid_ini_path()
    if ini_path and ini_path != Path(""):
        success = _write_values_to_ini(ini_path, send_rate, port)
    try:
        docs_paths = [
            Path.home() / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Config" / "TAStatsAPI.ini",
            Path.home() / "OneDrive" / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Config" / "TAStatsAPI.ini"
        ]
        for docs_ini in docs_paths:
            if docs_ini.parent.exists() or docs_ini.exists():
                _write_values_to_ini(docs_ini, send_rate, port)
                success = True
    except Exception as e:
        print(f"No se pudo escribir en la carpeta de Documents: {e}")
    return success