# Voz a Texto en Tiempo Real (Web + Gemini Live)

Una aplicación web que captura el audio del micrófono y lo transcribe en tiempo real usando Gemini Live. Además, incluye funcionalidades para pausar la transmisión, acumular bloques de audio y procesarlos bajo demanda, así como exportar la transcripción a un archivo de texto.

## Estructura
- `backend/`: puente WebSocket hacia Gemini Live (BidiGenerateContent)
- `frontend/`: app web (React + Vite)

## Requisitos
- Node.js 18+
- npm 8+
- Una API key de Gemini con acceso a Gemini Live (BidiGenerateContent)
- (Opcional) `xdotool` en Linux para dictado nativo

## Características
- **Transmisión en tiempo real:** Comunicación directa mediante WebSockets hacia Gemini con latencia mínima.
- **Finalización manual:** Botón "Procesar" para detener el micrófono y cerrar el stream (commit) para obtener el cierre de la transcripción.
- **Exportación de texto:** Opción nativa de descargar un archivo de extensión `.txt` con la transcripción completa lograda de las respuestas.
- **Selección de Idiomas:** Selector en la UI (actualmente no modifica la configuración de Gemini).
- **Dictado nativo (Linux):** Envía la transcripción a la ventana activa usando `xdotool`.

## Inicio rapido (recomendado)
```bash
npm install
cp backend/.env.example backend/.env
# Edita GEMINI_API_KEY en backend/.env
npm run dev
```

Abre `http://localhost:5173` (frontend) y el backend queda escuchando en `http://127.0.0.1:8787` (por defecto, configurable con `PORT` en `backend/.env`). Utilizando `npm run dev` en el directorio principal se levantarán ambos entornos en simultáneo a través de `concurrently`.

## Variables de entorno (backend)
- `GEMINI_API_KEY`: requerido.
- `PORT`: puerto del backend (default `8787`).
- `HOST`: host del backend (default `127.0.0.1`).
- `FRONTEND_ORIGIN`: origen permitido para CORS (default `http://localhost:5173`).
- `NATIVE_TYPE_ENABLED`: habilita dictado nativo (default `false`).
- `NATIVE_TYPE_CMD`: comando para dictado nativo (default `xdotool`).

## Ejecutar por separado
Backend:
```bash
cd backend
cp .env.example .env
# Edita GEMINI_API_KEY en backend/.env
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
- El backend expone `GET /health`, `GET /api/models`, `POST /api/realtime/session`, WS en `/api/realtime/stream` y `POST /api/native/type`.
- El audio se envía como PCM16 a 16kHz en chunks base64 (20ms).
- El frontend usa `fetch` relativo junto con proxy configurado en Vite en modo de desarrollo, así que asume que el backend está corriendo concurrentemente en el puerto adecuado. Si usas hosts distintos, ajusta la URL en `frontend/src/App.tsx` o en tu configuración de deployment.
- Si ves `EADDRINUSE`, hay puertos ocupados (`8787` o `5173`).

## Integración nativa (Linux)
Opcionalmente puedes enviar la transcripción a la ventana activa (estilo dictado). Requiere `xdotool` y habilitar la opción en el backend.

Pasos:
1. Instala `xdotool` con tu gestor de paquetes.
2. En `backend/.env`, configura `NATIVE_TYPE_ENABLED=true`.
3. Inicia el proyecto y activa el toggle "Dictado nativo" en la UI.
4. Enfoca la aplicación destino y empieza a dictar.
