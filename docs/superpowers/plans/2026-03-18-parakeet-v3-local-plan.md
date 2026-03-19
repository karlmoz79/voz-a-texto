# Plan de Implementación: Transcripción Local con ParaKeet V3

**Fecha:** 2026-03-18
**Goal:** Reemplazar Gemini Live por ParaKeet V3 local con modo push-to-talk (Alt+I = grabar, soltar = procesar + dictate)

**Architecture:** Backend Node.js lanza proceso Python con ONNX Runtime CPU ejecutando ParaKeet TDT v3. Frontend captura audio en keydown/keyup de Alt+I y recibe transcripción para enviar a ventana activa.

**Tech Stack:** Node.js, Python 3.10+, ONNX Runtime CPU, NVIDIA ParaKeet TDT 0.6B v3, xdotool

---

## Estructura de Archivos

```
backend/
├── src/
│   └── server.js           # MODIFICAR: quitar Gemini, usar Python process
├── scripts/
│   └── transcribe.py       # NUEVO: wrapper Python para ParaKeet
├── venv/                    # NUEVO: venv Python
├── requirements.txt         # NUEVO: dependencias Python
└── .env                    # MODIFICAR: quitar GEMINI_API_KEY

frontend/src/
└── App.tsx                 # MODIFICAR: push-to-talk logic
```

---

## Tarea 1: Setup Python (venv + requirements)

**Archivos:**
- Crear: `backend/requirements.txt`
- Crear: `backend/scripts/__init__.py`

- [ ] **Paso 1: Crear requirements.txt**

```txt
onnxruntime>=1.17.0
nemo-toolkit[asr]>=2.3.0
torch>=2.0.0
numpy<2.0
```

- [ ] **Paso 2: Crear scripts/__init__.py vacío**

```python
# Placeholder for backend/scripts module
```

- [ ] **Paso 3: Crear venv e instalar dependencias**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Tarea 2: Crear transcribe.py (mock)

**Archivos:**
- Crear: `backend/scripts/transcribe.py`

- [ ] **Paso 1: Crear transcribe.py con mock**

```python
#!/usr/bin/env python3
import sys
import json
import time

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        
        try:
            msg = json.loads(line)
            if msg.get("type") == "transcribe":
                audio_data = msg.get("audio", "")
                time.sleep(2)  # Simula procesamiento
                result = {"type": "transcript", "text": f"Transcripcion mock: {len(audio_data)} bytes"}
                print(json.dumps(result), flush=True)
        except json.JSONDecodeError:
            pass

if __name__ == "__main__":
    main()
```

- [ ] **Paso 2: Hacer ejecutable y probar**

```bash
chmod +x backend/scripts/transcribe.py
echo '{"type": "transcribe", "audio": "test"}' | python3 backend/scripts/transcribe.py
```

---

## Tarea 3: Modificar server.js - Quitar Gemini

**Archivos:**
- Modificar: `backend/src/server.js`

- [ ] **Paso 1: Agregar imports para child_process**

```javascript
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import path from "path";
```

- [ ] **Paso 2: Agregar configuración de Python**

```javascript
const PYTHON_VENV_PATH = path.join(process.cwd(), "venv", "bin", "python3");
const TRANSCRIBE_SCRIPT = path.join(process.cwd(), "scripts", "transcribe.py");
```

- [ ] **Paso 3: Reemplazar función startGemini por spawnPython**

Eliminar código de Gemini (WebSocket a generativelanguage.googleapis.com, manejo de serverContent/inputTranscription). Reemplazar por:

```javascript
let pythonProcess = null;

const spawnPython = () => {
  if (pythonProcess && pythonProcess.exitCode === null) return;
  
  pythonProcess = spawn(PYTHON_VENV_PATH, [TRANSCRIBE_SCRIPT], {
    stdio: ["pipe", "pipe", "pipe"]
  });
  
  pythonProcess.stdout.on("data", (data) => {
    try {
      const msg = JSON.parse(data.toString());
      if (msg.type === "transcript") {
        sendToClient({ type: "final_transcript", text: msg.text });
      }
    } catch (e) {}
  });
  
  pythonProcess.on("error", (err) => {
    sendToClient({ type: "error", message: "Python process error: " + err.message });
  });
};
```

- [ ] **Paso 4: Eliminar GEMINI_API_KEY checks y endpoint /api/models**

---

## Tarea 4: Modificar server.js - Mensajes WebSocket

**Archivos:**
- Modificar: `backend/src/server.js` (clientWs.on("message"))

- [ ] **Paso 1: Nuevos mensajes**

```javascript
if (msg.type === "start_recording") {
  audioBuffer = [];
  spawnPython();
  sendToClient({ type: "status", state: "recording" });
}

if (msg.type === "audio_chunk") {
  if (pythonProcess?.stdin?.writable) {
    pythonProcess.stdin.write(JSON.stringify({type: "transcribe", audio: msg.audio}) + "\n");
    pythonProcess.stdin.flush();
  }
}

if (msg.type === "stop_and_transcribe") {
  sendToClient({ type: "status", state: "processing" });
}
```

- [ ] **Paso 2: Eliminar mensajes obsoletos de Gemini**

Eliminar: `start`, `commit`, `audio_chunk` ( old ), `stop`

---

## Tarea 5: Modificar App.tsx - Push-to-Talk

**Archivos:**
- Modificar: `frontend/src/App.tsx`

- [ ] **Paso 1: Reemplazar handleKeyDown para push-to-talk**

```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.altKey && e.key.toLowerCase() === "i" && !e.repeat) {
      e.preventDefault();
      startRecording(); // keydown: iniciar grabación
    }
  };
  const handleKeyUp = (e: KeyboardEvent) => {
    if (e.altKey && e.key.toLowerCase() === "i") {
      e.preventDefault();
      stopAndTranscribe(); // keyup: detener y procesar
    }
  };
  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
  return () => {
    window.removeEventListener("keydown", handleKeyDown);
    window.removeEventListener("keyup", handleKeyUp);
  };
}, []);
```

- [ ] **Paso 2: Crear startRecording y stopAndTranscribe**

```tsx
const startRecording = async () => {
  if (wsRef.current) return;
  setStatus("Grabando...");
  // Iniciar WebSocket, enviar start_recording
};

const stopAndTranscribe = () => {
  workletNodeRef.current?.disconnect();
  ws.send(JSON.stringify({ type: "stop_and_transcribe" }));
  setStatus("Procesando...");
};
```

- [ ] **Paso 3: Simplificar stopSession** - Solo cerrar WebSocket

- [ ] **Paso 4: Simplificar manejo de WebSocket** - Mantener solo `final_transcript`

- [ ] **Paso 5: Eliminar código obsoleto**
- Auto-commit por silencio
- `speech_started`, `partial_transcript`
- `restartInFlightRef`, `autoCommitInFlightRef`

---

## Tarea 6: Actualizar .env y README

**Archivos:**
- Modificar: `backend/.env`
- Modificar: `README.md`

- [ ] **Paso 1: Actualizar .env**

```env
# ELIMINADO
# GEMINI_API_KEY=...

# AÑADIDO
PARAKEET_MODEL_PATH=./models/parakeet-tdt-0.6b-v3
PARAKEET_MAX_AUDIO_SEC=30
```

- [ ] **Paso 2: Actualizar README.md**

Documentar: instalación Python, modelo ParaKeet, modo push-to-talk

---

## Tarea 7: Integrar ParaKeet real en transcribe.py

**Archivos:**
- Modificar: `backend/scripts/transcribe.py`

- [ ] **Paso 1: Implementar carga de modelo**

```python
import onnxruntime as ort
from nemo.collections.asr.models import EncDecCTCModelBPE

class ParakeetTranscriber:
    def __init__(self, model_name="nvidia/parakeet-tdt-0.6b-v3"):
        self.model = EncDecCTCModelBPE.from_pretrained(model_name)
        self.model.eval()
    
    def transcribe(self, audio_base64):
        import base64
        import numpy as np
        audio_data = base64.b64decode(audio_base64)
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_np.astype(np.float32) / 32768.0
        transcription = self.model.transcribe([audio_float])
        return transcription[0]
```

---

## Tarea 8: Testing End-to-End

- [ ] Probar sin Python (mock) - UI cambia a "Grabando"/"Procesando"
- [ ] Probar con Python mock - recibe transcripción
- [ ] Probar con ParaKeet real - primera ejecución descarga modelo (~2GB)
- [ ] Verificar dictate en otra ventana - Alt+I → hablar → soltar → texto aparece

---

## Resumen de Cambios

| Archivo | Acción |
|---------|--------|
| `backend/requirements.txt` | Crear |
| `backend/scripts/__init__.py` | Crear |
| `backend/scripts/transcribe.py` | Crear |
| `backend/src/server.js` | Reescribir |
| `backend/.env` | Modificar |
| `frontend/src/App.tsx` | Reescribir parcialmente |
| `README.md` | Actualizar |
