import ctypes
import sys

from config_manager import validate_rl_path
from web_server import run_config_ui

_SINGLE_INSTANCE_MUTEX_NAME = "Global\\RocketStatsML_SingleInstance"
_ERROR_ALREADY_EXISTS = 183
_instance_lock_handle = None

def _acquire_single_instance_lock() -> bool:
    """Evita abrir una segunda instancia: dos procesos escuchando el mismo
    puerto/socket a la vez se pisan entre sí y dejan la app colgada."""
    global _instance_lock_handle
    _instance_lock_handle = ctypes.windll.kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != _ERROR_ALREADY_EXISTS

def main():
    if not _acquire_single_instance_lock():
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showwarning(
            "Rocket League Stats ML",
            "La aplicación ya está ejecutándose.\nSolo se permite una instancia activa a la vez."
        )
        root.destroy()
        sys.exit(0)

    print("=== Iniciando Panel de Control de Estadísticas de Rocket League ===")
    
    # Liberar puertos para evitar conflictos con procesos huérfanos o colgados
    from web_server import kill_process_on_port
    print("[i] Verificando y liberando puertos (8000, 49124)...")
    kill_process_on_port(8000)
    kill_process_on_port(49124)

    print("[i] Abriendo ventana de la interfaz web...")

    try:
        run_config_ui(validate_rl_path, lambda p: None)
    except (KeyboardInterrupt, SystemExit):
        print("\n[i] Aplicación cerrada por el usuario.")
    finally:
        if _instance_lock_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(_instance_lock_handle)
            except Exception:
                pass
        import os
        os._exit(0)

if __name__ == "__main__":
    main()
