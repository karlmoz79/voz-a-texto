# AGENTS.md - Voz a Texto en Tiempo Real Local

## Resumen del proyecto
- Objetivo: App web que captura micrófono y transcribe de manera completamente local y privada usando el modelo STT Fast Conformer Hybrid Large PC de NVIDIA (local).
- Características Modulares: Captura de dictado con modo "Push-to-Talk" global vía escucha profunda del teclado (presionar Alt+I), transmisión y acumulación de buffers al WebSocket mientras el usuario dicta, modelo ASR ejecutado en subproceso en Python (Node -> Python child_process), transcripción offline del texto y exportación de archivos (.txt). Dictado nativo opcional simulando el teclado en Linux (`xdotool`).
- Stack: Backend Node.js (Express + ws) corriendo en paralelo al código de Python 3 (NeMo acelerado con PyTorch). Frontend compuesto en React + Vite + TypeScript.
- Versión mínima: Node.js 18+, Python 3.10+, npm 8+.

## Setup y desarrollo
- Instalar dependencias web JS: `npm install` (raíz). Se configuran espacios de trabajo (workspaces).
- Entorno nativo local en Python (usando la herramienta estricta `uv` e instanciando con `pyproject.toml`): `cd backend && uv sync` (Esto creará automáticamente el entorno virtual y resolverá las dependencias).
- Iniciar entorno local (servidor de UI y servidor Transcriptor): `npm run dev` (raíz - levanta backend y frontend mediante *concurrently*).
- Variables de entorno locales: copiar `backend/.env.example` o editar en directo `backend/.env`.

## Calidad (obligatorio antes de finalizar)
- Lint: `N/A`
- Typecheck: `N/A`
- Tests: `N/A`
- Build local (si aplica): `npm run build --workspace frontend`

## Convenciones de codigo
- Lenguaje/estilo: JS ESM en backend; TypeScript/React en frontend; Scripts de machine learning modulares e independientes en Python 3. Adherencia a una arquitectura limpia asincrónica y simplificada.
- Mantener siempre la infraestructura Python controlada y empaquetada estrictamente gestionada bajo el ecosistema de resoluciones `uv`.
- Arquitectura centralizada: frontend con UI de modo "Push-to-Talk" con control exclusivo a través de un websocket bidireccional, despachando chunks a la capa backend en Node.js, donde este levanta y controla su CLI de Python subyacente para inyectar flujos PCM decodificados en memoria (`stdin`) de manera paralela hasta que finaliza la petición con la transcripción devuelta (`stdout`).
- Las dependencias deberán documentarse si son necesarias.

## Reglas de cambios
- No modificar: `node_modules/`, `.venv/` o carpetas temporales para modelos, archivos `.env` (donde haya configuraciones en local absolutas).
- Evitar: incluir rutas absolutas en repo o subir tokens accidentalmente y modificar el flujo principal del Python subprocess sin la debida consideración.
- Migraciones: `N/A`

## Seguridad y datos
- Nunca commitear archivos `.env` al menos que contengas variables inofensivas en un archivo `example`.
- Máscaras de datos sensibles si aplican. Validaciones y sanitizaciones obligatorias cuando se pase la terminal hacia procesos crudos como `xdotool`.

## Flujo de trabajo
- Commits: `feat/fix/chore` descriptivo.
- Definicion de terminado: levantamiento sincrono del clúster vite + el motor de Node, subprocesos de Python emitiendo estados de JSON sin crasheos y dictado sobre inputs físicos en Linux garantizado usando keyups sin latencia desmedida. 

## Monorepo
- Package principal: codebase principal con workspaces `backend` y `frontend` nativos de npm. 
- Comandos ejecutables cruzados: `npm run <cmd> --workspace <nombre-proyecto>`
- Prestigio de documento: Éste AGENTS.md dicta el rumbo.

## Referencias
- README: `./README.md`
- PLAN: Documentos en `docs/superpowers/plans/`.
- Arquitectura Central: `backend/src/server.js`, `frontend/src/App.tsx`, `backend/scripts/transcribe.py`.
- CI/CD: `N/A`
