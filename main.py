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
        messagebox.showwarning(
            "Rocket League Stats",
            "La aplicación ya está abierta.\nBúscala en tus ventanas o en la barra de tareas."
        )
        root.destroy()
        sys.exit(0)

    print("=== Iniciando Panel de Control de Estadísticas de Rocket League ===")
    print("[i] Abriendo ventana de la interfaz web...")

    # Iniciar la interfaz web que permite configurar, simular y monitorear la API
    run_config_ui(validate_rl_path, lambda p: None)

if __name__ == "__main__":
    main()
