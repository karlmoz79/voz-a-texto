# Reporte de Errores y Mejoras Pendientes

Este documento detalla los problemas técnicos y bugs identificados en la aplicación **Voz a Texto**.

## 1. Importaciones Duplicadas
- **Archivo:** `backend/voz_a_texto/desktop/app.py`
- **Línea:** 10
- **Descripción:** Se detectó un import duplicado de la librería `sys`.
- **Snippet:**
  ```python
  import sys  # Línea 1
  # ...
  import sys  # Línea 10 - DUPLICADO
  ```

## 2. Pixmap Opcional no Manejado
- **Archivo:** `backend/voz_a_texto/desktop/tray.py`
- **Línea:** 35-37
- **Descripción:** Si el archivo `tray_recording_path` no existe en disco, `cached_pixmaps["recording"]` se establece como `None`.
- **Consecuencia:** En `apply_state()`, si el pixmap es nulo, la bandeja del sistema no se actualiza y no mostrará visualmente el estado "grabando".

## 3. Posible AttributeError (XDG Session)
- **Archivo:** `backend/voz_a_texto/desktop/native_typing.py`
- **Línea:** 85
- **Descripción:** El código intenta ejecutar `.lower()` sobre una variable de entorno.
- **Snippet:**
  ```python
  session_type = self._read_env("XDG_SESSION_TYPE").lower()
  ```
- **Riesgo:** Si `XDG_SESSION_TYPE` no está definido (retorna `None`), la aplicación lanzará una excepción y se cerrará.

## 4. Silenciamiento de Errores en Autostart
- **Archivo:** `backend/voz_a_texto/desktop/autostart.py`
- **Líneas:** 83-88
- **Descripción:** El método `disable()` usa un bloque `try-except` que ignora fallos.
- **Detalle:** Capturar solo `FileNotFoundError` está bien para casos donde el archivo ya no existe, pero otros errores (como falta de permisos) deberían ser notificados en lugar de fallar silenciosamente.

## 5. Asignación Directa a Propiedad (ModelManager)
- **Archivo:** `backend/voz_a_texto/desktop/controller.py`
- **Líneas:** 374, 435, 442
- **Descripción:** Se está modificando `self.model_manager.runtime_config` directamente.
- **Recomendación:** Se debe verificar si el `ModelManager` posee una propiedad con *setter* o un método específico para actualizar la configuración y asegurar la integridad de los datos.

## 6. Comportamiento Indefinido en Servidor IPC
- **Archivo:** `backend/voz_a_texto/desktop/controller.py`
- **Líneas:** 72-75
- **Descripción:** Se llama a `removeServer` inmediatamente antes de `listen`.
- **Snippet:**
  ```python
  self.ipc_server.removeServer("voz_a_texto_ipc")
  if self.ipc_server.listen("voz_a_texto_ipc"):
  ```
- **Riesgo:** En algunos sistemas operativos, esto puede causar colisiones si el socket todavía está en uso por el kernel, causando que la aplicación no pueda recibir órdenes de apertura.

## 7. Desincronización de UI en Ajustes
- **Archivo:** `backend/voz_a_texto/desktop/settings_window.py`
- **Líneas:** 163-168
- **Descripción:** Si la función `_set_combo_value` no localiza el modelo en la lista desplegable, simplemente retorna la ejecución.
- **Problema:** Esto deja la interfaz gráfica mostrando un valor que no corresponde a la realidad del programa.

## 8. Desconexión Prematura de Socket IPC
- **Archivo:** `backend/voz_a_texto/desktop/controller.py`
- **Línea:** 86
- **Descripción:** El cierre del socket se ejecuta de forma síncrona inmediata.
- **Mejora:** Debería moverse a un *callback* del evento `disconnected()` o asegurar que los bytes fueron escritos totalmente antes de forzar el cierre de la conexión.