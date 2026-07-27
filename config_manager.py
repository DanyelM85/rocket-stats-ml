import os
import configparser
from pathlib import Path

# Rutas típicas según la plataforma
DEFAULT_PATHS = [
    Path(r"C:\Program Files\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Epic Games\rocketleague"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\rocketleague"),
    Path(r"C:\Program Files\Steam\steamapps\common\rocketleague"),
]

RELATIVE_INI_PATH = Path("TAGame/Config/DefaultStatsAPI.ini")

def find_rl_installation() -> Path | None:
    """Busca la ruta de instalación de Rocket League en las carpetas habituales."""
    for path in DEFAULT_PATHS:
        ini_candidate = path / RELATIVE_INI_PATH
        if ini_candidate.exists() or path.exists():
            return path
    return None

def get_valid_ini_path() -> Path:
    """Obtiene la ruta final del archivo DefaultStatsAPI.ini (autodetectada o manual)."""
    base_path = find_rl_installation()
    
    if base_path and (base_path / RELATIVE_INI_PATH).parent.exists():
        print(f"[+] Rocket League detectado automáticamente en: {base_path}")
        return base_path / RELATIVE_INI_PATH

    print("[!] No se encontró la instalación estándar de Rocket League (Epic/Steam).")
    
    while True:
        user_input = input("👉 Introduce la ruta raíz de instalación de Rocket League (ej: D:\\Juegos\\rocketleague): ").strip('"\' ')
        custom_path = Path(user_input)
        
        ini_path = custom_path / RELATIVE_INI_PATH
        
        # Verificamos si existe la carpeta TAGame/Config
        if ini_path.parent.exists():
            return ini_path
        else:
            print(f"[X] La ruta proporcionada no parece válida. No se encontró la carpeta: {ini_path.parent}")

def setup_stats_api(send_rate: float = 30.0, port: int = 49123) -> bool:
    """
    Lee y/o modifica el archivo DefaultStatsAPI.ini con la configuración elegida.
    """
    ini_path = get_valid_ini_path()
    
    # Nos aseguramos de que el directorio del .ini exista
    ini_path.parent.mkdir(parents=True, exist_ok=True)

    config = configparser.ConfigParser()
    # Preservar mayúsculas/minúsculas de las llaves .ini
    config.optionxform = str  # type: ignore

    # Si el archivo ya existe, lo leemos
    if ini_path.exists():
        config.read(ini_path)

    # Rocket League suele leer estas propiedades bajo la sección [DefaultStatsAPI] o [Engine.StatsAPI]
    # Si la sección no existe la creamos o usamos el archivo plano si aplica
    section = "DefaultStatsAPI"
    if not config.has_section(section):
        config.add_section(section)

    # Asignar valores
    config.set(section, "PacketSendRate", str(send_rate))
    config.set(section, "Port", str(port))

    try:
        with open(ini_path, "w", encoding="utf-8") as configfile:
            config.write(configfile)
        print(f" [✓] Archivo configurado con éxito en:\n    {ini_path}")
        print(f" [i] PacketSendRate = {send_rate} | Port = {port}")
        print(" [!] Recuerda reiniciar Rocket League si ya lo tenías abierto.")
        return True
    except PermissionError:
        print(f"[X] Error de permisos al escribir en {ini_path}. Intenta ejecutar el script como Administrador.")
        return False
    except Exception as e:
        print(f"[X] Error inesperado: {e}")
        return False

if __name__ == "__main__":
    # Test individual del módulo
    setup_stats_api(send_rate=30.0, port=49123)