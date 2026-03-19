# Voz a Texto en Tiempo Real Local (Fast Conformer Hybrid Large)

Una aplicación web que captura el audio del micrófono y lo transcribe localmente con el modelo `nvidia/stt_es_fastconformer_hybrid_large_pc`, activado mediante un sistema de "Push-to-Talk Global". La transcripción resultante se puede enviar de manera automática a la ventana activa simulando un tipeo nativo.

## Estructura
- `backend/`: Node.js WebSocket server que lanza a un proceso de Python (`transcribe.py`) el cual ejecuta localmente ParaKeet.
- `frontend/`: App web construida sobre React + Vite en TypeScript, responsable del frontend y del control Push-to-Talk.

## Requisitos
- Node.js 18+
- Python 3.10+
- npm 8+
- (Opcional) `xdotool` en Linux para dictado nativo

## Características
- **Transcripción Local:** Transcripción ejecutada enteramente de forma local y offline acelerada mediante PyTorch optimizado (o ONNX Runtime).
- **Push-to-Talk Global:** Gracias a la escucha de teclado de bajo nivel (`pynput`), simplemente mantén presionado `Alt+I` desde **cualquier ventana** de tu sistema operativo para grabar. Al soltar, el audio se procesa y la transcripción se envía de vuelta.
- **Dictado Nativo (Linux):** Envía la transcripción directamente donde esté tu cursor usando `xdotool`.
- **Exportación de texto:** Opción de descargar un archivo `.txt` con el historial de la transcripción.

## Instalación

1. Clona el proyecto y ve al directorio principal.
2. Instala dependencias del marco de trabajo:
   ```bash
   npm install
   ```
3. Instala las dependencias del backend y configura el entorno Python siguiendo la arquitectura `uv` automatizada:
   ```bash
   cd backend
   uv sync
   cp .env.example .env
   # Asegúrate de verificar/colocar configuraciones dentro de .env
   cd ..
   ```

## Inicio rapido

Utilizando `npm run dev` en el directorio principal se levantarán ambos entornos en simultáneo a través de `concurrently`:
```bash
npm run dev
```

Abre `http://localhost:5173` (frontend). El backend quedará escuchando en `http://127.0.0.1:8787`.

**Nota sobre la primera vez:** La primera vez que presiones para hablar, o cuando se levante el servidor de Python, descargará el modelo (~2GB) desde Hugging Face usando NeMo toolkit, por lo que tardará unos instantes antes de estar "listo".

## Variables de entorno (backend)
- `PORT`: puerto del backend (default `8787`).
- `HOST`: host del backend (default `127.0.0.1`).
- `FRONTEND_ORIGIN`: origen permitido para CORS (default `http://localhost:5173`).
- `NATIVE_TYPE_ENABLED`: habilita dictado nativo (default `true`).
- `NATIVE_TYPE_CMD`: comando para dictado nativo (default `xdotool`).
- `PARAKEET_MODEL_PATH`: ID del repositorio alojado en Hugging Face del modelo ASR (default `nvidia/stt_es_fastconformer_hybrid_large_pc`).
- `PARAKEET_MAX_AUDIO_SEC`: Máxima duración de audio procesable en segundos por chunk (default `30`).

## Integración nativa (Linux)
Opcionalmente puedes enviar la transcripción a la ventana activa (estilo dictado nativo) desde cualquier lugar de tu escritorio de Linux. El backend intercepta de fondo la señal de teclado usando `pynput` y se comunica con el cliente de React.

1. Instala `xdotool` con tu gestor de paquetes (ej. `sudo apt install xdotool`).
2. Verifica que `NATIVE_TYPE_ENABLED=true` esté en el `.env` (backend).
3. Activa la casilla "Dictado nativo" en la UI web y mantenla corriendo. *(Nota: Si desactivas esta casilla, el atajo global `Alt+I` será completamente ignorado en segundo plano).*
4. Mueve tu ratón y enfoca cualquier caja de texto nativa (ej. el Bloc de Notas, VSCode, Telegram o Word).
5. Mantén pulsadas las teclas `Alt+I`. Habla al micrófono y finalmente suelta las teclas. Lo que hayas dicho ingresará automáticamente tipeado como por arte de magia bajo tu cursor sin necesitar jamás interactuar visualmente con el navegador.
