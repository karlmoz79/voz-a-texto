# AGENTS.md - Voz a Texto en Tiempo Real Local

## Resumen del proyecto
- Objetivo: Aplicacion de escritorio local y privada de voz a texto, residente en bandeja del sistema con `PySide6`.
- Caracteristicas: Push-to-talk global, transcripcion offline, multiple modelos ASR (Fast Conformer ES, Whisper, Parakeet), exportacion de texto y dictado nativo en Linux con `xdotool`.
- Stack: nucleo Python reutilizable en `backend/voz_a_texto/` y shell desktop PySide en `backend/voz_a_texto/desktop/` con hotkey global, captura de audio local, precarga de modelo, autostart, tema premium e instalacion local.
- Version minima: Python 3.12+.

## Setup y desarrollo
- Entorno Python (usando `uv` y `pyproject.toml`): `cd backend && uv sync`
- Iniciar shell desktop: `npm run dev` (raiz) o `cd backend && uv run python scripts/desktop_app.py`
- Variables de entorno locales: `backend/.env` (opcional, la configuracion principal vive en `~/.config/voz-a-texto/config.json`).
- Dependencias Linux: `PySide6`, `sounddevice`, `pynput`; la captura nativa puede requerir PortAudio disponible en el sistema. `libxcb-cursor0` para Qt en Mint/Ubuntu/Debian. `xdotool` para dictado nativo.

## Calidad (obligatorio antes de finalizar)
- Tests Python backend: `cd backend && ./.venv/bin/python -m unittest discover -s tests -t .`

## Convenciones de codigo
- Lenguaje/estilo: Python 3 para todo el proyecto. Adherencia a una arquitectura limpia y modular.
- Mantener siempre la infraestructura Python controlada y empaquetada estrictamente gestionada bajo el ecosistema de resoluciones `uv`.
- Arquitectura: toda la logica de configuracion, ASR y desktop vive en `backend/voz_a_texto/`.
- `backend/voz_a_texto/desktop/` contiene: `QApplication`, bandeja del sistema, ventana de ajustes con tema premium (FramelessWindow), hotkey global con `pynput`, captura local de audio con `sounddevice`, `TranscriptStore`, `NativeTypingService`, `AutostartService`, theme module y coordinacion de estado del shell.
- Las dependencias deberan documentarse si son necesarias.

## Reglas de cambios
- No modificar: `node_modules/`, `.venv/` o carpetas temporales para modelos, archivos `.env` (donde haya configuraciones en local absolutas).
- Evitar: incluir rutas absolutas en repo o subir tokens accidentalmente.

## Seguridad y datos
- Nunca commitear archivos `.env` al menos que contengas variables inofensivas en un archivo `example`.
- Mascaras de datos sensibles si aplican. Validaciones y sanitizaciones obligatorias cuando se pase la terminal hacia procesos crudos como `xdotool`.

## Flujo de trabajo
- Commits: `feat/fix/chore` descriptivo.
- Definicion de terminado: la app PySide funciona sola, en segundo plano, con todas las caracteristicas (hotkey, dictado, precarga, autostart, instalacion local, tema premium) sin depender de ningun stack web.

## Monorepo
- Package principal: raiz con workspace `backend` de npm para scripts de conveniencia.
- Comandos: `npm run dev`, `npm run desktop:install`, `npm run desktop:uninstall`.
- Prestigio de documento: Este AGENTS.md dicta el rumbo.

## Referencias
- README: `./README.md`
- Arquitectura Central: `backend/voz_a_texto/`, `backend/voz_a_texto/desktop/`, `backend/scripts/desktop_app.py`, `backend/voz_a_texto/desktop/theme.py`.
- Modelos: `backend/voz_a_texto/models.py`
