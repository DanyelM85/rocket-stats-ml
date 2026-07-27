# Plan de Implementación: Interfaz de Usuario Web para Configuración de Rocket League

Este plan detalla cómo implementar una interfaz de usuario (UI) basada en navegador (HTML/CSS/JS) y Python que sirva como alternativa amigable cuando no se encuentre la instalación de Rocket League automáticamente.

## 1. Arquitectura y Componentes

Utilizaremos únicamente librerías estándar de Python para evitar dependencias externas (`http.server`, `webbrowser`, `threading`, `tkinter`).

### A. Servidor Web Integrado (`web_server.py` o módulo interno)
Un servidor HTTP ligero que:
1. **Sirva la UI (HTML/CSS/JS)** de forma local (ej. `http://localhost:8000`).
2. **Exponga APIs locales** simples usando solicitudes `POST` / `GET`:
   - `/api/browse`: Abre un cuadro de diálogo nativo (`tkinter.filedialog.askdirectory`) para seleccionar una carpeta y devuelve la ruta seleccionada.
   - `/api/validate`: Recibe la ruta ingresada, comprueba si es válida (si existe o si se puede estructurar `TAGame/Config`), y devuelve éxito o error.
   - `/api/submit`: Guarda la ruta seleccionada, detiene el servidor de forma segura y reanuda el flujo principal del programa.

### B. Interfaz de Usuario Web (`web/index.html`)
Una página web interactiva con un diseño moderno, limpio y responsive (estilo Rocket League o tema oscuro moderno):
- **Encabezado**: Título llamativo indicando que no se detectó Rocket League.
- **Sección de Selección**:
  - Un campo de texto editable con la ruta de instalación.
  - Un botón de **"Buscar Carpeta"** (Browse) que llame a `/api/browse` y rellene el campo automáticamente usando el selector de archivos nativo de Windows.
- **Validación en tiempo real**: Mensajes de error claros si la ruta seleccionada no es correcta.
- **Botón de Confirmación**: Un botón verde "Guardar y Continuar" que envía la ruta a `/api/submit`.
- **Pantalla de Éxito**: Una vez guardado con éxito, muestra un mensaje indicando que puede volver a la consola y cierra la pestaña del navegador automáticamente.

### C. Integración en `config_manager.py`
Modificar `get_valid_ini_path()` para realizar el siguiente flujo:
1. **Autodetect**: Intenta buscar la instalación de forma automática.
2. **Web Fallback**: Si no se encuentra:
   - Inicia el servidor web local en un puerto disponible (ej: `49124` o dinámico).
   - Abre el navegador web del usuario automáticamente usando `webbrowser.open`.
   - Espera a que el usuario complete el proceso en la web.
   - Una vez el usuario envía una ruta válida, el servidor se detiene y devuelve la ruta configurada.
3. **CLI Fallback**: Si la inicialización de la interfaz web o el servidor falla por alguna razón (ej. entorno sin GUI), se vuelve al bucle de entrada en la consola (`input()`) como plan de respaldo absoluto.

---

## 2. Plan de Acción Paso a Paso

### Paso 1: Crear la interfaz HTML/CSS/JS (`web/index.html` o template en Python)
Diseñaremos una plantilla HTML autocontenida (CSS y JS embebidos para simplificar la entrega y evitar problemas de rutas relativas). Usaremos Bootstrap para un diseño estético, moderno, con degradados oscuros e iconos elegantes.

### Paso 2: Desarrollar el servidor local (`web_server.py`)
Implementar una clase heredada de `http.server.BaseHTTPRequestHandler` para gestionar la interfaz y las llamadas de API de forma asíncrona o en un hilo secundario:
- Evitar bloquear el flujo de control de forma indefinida.
- Manejar la interacción con `tkinter` en el hilo principal si es necesario (ya que `tkinter` requiere ejecutarse en el hilo principal en algunos sistemas operativos).

### Paso 3: Integrar y probar en `config_manager.py`
Reemplazar la interacción directa por consola en `get_valid_ini_path` para llamar a esta interfaz de navegador.

### Paso 4: Pruebas y Validación
- Probar el caso de éxito (el usuario selecciona una carpeta válida en la UI).
- Probar validación de errores (el usuario selecciona una carpeta incorrecta).
- Probar el comportamiento del navegador y el cierre de servidor.
