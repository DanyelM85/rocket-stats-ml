import os
import json
from pathlib import Path

# Rutas típicas según la plataforma
DEFAULT_PATHS = [
    Path(r"C:\Program Files\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\rocketleague"),
    Path(r"C:\Program Files\Steam\steamapps\common\rocketleague"),
]

RELATIVE_INI_PATH = Path("TAGame/Config/DefaultStatsAPI.ini")
CONFIG_JSON_PATH = Path("app_config.json")

def load_saved_path() -> str | None:
    """Carga la ruta de instalación de Rocket League guardada en app_config.json."""
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("rl_installation_path")
        except:
            pass
    return None

def save_installation_path(path_str: str):
    """Guarda la ruta de instalación en app_config.json."""
    try:
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump({"rl_installation_path": path_str}, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar la ruta de instalación en JSON: {e}")

def find_rl_installation() -> Path | None:
    """Busca la ruta de instalación de Rocket League en las carpetas habituales o en la guardada."""
    saved = load_saved_path()
    if saved and Path(saved).exists():
        return Path(saved)

    for path in DEFAULT_PATHS:
        ini_candidate = path / RELATIVE_INI_PATH
        if ini_candidate.exists() or path.exists():
            # Guardamos para futuras ejecuciones
            save_installation_path(str(path))
            return path
    return None

def validate_rl_path(path_str: str) -> tuple[bool, str]:
    try:
        cleaned_path = path_str.strip('"\' ')
        if not cleaned_path:
            return False, "La ruta no puede estar vacía."
        path = Path(cleaned_path)
        
        # Intentar verificar si existe la ruta en el disco de manera segura
        if not path.exists():
            return False, "La ruta especificada no existe en el disco."
        
        # Indicadores de que es el directorio raíz de Rocket League (TAGame o Binaries)
        has_tagame = (path / "TAGame").exists()
        has_binaries = (path / "Binaries").exists()
        has_ini_dir = (path / RELATIVE_INI_PATH.parent).exists()
        
        if has_tagame or has_binaries or has_ini_dir:
            return True, ""
        
        return False, "La carpeta existe, pero no parece ser la raíz de Rocket League (debe contener 'TAGame' o 'Binaries')."
    except Exception as e:
        return False, f"Ruta inválida o inaccesible: {e}"

def get_valid_ini_path() -> Path:
    """Obtiene la ruta final del archivo DefaultStatsAPI.ini."""
    base_path = find_rl_installation()
    if base_path:
        return base_path / RELATIVE_INI_PATH
    return Path("")

def read_ini_values(ini_path: Path) -> tuple[int, float]:
    """Lee los valores actuales de Port y PacketSendRate del archivo .ini de forma segura."""
    port = 49123
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
            # Detectar inicio de sección
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
                    # Si viene con decimales de python (.0), los guardamos como int si es entero para más limpieza
                    val = int(send_rate) if send_rate.is_integer() else send_rate
                    new_lines.append(f"{prefix}PacketSendRate={val}\n")
                    rate_updated = True
                    continue

            new_lines.append(line)

        # Si la sección no tenía las llaves, las agregamos al final del archivo
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

def setup_stats_api(send_rate: float = 30.0, port: int = 49123) -> bool:
    """
    Modifica el archivo DefaultStatsAPI.ini en la instalación,
    y también TAStatsAPI.ini en Documents/My Games/Rocket League.
    """
    success = False
    
    # 1. Configurar en carpeta de instalación
    ini_path = get_valid_ini_path()
    if ini_path and ini_path != Path(""):
        success = _write_values_to_ini(ini_path, send_rate, port)

    # 2. Configurar en Documents/My Games/Rocket League
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