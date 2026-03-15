# AGENTS.md - Voz a Texto en Tiempo Real

## Resumen del proyecto
- Objetivo: App web que captura micrófono y transcribe en tiempo real usando Gemini Live (BidiGenerateContent).
- Características Modulares: Transmisión en tiempo real al WebSocket, finalización de stream con "Procesar" (commit) y exportación local de archivos con transcripción (.txt). Dictado nativo opcional en Linux.
- Stack: Backend Node.js (Express + ws) y Frontend React + Vite + TypeScript.
- Versión mínima: Node.js 18+, npm 8+.

## Setup y desarrollo
- Instalar dependencias: `npm install` (raíz). Se configuran espacios de trabajo (workspaces).
- Iniciar entorno local: `npm run dev` (raíz - levanta backend y frontend mediante *concurrently*) o comandos separados en workspaces: `npm run dev --workspace backend` y `npm run dev --workspace frontend`.
- Variables de entorno: `backend/.env` (ver `backend/.env.example`).

## Calidad (obligatorio antes de finalizar)
- Lint: `N/A`
- Typecheck: `N/A`
- Tests: `N/A`
- Build local (si aplica): `npm run build --workspace frontend`

## Convenciones de codigo
- Lenguaje/estilo: JS ESM en backend; TypeScript/React en frontend; mantener código simple y explícito, respetando arquitecturas funcionales y de hooks en React.
- Arquitectura: puente WebSocket en backend controlando flujos de Gemini, ratelimits, cola de audio hasta `setupComplete`, y dictado nativo; Frontend con UI minimalista que captura audio PCM16 a 16kHz usando AudioContext + AudioWorklets, resampleo y chunks base64.
- Evitar: incluir secretos, cambiar APIs sin actualizar la documentación pertinente como `README.md`/`AGENTS.md`.

## Reglas de cambios
- No modificar: `node_modules/`, archivos `.env` con secretos.
- Migraciones: `N/A`
- Dependencias nuevas: justificar necesidad y mantener mínimo.

## Seguridad y datos
- Nunca commitear secretos (`.env`, llaves, tokens).
- Mascaras de datos sensibles en logs.
- Revisar permisos y validaciones de entrada/salida (especialmente controlando los bytes y chunks de audio con conversor a base64).

## Flujo de trabajo
- Commits: `feat/fix/chore` descriptivo.
- PR: describir cambios y pasos de prueba.
- Definicion de terminado: servidores levantan y flujo de transcripción funciona (incluyendo el envío al procesar de chunks guardados); cambios documentados.

## Monorepo (si aplica)
- Package principal: root con workspaces `backend` y `frontend`. Soporta rutinas completas mediamente `concurrently`.
- Comandos por paquete: utilizable `npm run <cmd> --workspace <nombre-proyecto>`
- Regla de precedencia: AGENTS.md de la raíz.

## Referencias
- README: `./README.md`
- PLAN: `./PLAN.md` (Esquema originario del alcance)
- Arquitectura Central: `backend/src/server.js`, `frontend/src/App.tsx`, `frontend/src/audio-worklet.ts`
- CI/CD: `N/A`
