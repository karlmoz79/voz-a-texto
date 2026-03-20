# Voz a Texto en Tiempo Real Local

Aplicacion web para capturar audio del microfono y transcribirlo de forma local con NVIDIA NeMo. El flujo principal usa `nvidia/stt_es_fastconformer_hybrid_large_pc` como modelo por defecto, con soporte configurable para Parakeet mediante variables de entorno.

## Estructura
- `backend/`: servidor Node.js + WebSocket que coordina la sesion, el hotkey global y el proceso Python de transcripcion.
- `frontend/`: app React + Vite que controla el push-to-talk, el estado de captura y la exportacion del texto.
- `docs/superpowers/plans/`: planes de trabajo y seguimiento.

## Requisitos
- Node.js 18+
- Python 3.12+
- npm 8+
- `uv` para el entorno Python del backend
- `xdotool` en Linux si quieres dictado nativo

## Caracteristicas
- **Transcripcion local:** el audio se procesa en el equipo, sin enviar datos a servicios remotos.
- **Push-to-talk estricto:** el microfono solo se abre mientras mantienes presionado el boton o `Alt+I`.
- **Hotkey global con propiedad unica:** una sola pestana controla el atajo global para evitar dictados duplicados.
- **Dictado nativo opcional:** la transcripcion final se puede escribir en la ventana activa usando `xdotool`.
- **Exportacion de texto:** el historial acumulado se puede descargar como `.txt`.

## Instalacion
1. Instala dependencias JavaScript desde la raiz:
   ```bash
   npm install
   ```
2. Prepara el entorno Python del backend:
   ```bash
   cd backend
   uv sync
   cp .env.example .env
   cd ..
   ```
3. Ajusta `backend/.env` si quieres usar otro modelo o cambiar limites.

## Desarrollo
Levanta frontend y backend en paralelo:

```bash
npm run dev
```

Frontend: `http://localhost:5173`  
Backend: `http://127.0.0.1:8787`

## Variables de entorno del backend
- `PORT`: puerto HTTP del backend. Default `8787`.
- `HOST`: host del backend. Default `127.0.0.1`.
- `FRONTEND_ORIGIN`: origen permitido para CORS. Default `http://localhost:5173`.
- `GLOBAL_HOTKEY_ENABLED`: habilita el listener global `Alt+I` en Linux. Default `true`.
- `NATIVE_TYPE_ENABLED`: habilita dictado nativo. Default `true`.
- `NATIVE_TYPE_CMD`: comando para escribir en la ventana activa. Default `xdotool`.
- `ASR_MODEL_ID`: modelo ASR principal. Default `nvidia/stt_es_fastconformer_hybrid_large_pc`.
- `ASR_MAX_AUDIO_SEC`: maximo de audio por dictado antes de rechazarlo. Default `30`.

Alias de compatibilidad:
- `PARAKEET_MODEL_PATH`
- `PARAKEET_MAX_AUDIO_SEC`

## Modelos soportados
- Default: `nvidia/stt_es_fastconformer_hybrid_large_pc`
- Alternativa configurable: `nvidia/parakeet-tdt-0.6b-v3`

Ejemplo para usar Parakeet:

```bash
ASR_MODEL_ID=nvidia/parakeet-tdt-0.6b-v3
```

## Integracion nativa en Linux
1. Instala `xdotool`.
2. Deja `NATIVE_TYPE_ENABLED=true` en `backend/.env`.
3. Mantén la UI abierta.
4. Usa el checkbox "Dictado nativo" si quieres que el texto final se escriba en la ventana enfocada.

## Calidad
- Build frontend:
  ```bash
  npm run build --workspace frontend
  ```
- Tests backend:
  ```bash
  npm run test --workspace backend
  ```
- Tests frontend:
  ```bash
  npm run test --workspace frontend
  ```
