# VoxFlow — Transcripción de Voz a Texto Local

> Aplicación de escritorio local y privada para Linux que captura audio del micrófono y lo transcribe sin conexión a internet. Reside en la bandeja del sistema; sin servidor, sin navegador, sin suscripciones.

---

## Características

| Función | Detalle |
|---|---|
| **Grabación por acción** | El micrófono solo se abre al pulsar el atajo configurado. Al soltar, la grabación continúa hasta que el usuario pulsa **■ Detener** o **✕ Cancelar** en el popup flotante. |
| **Popup de grabación** | Mini-ventana flotante siempre encima con waveform animada y botones de acción. |
| **VU meter en tiempo real** | Barra de nivel de audio mientras se graba, visible en la pestaña Inicio. |
| **Dictado nativo** | Escribe el texto transcrito directamente en la ventana enfocada con `xdotool` (solo X11). |
| **Precarga de modelo** | El modelo ASR se carga al arrancar para eliminar cold start. |
| **Cambio de modelo en caliente** | Cambia entre modelos sin reiniciar. Con fallback automático si falla. |
| **Selector de micrófono** | Elige cualquier dispositivo de entrada disponible en el sistema. |
| **Idioma forzado** | Fija el idioma (ES/EN/Auto) para modelos Whisper, evitando la detección automática que es lenta en CPU. |
| **Historial acumulado** | Las transcripciones de la sesión se acumulan y se pueden exportar a `.txt`. |
| **Eliminar modelos del disco** | Libera espacio borrando la caché de HuggingFace del modelo seleccionado desde la propia UI. |
| **Autostart** | Crea un `.desktop` en `~/.config/autostart/` para iniciar con la sesión. |
| **Instancia única** | Solo un proceso puede controlar hotkey y micrófono a la vez (IPC con `QLocalServer`). |
| **Tema premium** | Interfaz FramelessWindow con paleta terrosa: verde bosque, sage, tostado y crema. |
| **Señales de audio** | Beep de inicio y finalización de grabación. |

---

## Modelos soportados

| Modelo | Clave | Engine | Idioma | Tamaño aprox. |
|---|---|---|---|---|
| **Fast Conformer ES** | `fastconformer_es` | NVIDIA NeMo | Solo español | ~480 MB |
| **Whisper Tiny** | `whisper_tiny` | faster-whisper | Multilenguaje | ~75 MB |
| **Whisper Base** | `whisper_base` | faster-whisper | Multilenguaje | ~142 MB |
| **Whisper Small** | `whisper_small` | faster-whisper | Multilenguaje | ~244 MB |
| **Whisper Medium** | `whisper_medium` | faster-whisper | Multilenguaje | ~760 MB |
| **Parakeet V3** | `parakeet_v3` | NVIDIA NeMo | Solo inglés | ~1.2 GB |

> **Nota:** Los modelos se descargan automáticamente de HuggingFace en el primer uso y se almacenan en `~/.cache/huggingface/hub/`.

---

## Estructura del proyecto

```
voz-a-texto/
├── backend/
│   ├── voz_a_texto/            # Núcleo Python reutilizable
│   │   ├── app_config.py       # AppConfig, RuntimeConfig, carga/guardado de config
│   │   ├── asr.py              # ModelManager, transcripción, warmup de modelos
│   │   ├── models.py           # Catálogo de ModelProfile y funciones de normalización
│   │   └── desktop/            # Shell de escritorio PySide6
│   │       ├── app.py          # QApplication entry point
│   │       ├── controller.py   # DesktopShellController (coordinador central)
│   │       ├── settings_window.py  # Ventana de ajustes (FramelessWindow, 5 páginas)
│   │       ├── tray.py         # TrayController y menú de bandeja
│   │       ├── recording_popup.py  # Popup flotante con waveform animada
│   │       ├── audio_capture.py    # AudioCaptureService (sounddevice)
│   │       ├── hotkey_service.py   # GlobalHotkeyService (pynput)
│   │       ├── native_typing.py    # NativeTypingService (xdotool)
│   │       ├── autostart.py        # AutostartService (.desktop en autostart)
│   │       ├── installation.py     # Lógica de instalación/desinstalación local
│   │       ├── transcript_store.py # TranscriptStore (historial de sesión)
│   │       ├── state.py            # ShellState inmutable y constantes de estado
│   │       ├── theme.py            # Paleta de colores y QSS global
│   │       ├── paths.py            # APP_DISPLAY_NAME, APP_SLUG y rutas XDG
│   │       ├── qt_runtime.py       # Inicialización del entorno Qt
│   │       └── single_instance.py  # Guard de instancia única
│   ├── scripts/
│   │   ├── desktop_app.py      # Entrypoint de desarrollo
│   │   ├── install_desktop.py  # Instalación local
│   │   └── uninstall_desktop.py
│   ├── tests/                  # Suite completa de tests unitarios (59 tests)
│   ├── assets/
│   │   └── notification.wav    # Sonido de inicio/fin de grabación
│   └── pyproject.toml
├── package.json                # Scripts npm de conveniencia
└── AGENTS.md                   # Guía de arquitectura para agentes de IA
```

---

## Requisitos del sistema

### Python y entorno
- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) para gestión del entorno

### Dependencias del sistema (Linux)

| Paquete | Para qué | Instalación |
|---|---|---|
| `libxcb-cursor0` | Plugin Qt `xcb` en Mint/Ubuntu/Debian | `sudo apt install libxcb-cursor0` |
| `xdotool` | Dictado nativo en ventana enfocada | `sudo apt install xdotool` |
| `libportaudio2` | Captura de audio con `sounddevice` | `sudo apt install libportaudio2` |

> **Limitación:** El dictado nativo solo funciona en sesiones **X11**. Wayland puro no está soportado en esta versión.

---

## Inicio rápido (modo desarrollo)

```bash
# 1. Preparar el entorno Python
cd backend && uv sync

# 2. Arrancar la aplicación
cd backend && uv run python scripts/desktop_app.py

# O usando npm desde la raíz:
npm run dev
```

La app inicia minimizada en la **bandeja del sistema**, precarga el modelo ASR y queda lista para usar con el atajo configurado (por defecto `Ctrl+Space`).

---

## Instalación local (sin modo desarrollo)

Para integrar VoxFlow como aplicación de usuario de Linux:

```bash
npm run desktop:install
```

Esto realiza automáticamente:
1. Copia el backend a `~/.local/share/vox-flow/desktop/backend/`
2. Ejecuta `uv sync --frozen` en el destino
3. Crea el launcher `~/.local/bin/voz-a-texto`
4. Registra la entrada `~/.local/share/applications/vox-flow.desktop`

Tras la instalación, **VoxFlow** aparece en el menú de aplicaciones del sistema.

### Desinstalar

```bash
npm run desktop:uninstall
```

Elimina el launcher, la entrada de aplicaciones y el autostart. **Conserva** `~/.config/voz-a-texto/config.json` y cualquier `.txt` exportado.

---

## Configuración persistente

La configuración se guarda en `~/.config/voz-a-texto/config.json`:

```json
{
  "active_model": "fastconformer_es",
  "hotkey": "Ctrl+Space",
  "input_device": null,
  "language": "es",
  "launch_at_login": false,
  "max_audio_sec": 300,
  "native_typing_enabled": true
}
```

### Variables de entorno (opcionales)

| Variable | Descripción |
|---|---|
| `ASR_MODEL_ID` | Sobreescribe el modelo activo al arrancar (p. ej. `small`) |
| `ASR_MAX_AUDIO_SEC` | Sobreescribe el límite máximo de segundos de grabación |

---

## Flujo de uso

```
Arranque → Precarga del modelo ASR
    ↓
[Bandeja del sistema] — siempre disponible
    ↓
Presionar atajo (Ctrl+Space) → Empieza la grabación
    ↓
Popup flotante con waveform animada
    ↓
■ Detener → Transcripción en background (hilo separado)
  ✕ Cancelar → Descarta la grabación
    ↓
Texto transcrito → Dictado nativo (xdotool) + Historial de sesión
```

---

## Desarrollo y calidad

```bash
# Sincronizar entorno
cd backend && uv sync

# Ejecutar tests (59 pruebas)
cd backend && ./.venv/bin/python -m unittest discover -s tests -t .
```

Los tests cubren: `AppConfig`, `ModelManager`, `AudioCaptureService`, `HotkeyService`, `NativeTypingService`, `AutostartService`, `TranscriptStore`, `DesktopShellController`, instalación y runtime Qt.

---

## Scripts npm disponibles (desde la raíz)

| Comando | Acción |
|---|---|
| `npm run dev` | Inicia la app en modo desarrollo |
| `npm run desktop` | Alias de `dev` |
| `npm run desktop:install` | Instala la app localmente para el usuario |
| `npm run desktop:uninstall` | Desinstala la app del sistema |

---

## Historial de implementación

Todas las fases del plan de migración a PySide están implementadas y validadas:

- **Fase 0:** preparación y congelamiento funcional ✅
- **Fase 1:** núcleo Python reutilizable (`AppConfig`, `ModelManager`, catálogo de modelos) ✅
- **Fase 2:** shell desktop (`QApplication`, instancia única, bandeja, ventana de ajustes) ✅
- **Fase 3:** hotkey global y captura nativa de audio con `sounddevice` ✅
- **Fase 4:** precarga de modelo y cambio seguro entre modelos ✅
- **Fase 5:** dictado nativo con `xdotool` y detección de entornos incompatibles ✅
- **Fase 6:** autostart con `.desktop`, endurecimiento del arranque, `npm run desktop` como camino principal ✅
- **Fase 7:** instalación local para Linux con `uv`, launcher, entrada de aplicaciones y desinstalación limpia ✅
- **Fase 8:** rediseño de interfaz premium con `FramelessWindow` (paleta forest/sage/cream), popup de grabación con waveform animada, VU meter, selector de micrófono, idioma forzado y gestión de caché de modelos ✅

---

*VoxFlow v0.7.12 — Diseñado con mentalidad local y alta estética.*
