from config_manager import setup_stats_api

def main():
    print("=== Configurando Rocket League Stats API ===")
    
    # 1. Configurar el archivo .ini (PacketSendRate > 0 activa la API)
    # Recomendado: 30 o 60 para captura fluida de datos sin sobrecargar
    config_ok = setup_stats_api(send_rate=30.0, port=49123)
    
    if not config_ok:
        print("No se pudo preparar el archivo de configuración. Cancelando...")
        return

    # 2. Aquí llamarías a tus módulos dentro de /parsers para conectar al socket ws://localhost:49123
    print("\nTodo listo para conectar al WebSocket...")

if __name__ == "__main__":
    main()