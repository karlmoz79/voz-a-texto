# Voz a Texto en Tiempo Real (Web + OpenAI Realtime)

Una aplicación web que captura el audio del micrófono y lo transcribe en tiempo real usando OpenAI Realtime API. Además, incluye funcionalidades para pausar la transmisión, acumular bloques de audio y procesarlos bajo demanda, así como exportar la transcripción a un archivo de texto.

## Estructura
- `backend/`: puente WebSocket hacia OpenAI Realtime
- `frontend/`: app web (React + Vite)

## Requisitos
- Node.js 18+
- Una API key de OpenAI con acceso a Realtime (`gpt-4o-realtime-preview-2024-12-17` o similar)

## Características
- **Transmisión en tiempo real:** Comunicación directa mediante WebSockets hacia OpenAI con latencia mínima.
- **Pausa y Acumulación (Batching):** Opción de "Pausa" donde la aplicación sigue capturando el audio pero lo guarda en un buffer local sin transmitirlo; al dar clic a "Procesar", envía todo el bloque cargado para su interpretación completa.
- **Exportación de texto:** Opción nativa de descargar un archivo de extensión `.txt` con la transcripción completa lograda de las respuestas.
- **Selección de Idiomas:** Integrado selector que permite fijar el lenguaje para la instancia de OpenAI.

## Inicio rapido (recomendado)
```bash
npm install
cp backend/.env.example backend/.env
# Edita OPENAI_API_KEY en backend/.env
npm run dev
```

Abre `http://localhost:5173` (frontend) y el backend queda escuchando en `http://127.0.0.1:8787`. Utilizando `npm run dev` en el directorio principal se levantarán ambos entornos en simultáneo a través de `concurrently`.

## Ejecutar por separado
Backend:
```bash
cd backend
cp .env.example .env
# Edita OPENAI_API_KEY en backend/.env
npm install
npm run dev
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Notas
- El backend expone `POST /api/realtime/session` y WS en `/api/realtime/stream`.
- El frontend usa `fetch` relativo junto con proxy configurado en Vite en modo de desarrollo, así que asume que el backend está corriendo concurrentemente en el puerto adecuado. Si usas hosts distintos, ajusta la URL en `frontend/src/App.tsx` o en tu configuración de deployment.
- Si ves `EADDRINUSE`, hay puertos ocupados (`8787` o `5173`).
