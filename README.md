# Voz a Texto en Tiempo Real Local

Aplicacion de escritorio local y privada para capturar audio del microfono y transcribirlo offline con NVIDIA NeMo y OpenAI Whisper. Reside en la bandeja del sistema, sin necesidad de navegador ni servidor.

## Estructura
- `backend/voz_a_texto/`: nucleo Python reutilizable para configuracion, modelos ASR y shell de escritorio PySide.
- `backend/voz_a_texto/desktop/`: shell de escritorio con bandeja, hotkey global, captura nativa de audio y dictado.
- `backend/scripts/`: entrypoints del shell desktop, instalacion y desinstalacion.
- `docs/`: plan de migracion y documentacion de seguimiento.

## Requisitos
- Python 3.12+
- `uv` para el entorno Python del backend
- `PySide6` (se instala con `uv sync`)
- `libxcb-cursor0` en Linux Mint/Ubuntu/Debian para que Qt pueda cargar el plugin `xcb`
- `xdotool` en Linux si quieres dictado nativo
- PortAudio en el sistema para captura de audio con `sounddevice`

## Inicio rapido

### 1. Preparar el entorno
```bash
cd backend && uv sync
```

### 2. Arrancar el shell desktop
```bash
cd backend && uv run python scripts/desktop_app.py
```

Tambien puedes lanzarlo con npm (scripts de conveniencia):
```bash
npm run dev
```

La app inicia minimizada en la bandeja del sistema, precarga el modelo ASR y queda lista para push-to-talk con `Ctrl+Space`.

## Instalacion local (sin modo desarrollo)

Para integrar el shell desktop como app de usuario de Linux:

```bash
npm run desktop:install
```

Esto:
- Copia el backend a `~/.local/share/voz-a-texto/desktop/backend/`
- Ejecuta `uv sync --frozen`
- Crea el launcher `~/.local/bin/voz-a-texto`
- Registra `~/.local/share/applications/voz-a-texto.desktop`

Despues de instalar, la app aparece en el menu del sistema como **Voz a Texto**.

### Desinstalar
```bash
npm run desktop:uninstall
```

Elimina launcher, entrada de aplicaciones y autostart, pero **conserva** `~/.config/voz-a-texto/config.json` y cualquier historial exportado.

## Caracteristicas
- **Transcripcion local:** el audio se procesa en el equipo, sin enviar datos a servicios remotos.
- **Push-to-talk con hotkey global:** el microfono solo se abre mientras mantienes `Ctrl+Space` (configurable).
- **Dictado nativo:** la transcripcion se escribe directamente en la ventana enfocada con `xdotool`.
- **Bandeja del sistema:** estado del modelo, selector de modelo, toggles y exportacion desde la bandeja.
- **Precarga del modelo:** el modelo ASR se carga al arrancar para eliminar el cold start.
- **Cambio de modelo en caliente:** cambiar entre modelos sin reiniciar, con fallback al anterior si falla.
- **Autostart:** opcion para iniciar con la sesion creando `.desktop` en `~/.config/autostart/`.
- **Exportacion de texto:** historial acumulado exportable a `.txt`.
- **Instancia unica:** solo un proceso puede controlar hotkey y microfono a la vez.
- **Tema premium:** interfaz minimalista con paleta terrosa (verde bosque, sage, tostado y crema).

## Modelos soportados

| Modelo | Clave | Descripcion |
|--------|-------|-------------|
| Fast Conformer ES | `fastconformer_es` | `nvidia/stt_es_fastconformer_hybrid_large_pc` — default, español |
| Whisper Tiny | `whisper_tiny` | `tiny` — multilenguaje, muy rapido, ~75 MB |
| Whisper Base | `whisper_base` | `base` — multilenguaje, rapido, ~142 MB |
| Whisper Small | `whisper_small` | `small` — multilenguaje, equilibrado, ~244 MB |
| Whisper Medium | `whisper_medium` | `medium` — multilenguaje, preciso, ~760 MB |
| Parakeet V3 | `parakeet_v3` | `nvidia/parakeet-tdt-0.6b-v3` — solo ingles, preciso, ~1.2 GB |

El modelo activo se configura desde la bandeja, los ajustes, o en `~/.config/voz-a-texto/config.json`.

## Configuracion persistente

La app guarda ajustes en `~/.config/voz-a-texto/config.json`:
```json
{
  "active_model": "fastconformer_es",
  "max_audio_sec": 30,
  "native_typing_enabled": true,
  "hotkey": "Ctrl+Space",
  "launch_at_login": false
}
```

## Dependencias del sistema y limitaciones

| Dependencia | Uso | Instalacion |
|-------------|-----|-------------|
| `libxcb-cursor0` | Plugin Qt `xcb` | `sudo apt install libxcb-cursor0` |
| `xdotool` | Dictado nativo en ventana enfocada | `sudo apt install xdotool` |
| PortAudio | Captura de audio con `sounddevice` | `sudo apt install libportaudio2` |

**Limitaciones conocidas:**
- Dictado nativo solo soportado en sesiones X11. Wayland puro no esta soportado en esta version.
- Plataforma oficial: Linux general. macOS y Windows no estan soportados.
- Empaquetados autocontenidos (AppImage, .deb, Flatpak) quedan fuera de esta version.

## Calidad
```bash
# Tests Python del backend
cd backend && ./.venv/bin/python -m unittest discover -s tests -t .
```

## Estado de migracion a PySide

Todas las fases del plan de migracion estan implementadas y validadas:

- **Fase 0:** preparacion y congelamiento funcional ✅
- **Fase 1:** nucleo Python reutilizable (`AppConfig`, `ModelManager`, catalogo de modelos) ✅
- **Fase 2:** shell desktop (`QApplication`, instancia unica, bandeja, ventana de ajustes) ✅
- **Fase 3:** hotkey global y captura nativa de audio con `sounddevice` ✅
- **Fase 4:** precarga de modelo y cambio seguro entre modelos ✅
- **Fase 5:** dictado nativo con `xdotool` y deteccion de entornos incompatibles ✅
- **Fase 6:** autostart con `.desktop`, endurecimiento del arranque, `npm run desktop` como camino principal ✅
- **Fase 7:** instalacion local para Linux con `uv`, launcher, entrada de aplicaciones y desinstalacion limpia ✅
- **Fase 8:** rediseño de interfaz premium con tema terroso (FramelessWindow, paleta forest/sage/cream) ✅
