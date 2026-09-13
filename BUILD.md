# Cómo generar y actualizar el .exe
python -m PyInstaller RocketStatsML.spec --clean --noconfirm

Este proyecto se empaqueta con [PyInstaller](https://pyinstaller.org) en un único archivo portable `RocketStatsML.exe`. No hace falta tener Python instalado en la PC donde se vaya a usar el `.exe` — solo en la PC donde lo generas.

## 1. Preparar el entorno (solo la primera vez)

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

## 2. Generar / actualizar el .exe

Cada vez que cambies código (`main.py`, `web_server.py`, `config_manager.py`) o cualquier archivo dentro de `web/` (`index.html`, `overlay.html`), vuelve a correr:

```powershell
python -m PyInstaller RocketStatsML.spec --clean --noconfirm
```

Esto regenera `dist/RocketStatsML.exe` con el código y los archivos web más recientes. El archivo `RocketStatsML.spec` ya está configurado para incluir la carpeta `web/` completa — no necesitas tocarlo salvo que quieras cambiar algo del empaquetado (ver sección 4).

El primer build tarda ~1-2 minutos; los siguientes son más rápidos gracias a la caché en `build/`.

## 3. Probar el .exe

1. Ve a la carpeta `dist/`.
2. Ejecuta `RocketStatsML.exe`.
3. Debe abrir una ventana de Chrome con el panel de control, igual que con `python main.py`.

**Importante:** el `.exe` crea `app_config.json` y la carpeta `data/matches/` en la carpeta **desde donde se ejecuta** (normalmente `dist/`, o donde sea que muevas el `.exe`). Si vas a distribuir el `.exe` a otra PC o carpeta, muévelo a su propia carpeta dedicada (no sueltes solo el `.exe` en cualquier lado) para que esos archivos queden organizados junto a él.

## 4. Cosas que sí requieren tocar el `.spec` o el comando

| Cambio | Qué hacer |
|---|---|
| Agregaste una nueva carpeta/archivo de datos (no solo dentro de `web/`) | Agrega otra entrada en `datas=[...]` dentro de `RocketStatsML.spec`, ej: `('mi_carpeta', 'mi_carpeta')` |
| Agregaste una nueva dependencia de Python (`pip install algo-nuevo`) | Agrégala a `requirements.txt` y corre `pip install -r requirements.txt` antes de rebuildear |
| Quieres que NO se vea la ventana de consola negra detrás de la app | Cambia `console=True` a `console=False` en `RocketStatsML.spec` (perderás los mensajes de conexión/errores en texto) |
| El build falla con "Hidden import X not found" | Casi siempre es una advertencia inofensiva (ya pasa con `pycparser`/`importlib_resources` en este proyecto y no afecta nada). Si el `.exe` no arranca por eso, agrega el nombre del módulo a `hiddenimports=[...]` en el `.spec` |

## 5. Distribuir el .exe

- Es un único archivo (~18 MB), no necesita instalador.
- Cópialo a la carpeta donde quieras usarlo junto con — si aplica — un `app_config.json` ya configurado (opcional, se genera solo si no existe).
- Windows Defender / SmartScreen puede marcar el `.exe` como "desconocido" la primera vez (normal en ejecutables de PyInstaller sin firma digital) — hay que darle "Ejecutar de todas formas".
- No necesita Rocket League ni Python instalados para *abrir*, pero sí necesita Rocket League instalado en esa PC para poder capturar telemetría en vivo.

## Comando de referencia (equivalente a correr el .spec, por si se pierde)

```powershell
python -m PyInstaller --name RocketStatsML --onefile --add-data "web;web" --clean --noconfirm main.py
```
