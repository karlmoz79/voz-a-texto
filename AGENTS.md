# AGENTS.md - VoxFlow: Voz a Texto en Tiempo Real Local

## Resumen del proyecto
- Objetivo: Aplicación de escritorio local y privada de voz a texto (**VoxFlow**), residente en bandeja del sistema con `PySide6`.
- Características: Push-to-talk global, transcripción offline, múltiples modelos ASR (Fast Conformer ES, Whisper, Parakeet), exportación de texto y dictado nativo en Linux con `xdotool`.
- Stack: núcleo Python reutilizable en `backend/voz_a_texto/` y shell desktop PySide en `backend/voz_a_texto/desktop/` con hotkey global, captura de audio local, precarga de modelo, autostart, tema premium e instalación local.
- Versión mínima: Python 3.12+.

## Setup y desarrollo
- Entorno Python (usando `uv` y `pyproject.toml`): `cd backend && uv sync`
- Iniciar shell desktop: `npm run dev` (raíz) o `cd backend && uv run python scripts/desktop_app.py`
- Variables de entorno locales: `backend/.env` (opcional, la configuración principal vive en `~/.config/vox-flow/config.json`).
- Dependencias Linux: `PySide6`, `sounddevice`, `pynput`; la captura nativa puede requerir PortAudio disponible en el sistema. `libxcb-cursor0` para Qt en Mint/Ubuntu/Debian. `xdotool` para dictado nativo.

## Calidad (obligatorio antes de finalizar)
- Tests Python backend: `cd backend && ./.venv/bin/python -m unittest discover -s tests -t .`

## Convenciones de código
- Lenguaje/estilo: Python 3 para todo el proyecto. Adherencia a una arquitectura limpia y modular.
- Mantener siempre la infraestructura Python controlada y empaquetada estrictamente gestionada bajo el ecosistema de resoluciones `uv`.
- Branding: Siempre usar `APP_DISPLAY_NAME` (VoxFlow) y `APP_SLUG` (vox-flow) desde `voz_a_texto.desktop.paths` en lugar de strings hardcoded.
- Arquitectura: toda la lógica de configuración, ASR y desktop vive en `backend/voz_a_texto/`.
- `backend/voz_a_texto/desktop/` contiene: `QApplication`, bandeja del sistema, ventana de ajustes con tema premium (FramelessWindow), hotkey global con `pynput`, captura local de audio con `sounddevice`, `TranscriptStore`, `NativeTypingService`, `AutostartService`, theme module y coordinación de estado del shell.
- Las dependencias deberán documentarse si son necesarias.

## Reglas de cambios
- No modificar: `node_modules/`, `.venv/` o carpetas temporales para modelos, archivos `.env`.
- Evitar: incluir rutas absolutas en repo o subir tokens accidentalmente.

## Seguridad y datos
- Nunca commitear archivos `.env` al menos que contengas variables inofensivas en un archivo `example`.
- Máscaras de datos sensibles si aplican. Validaciones y sanitizaciones obligatorias cuando se pase la terminal hacia procesos crudos como `xdotool`.

## Flujo de trabajo
- Commits: `feat/fix/chore` descriptivo.
- Definición de terminado: la app PySide funciona sola, en segundo plano, con todas las características (hotkey, dictado, precarga, autostart, instalación local, tema premium) sin depender de ningún stack web.

## Monorepo
- Package principal: raíz con workspace `backend` de npm para scripts de conveniencia.
- Comandos: `npm run dev`, `npm run desktop:install`, `npm run desktop:uninstall`.
- Prestigio de documento: Este AGENTS.md dicta el rumbo.

## Referencias
- README: `./README.md`
- Arquitectura Central: `backend/voz_a_texto/`, `backend/voz_a_texto/desktop/`, `backend/scripts/desktop_app.py`, `backend/voz_a_texto/desktop/theme.py`.
- Modelos: `backend/voz_a_texto/models.py`
- Rutas y Branding: `backend/voz_a_texto/desktop/paths.py`
