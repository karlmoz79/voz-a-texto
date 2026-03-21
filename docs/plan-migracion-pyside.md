# Plan de Migracion a PySide sin Servidores

## Resumen
- Migrar la app actual React + Node + WebSocket a una sola aplicacion de escritorio en Python con `PySide6`, residente en bandeja del sistema, sin backend HTTP ni frontend web.
- La app correra en segundo plano, precargara el modelo al arrancar, escuchara una combinacion global de teclas para push-to-talk, capturara microfono localmente, transcribira con NeMo y escribira el texto en la ventana actualmente enfocada cuando el dictado nativo este activo.
- La v1 del plan queda definida para `Linux general`, con soporte oficial de dictado nativo y foco sobre sesiones X11 compatibles.
- La UI sera `bandeja + ventana de ajustes`, sin ventana principal persistente.

## Fases de Implementacion
### Fase 0. Preparacion y congelamiento funcional
- Congelar el comportamiento actual como referencia de paridad: hotkey global, push-to-talk, dictado nativo, exportacion y cambio de modelo.
- Definir una carpeta nueva para la app PySide dentro del backend Python para no mezclar UI nueva con React/Node durante el arranque de la migracion.
- Documentar dependencias nuevas esperadas: `PySide6`, `sounddevice` y cualquier helper de configuracion o empaquetado.
- Criterio de salida: existe una base documental clara de la funcionalidad actual y una estructura inicial de proyecto para la app de escritorio.

### Fase 1. Nucleo Python reutilizable
- Extraer la logica de ASR de `transcribe.py` a un modulo reutilizable orientado a clases, sin `stdin/stdout` ni mensajes JSON.
- Centralizar la resolucion de configuracion de modelos, maximo de audio y estado del modelo en un `ModelManager`.
- Crear `AppConfig` para persistir ajustes de usuario en `~/.config/voz-a-texto/config.json`.
- Criterio de salida: el motor de transcripcion y la configuracion pueden usarse desde Python puro sin depender de Node ni del servidor.

### Fase 2. Shell de escritorio con PySide
- Crear la aplicacion `QApplication`, control de instancia unica y `QSystemTrayIcon`.
- Implementar la ventana de ajustes con estado de modelo, toggle de dictado nativo, selector de modelo e historial reciente.
- Añadir menu de bandeja con abrir ajustes, cambiar modelo, activar/desactivar dictado nativo, exportar texto, autostart y salir.
- Criterio de salida: la app inicia minimizada a bandeja, muestra estado y puede abrir/cerrar su ventana de ajustes sin navegador.

### Fase 3. Hotkey global y captura nativa de audio
- Integrar un `HotkeyService` que reemplace el ownership por pestanas con una sola escucha global dentro de la app residente.
- Implementar `AudioCaptureService` con captura local a `16 kHz mono`, apertura al presionar el hotkey y cierre al soltarlo.
- Mantener limites de duracion, limpieza de buffers y estados `grabando` y `procesando`.
- Criterio de salida: desde la bandeja, el hotkey global inicia y detiene grabacion real sin servidor ni interfaz web.

### Fase 4. Precarga de modelo y cambio entre Fast Conformer y Parakeet
- Precargar el modelo activo al arrancar la app para eliminar el cold start del primer dictado.
- Implementar selector real entre `Fast Conformer ES` y `Parakeet v3`, con recarga segura en background.
- Mantener fallback al modelo anterior si el nuevo no carga correctamente.
- Criterio de salida: el usuario puede elegir cualquiera de los dos modelos y la app queda operativa sin reiniciar.

### Fase 5. Dictado nativo sobre ventana enfocada
- Mover la logica de escritura nativa a un `NativeTypingService` integrado en Python.
- Mantener compatibilidad con `xdotool` en Linux y validar que el texto se inserta en la ventana enfocada al terminar la transcripcion.
- Manejar errores de foco, sesion no soportada o comando ausente con mensajes visibles desde bandeja/ajustes.
- Criterio de salida: con una app externa enfocada, el texto dictado aparece en ese campo sin necesitar navegador abierto.

### Fase 6. Autostart, endurecimiento y retiro del stack web
- Implementar opcion de inicio automatico con `.desktop` en `~/.config/autostart/`.
- Añadir pruebas unitarias y checklist manual de paridad funcional.
- Retirar del camino principal de ejecucion las piezas de React, Vite, Express y WebSocket, dejandolas solo mientras dure la migracion o eliminandolas cuando la nueva app ya sea estable.
- Criterio de salida: la app PySide funciona sola, en segundo plano, con autostart y sin depender del stack web para su uso normal.

### Fase 7. Empaquetado y distribucion local
- Separar formalmente dos caminos soportados: `desarrollo` desde el checkout con `uv` y `distribucion local` para usuarios finales sin depender de `npm run desktop`.
- Priorizar como primer entregable un instalador local para Linux basado en `uv`, con launcher de usuario y entrada `.desktop`, antes de evaluar formatos autocontenidos como AppImage o paquetes del sistema.
- Preparar una instalacion reutilizable para el usuario actual que registre un comando estable, acceso en menu de aplicaciones y compatibilidad con autostart.
- Documentar instalacion, actualizacion, desinstalacion, dependencias del sistema y limitaciones conocidas.
- Criterio de salida: existe una forma repetible de instalar, arrancar, reiniciar y desinstalar la app PySide fuera del entorno de desarrollo, manteniendo intacta la configuracion del usuario.

## Cambios de Implementacion
### 1. Nueva arquitectura de aplicacion
- Reemplazar el flujo `frontend + backend + WebSocket` por un solo proceso Python con `QApplication`.
- Crear un paquete Python nuevo para la app de escritorio con estos subsistemas:
  - `TrayController`: icono de bandeja, menu contextual, estados y acciones rapidas.
  - `SettingsWindow`: ventana pequena de configuracion y estado.
  - `AppConfig`: persistencia local de ajustes.
  - `HotkeyService`: escucha global de la combinacion de teclas.
  - `AudioCaptureService`: captura local del microfono en `16 kHz mono`.
  - `ModelManager`: carga, precarga, cambio y uso del modelo ASR.
  - `NativeTypingService`: escritura en la ventana enfocada.
  - `TranscriptStore`: historial reciente y exportacion a `.txt`.
- Eliminar la dependencia funcional de Express, `ws`, Vite y React del camino de ejecucion principal. Durante la migracion se mantienen solo como referencia hasta validar paridad; despues se retiran del runtime.
- Forzar instancia unica de la app para evitar dos listeners globales y dos procesos de dictado simultaneos.

### 2. Interfaz PySide y experiencia de uso
- Usar `QSystemTrayIcon` como shell principal.
- Menu de bandeja con:
  - estado actual: `cargando modelo`, `listo`, `grabando`, `procesando`, `error`
  - abrir ajustes
  - activar/desactivar dictado nativo
  - cambiar modelo activo
  - exportar ultima transcripcion
  - iniciar al arrancar sesion
  - salir
- `SettingsWindow` compacta con:
  - estado del modelo y del microfono
  - selector de modelo
  - visualizacion de hotkey configurada
  - toggle de dictado nativo
  - area de historial/transcripcion reciente
  - boton de exportacion
- No habra ventana principal siempre visible. La app inicia minimizada a bandeja.

### 3. Hotkey global y push-to-talk
- Mantener el concepto actual de combinacion global con escucha profunda del teclado, pero moverlo a un servicio Python integrado.
- Conservar como valor por defecto la combinacion actual `Alt+Z`, pero dejarla configurable en ajustes para futuras iteraciones.
- Comportamiento fijo:
  - al presionar la combinacion: abrir captura de microfono
  - mientras se mantenga: acumular audio
  - al soltar: detener captura y lanzar transcripcion
- El hotkey ya no dependera de ninguna UI web ni de ownership entre pestanas, porque habra una sola instancia residente del sistema.

### 4. Captura de audio y transcripcion local
- Sustituir la captura del navegador por captura nativa en Python usando una sola ruta de audio local.
- Implementar captura de microfono con `sounddevice` y `numpy` para producir PCM16 a `16 kHz`, evitando depender de Qt Multimedia para el pipeline de audio.
- Refactorizar la logica de `transcribe.py` a clases reutilizables dentro de la app de escritorio:
  - carga del modelo al arrancar la app
  - reutilizacion del modelo ya cargado
  - transcripcion por buffer de audio al soltar el hotkey
- Precarga obligatoria del modelo seleccionado al iniciar la aplicacion para eliminar el "primer arranque lento" en el primer dictado.
- Mantener un solo modelo activo en memoria a la vez para evitar consumo excesivo de RAM/VRAM.

### 5. Modelos soportados
- Soportar explicitamente dos perfiles de modelo:
  - `Fast Conformer ES` como default: `nvidia/stt_es_fastconformer_hybrid_large_pc`
  - `Parakeet v3`: `nvidia/parakeet-tdt-0.6b-v3`
- El selector de modelo vive en ajustes y tambien en el menu de bandeja.
- Al cambiar de modelo:
  - la app entra a estado `cargando modelo`
  - precarga el nuevo modelo en background
  - solo reemplaza el modelo activo cuando termina correctamente
  - si falla, conserva el modelo anterior y muestra error visible
- La configuracion deja de vivir en `JS env` y pasa a un archivo de configuracion Python persistido por usuario.

## Interfaces, Configuracion y Compatibilidad
- Sustituir las variables `ASR_MODEL_ID`, `ASR_MAX_AUDIO_SEC`, `NATIVE_TYPE_ENABLED` y hotkey por una configuracion persistida localmente, por ejemplo `~/.config/voz-a-texto/config.json`.
- Esquema de configuracion v1:
  - `active_model`: `fastconformer_es` | `parakeet_v3`
  - `max_audio_sec`: numero, default `30`
  - `native_typing_enabled`: boolean, default `true`
  - `hotkey`: string serializada, default `Alt+Z`
  - `launch_at_login`: boolean, default `false`
- El dictado nativo seguira usando un adaptador de comandos Linux. V1 oficial:
  - `xdotool` para escribir en la ventana enfocada en sesiones compatibles
  - deteccion explicita de entorno no soportado para desactivar la funcion con mensaje claro en la UI
- Implementar arranque automatico opcional con archivo `.desktop` en `~/.config/autostart/`.
- Mantener `uv` como base del entorno Python de desarrollo y ejecucion.
- Definir en Fase 7 un launcher instalado por usuario, por ejemplo en `~/.local/bin/voz-a-texto`, y una entrada de aplicaciones en `~/.local/share/applications/voz-a-texto.desktop`.
- El autostart y el menu de aplicaciones deben reutilizar el mismo entrypoint instalado para evitar divergencias entre el checkout de desarrollo y la instalacion local.
- La primera distribucion soportada seguira siendo `Linux general` con foco en sesiones X11 para dictado nativo; Wayland y bundles autocontenidos quedan como iteracion posterior.

## Plan de Validacion
- Pruebas unitarias de:
  - resolucion de modelo por configuracion
  - cambio de modelo con fallback al anterior si falla
  - parser/estado de hotkey global
  - serializacion de configuracion
  - construccion segura del comando de dictado nativo
- Pruebas de integracion manual:
  - la app inicia en bandeja y precarga el modelo sin abrir navegador ni servidor
  - al mantener el hotkey, el microfono se activa; al soltarlo, se genera transcripcion
  - con dictado nativo activo, el texto aparece en la aplicacion enfocada
  - con dictado nativo inactivo, el texto solo queda en historial/exportacion
  - el cambio entre Fast Conformer y Parakeet funciona sin reiniciar la app
  - la segunda instancia no toma control del hotkey ni del microfono
  - el autostart crea y elimina correctamente su `.desktop`
  - si el entorno no soporta dictado nativo, la app lo deshabilita y muestra aviso
  - una instalacion local crea launcher y entrada de aplicaciones sin depender de `npm`
  - la app instalada arranca desde el menu del sistema y reutiliza la misma configuracion del usuario
  - desinstalar elimina accesos directos y launchers sin borrar `config.json` ni el historial exportado
- Criterio de aceptacion:
  - la app cumple paridad funcional con el flujo actual de dictado local
  - no requiere HTTP, WebSocket, navegador ni pestanas abiertas
  - puede permanecer en segundo plano y operar desde bandeja
  - puede instalarse y relanzarse de forma repetible fuera del modo desarrollo

## Supuestos y decisiones cerradas
- Objetivo de plataforma: `Linux general`; el soporte explicito de Wayland no entra en esta v1 del plan.
- La UI sera `bandeja + ajustes`; no habra ventana principal persistente.
- `Fast Conformer ES` sera el modelo por defecto; `Parakeet v3` sera opcion seleccionable.
- El hotkey seguira existiendo como combinacion global y su default sera la combinacion actual `Alt+Z`, pero quedara preparado para configuracion posterior.
- El runtime final sera Python + PySide6; Node, Express, React y WebSocket salen del camino principal de ejecucion.
- La primera distribucion soportada de Fase 7 sera una instalacion local basada en `uv`, launcher de usuario y `.desktop`, no un bundle autocontenido.
- AppImage, `.deb`, Flatpak u otros formatos quedan fuera de esta iteracion inicial salvo que aparezca una necesidad concreta de distribucion masiva.
