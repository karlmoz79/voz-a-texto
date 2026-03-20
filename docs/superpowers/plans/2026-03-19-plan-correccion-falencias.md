# Plan de Correccion de Falencias

## Resumen
- Corregir el flujo de push-to-talk para que el microfono solo capture durante la pulsacion real.
- Limitar el hotkey global a una sola pestana propietaria.
- Unificar configuracion y documentacion del modelo ASR con Fast Conformer ES como default.
- Endurecer la instalacion y agregar pruebas automatizadas minimas.

## Cambios clave
### 1. Grabacion y privacidad
- Estado explicito `idle -> connecting -> ready -> recording -> processing`.
- Cancelacion correcta si el usuario suelta antes de que abra el WebSocket.
- Apertura y cierre real del microfono en cada dictado.
- Limpieza del buffer local entre sesiones.

### 2. Hotkey global
- Solo una sesion recibe `Alt+I` global.
- El backend reasigna propiedad al cerrar la pestana duena.
- El hotkey deja de depender del checkbox de dictado nativo.

### 3. Modelo y configuracion
- `ASR_MODEL_ID` como variable principal.
- `ASR_MAX_AUDIO_SEC` como limite real de audio.
- Compatibilidad temporal con `PARAKEET_MODEL_PATH` y `PARAKEET_MAX_AUDIO_SEC`.
- Fast Conformer ES como default y Parakeet como opcion configurable.

### 4. Verificacion
- Prueba unitaria del arbitraje de hotkey en backend.
- Prueba unitaria del flujo de estado de grabacion en frontend.
- Build del frontend y chequeos sintacticos de backend/Python.

## Supuestos
- Python 3.12+ sigue siendo el baseline documentado.
- No se agrega selector de modelo en la UI en esta iteracion.
- El hotkey global sigue limitado a Linux.
