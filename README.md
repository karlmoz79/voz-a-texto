# Voz a Texto en Tiempo Real Local

Aplicacion de escritorio local y privada para capturar audio del microfono y transcribirlo offline con NVIDIA NeMo. Reside en la bandeja del sistema, sin necesidad de navegador ni servidor.

## Estructura
- `backend/voz_a_texto/`: nucleo Python reutilizable para configuracion, modelos ASR y shell de escritorio PySide.
- `backend/voz_a_texto/desktop/`: shell de escritorio con bandeja, hotkey global, captura nativa de audio y dictado.
- `backend/scripts/`: entrypoints del shell desktop, instalacion y desinstalacion.
- `backend/`: servidor Node.js legado (en proceso de retiro).
- `frontend/`: app React + Vite legada (en proceso de retiro).
- `docs/`: plan de migracion y documentacion de seguimiento.

## Requisitos
- Python 3.12+
- `uv` para el entorno Python del backend
- Node.js 18+ y npm 8+ (solo para los scripts de conveniencia raiz)
- `PySide6` (se instala con `uv sync`)
- `libxcb-cursor0` en Linux Mint/Ubuntu/Debian para que Qt pueda cargar el plugin `xcb`
- `xdotool` en Linux si quieres dictado nativo
- PortAudio en el sistema para captura de audio con `sounddevice`

## Inicio rapido

### 1. Preparar el entorno
```bash
npm install           # dependencias JS de conveniencia
cd backend && uv sync # entorno Python con todas las dependencias
cd ..
```

### 2. Arrancar el shell desktop
```bash
npm run dev
# o equivalentemente:
npm run desktop
```

Tambien puedes lanzarlo directamente:
```bash
cd backend
uv run python scripts/desktop_app.py
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
- **Dos modelos soportados:** `Fast Conformer ES` (default, español) y `Multi-idioma (FastConformer)` (ingles).
- **Cambio de modelo en caliente:** cambiar entre modelos sin reiniciar, con fallback al anterior si falla.
- **Autostart:** opcion para iniciar con la sesion creando `.desktop` en `~/.config/autostart/`.
- **Exportacion de texto:** historial acumulado exportable a `.txt`.
- **Instancia unica:** solo un proceso puede controlar hotkey y microfono a la vez.

## Modelos soportados
| Modelo | Clave | Descripcion |
|--------|-------|-------------|
| Fast Conformer ES | `fastconformer_es` | `nvidia/stt_es_fastconformer_hybrid_large_pc` — default, español |
| Multi-idioma (FastConformer) | `parakeet_v3` | `nvidia/parakeet-tdt-0.6b-v3` — ingles |

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

## Flujo web legado (en proceso de retiro)

Si necesitas comparar contra el flujo anterior (React + Node + WebSocket):

```bash
npm run dev:web
```

Frontend: `http://localhost:5173`  
Backend: `http://127.0.0.1:8787`

> **Nota:** El flujo web se mantiene temporalmente para referencia de paridad funcional. El camino principal de ejecucion es el shell desktop PySide.

### Variables de entorno del backend web legado
- `PORT`: puerto HTTP. Default `8787`.
- `HOST`: host. Default `127.0.0.1`.
- `FRONTEND_ORIGIN`: CORS. Default `http://localhost:5173`.
- `GLOBAL_HOTKEY_ENABLED`: hotkey global en Linux. Default `true`.
- `NATIVE_TYPE_ENABLED`: dictado nativo. Default `true`.
- `NATIVE_TYPE_CMD`: comando de tipeo. Default `xdotool`.
- `ASR_MODEL_ID`: modelo ASR. Default `nvidia/stt_es_fastconformer_hybrid_large_pc`.
- `ASR_MAX_AUDIO_SEC`: limite de audio. Default `30`.

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
# Tests Python del backend (55 tests)
cd backend && ./.venv/bin/python -m unittest discover -s tests -t .

# Tests Node del backend legado
npm run test --workspace backend
```

## Estado de migracion a PySide

Todas las fases del plan de migracion estan implementadas y validadas:

- **Fase 0:** preparacion y congelamiento funcional ✅
- **Fase 1:** nucleo Python reutilizable (`AppConfig`, `ModelManager`, catalogo de modelos) ✅
- **Fase 2:** shell desktop (`QApplication`, instancia unica, bandeja, ventana de ajustes) ✅
- **Fase 3:** hotkey global y captura nativa de audio con `sounddevice` ✅
- **Fase 4:** precarga de modelo y cambio seguro entre Fast Conformer y Parakeet ✅
- **Fase 5:** dictado nativo con `xdotool` y deteccion de entornos incompatibles ✅
- **Fase 6:** autostart con `.desktop`, endurecimiento del arranque, `npm run desktop` como camino principal ✅
- **Fase 7:** instalacion local para Linux con `uv`, launcher, entrada de aplicaciones y desinstalacion limpia ✅

**Pendiente:** retiro definitivo del codigo web (React, Node, WebSocket) cuando la paridad funcional sea aceptada.
