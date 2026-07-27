from config_manager import validate_rl_path
from web_server import run_config_ui

def main():
    print("=== Iniciando Panel de Control de Estadísticas de Rocket League ===")
    print("[i] Abriendo ventana de la interfaz web...")
    
    # Iniciar la interfaz web que permite configurar, simular y monitorear la API
    run_config_ui(validate_rl_path, lambda p: None)

if __name__ == "__main__":
    main()
