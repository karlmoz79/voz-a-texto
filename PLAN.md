# Plan de Implementación: App Web de Voz a Texto en Tiempo Real (OpenAI/Whisper)

**Resumen**
Construir una app web que capture audio del micrófono, lo transmita en tiempo real a un backend, y este a su vez lo envíe al modelo en la nube (OpenAI Realtime con transcripción Whisper) para mostrar texto parcial y final en la UI con baja latencia.

**Objetivo**
Transcribir voz en tiempo real desde el navegador a texto, con resultados parciales y finales visibles para el usuario en segundos.

**Arquitectura (alto nivel)**
Frontend web capta micrófono y envía chunks PCM16 al backend vía WebSocket. El backend mantiene una sesión Realtime con OpenAI, retransmite audio, recibe eventos de transcripción (parciales/finales) y los envía al frontend. El frontend renderiza transcript y estado de conexión.

**Tech Stack**
- Frontend: React + TypeScript + Vite, Web Audio API.
- Backend: Node.js + Express + `ws` (WebSocket).
- Cloud STT: OpenAI Realtime API con `input_audio_transcription` (Whisper).

---

## Alcance y decisiones cerradas
- Plataforma: Web.
- Transcripción: Streaming en tiempo real con parciales.
- Proveedor: OpenAI (Realtime + Whisper).
- Audio: PCM16, mono, 24kHz.
- VAD: `server_vad` (detección de turnos en la nube).
- No se persiste audio por defecto; solo texto en memoria (opción de descarga local).

---

## APIs / Interfaces públicas

### Backend HTTP
1. `POST /api/realtime/session`
   - Crea sesión Realtime (o genera token efímero si aplica).
   - Respuesta:
     ```json
     { "wsUrl": "wss://<backend>/api/realtime/stream", "sessionId": "<id>" }
     ```

### Backend WebSocket (`/api/realtime/stream`)
Mensajes cliente → servidor:
- `start`:
  ```json
  { "type": "start", "config": { "language": "es", "vad": "server" } }
  ```
- `audio_chunk` (base64 PCM16 24kHz):
  ```json
  { "type": "audio_chunk", "audio": "<base64>" }
  ```
- `stop`:
  ```json
  { "type": "stop" }
  ```

Mensajes servidor → cliente:
- `partial_transcript`:
  ```json
  { "type": "partial_transcript", "text": "hola ..." }
  ```
- `final_transcript`:
  ```json
  { "type": "final_transcript", "text": "hola mundo" }
  ```
- `status` / `error`.

---

## Flujo de datos
1. Usuario da permiso de micrófono.
2. Frontend captura audio, re-muestrea a 24kHz PCM16, chunk 20ms (480 samples).
3. WebSocket frontend → backend con `audio_chunk`.
4. Backend abre WebSocket a OpenAI Realtime y envía chunks con `input_audio_buffer.append`.
5. OpenAI responde eventos de transcripción parcial y final.
6. Backend reenvía texto a frontend.
7. UI actualiza transcript en tiempo real.

---

## Manejo de errores y resiliencia
- Reconexión WS en frontend con backoff.
- Timeout de sesión: cerrar si 60s sin audio.
- Validaciones: tamaño de chunk, formato PCM16, tasa de muestreo.
- Errores de OpenAI mapeados a códigos amigables en UI.

---

## Seguridad
- API key de OpenAI solo en backend.
- CORS restringido al dominio del frontend.
- Rate limit por IP para WS.
- TLS obligatorio en producción.
- Logs sin audio.

---

## UI/UX (mínimo viable)
- Botón `Iniciar` / `Detener`.
- Indicador de estado (Conectando / Escuchando / Error).
- Área de transcript con parciales en gris y finales en negro.
- Selector opcional de idioma (por defecto `es`).

---

## Plan de implementación por fases

### Fase 1: Backend Realtime Bridge
- Crear servidor Node + Express + WS.
- Endpoint `POST /api/realtime/session`.
- Handler WS que:
  - Abre sesión con OpenAI Realtime.
  - Envía `session.update` (modalities, input_audio_format, transcription, VAD).
  - Proxy de eventos hacia el cliente.
- Logs y manejo de desconexiones.

### Fase 2: Frontend Captura de Audio
- UI básica (React).
- Captura con `getUserMedia`.
- Pipeline Web Audio:
  - `AudioContext` → `MediaStreamSource` → `AudioWorklet`/`ScriptProcessor`.
  - Resample a 24kHz PCM16.
  - Chunk 20ms y base64.
- WS a backend y render de transcript.

### Fase 3: Integración End-to-End
- Flujo completo: iniciar → hablar → ver texto.
- Ajustar VAD (`threshold`, `silence_duration_ms`) para español.
- Validar latencia objetivo (< 1.5s parcial).

### Fase 4: Calidad y endurecimiento
- Reconexión WS.
- Indicadores de estado.
- Opción de exportar transcript (descarga local).

---

## Casos de prueba
- Permiso micrófono denegado → UI muestra error.
- Conexión WS caída → reintento y mensaje.
- Audio inválido (muestras corruptas) → backend rechaza y alerta.
- Latencia: medir tiempos desde habla hasta parcial < 1.5s.
- Sesión inactiva > 60s → cierre y UI notificada.

---

## Suposiciones y defaults
- Uso de OpenAI Realtime API con transcripción Whisper.
- Idioma por defecto: `es`.
- No persistencia de datos en servidor.
- UI minimalista enfocada en funcionalidad.

