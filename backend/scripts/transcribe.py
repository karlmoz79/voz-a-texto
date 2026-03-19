#!/usr/bin/env python3
import sys
import json
import base64
import numpy as np
import tempfile
import os
import soundfile as sf
import onnxruntime as ort
from nemo.collections.asr.models import ASRModel

import torch

class ParakeetTranscriber:
    def __init__(self, model_name="nvidia/parakeet-tdt-0.6b-v3"):
        # Esto descargará el modelo automáticamente si no existe y luego lo mantendrá en caché
        self.model = ASRModel.from_pretrained(model_name)
        self.model.eval()
        # Optimizar para CPU
        if not torch.cuda.is_available():
            torch.set_num_threads(os.cpu_count() or 4)
            torch.set_grad_enabled(False)
    
    def transcribe(self, audio_base64):
        audio_data = base64.b64decode(audio_base64)
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_np.astype(np.float32) / 32768.0
        
        # Guardar en archivo temporal temporal ya que NeMo transcribe() espera rutas de archivos
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            # Exportar un wav a 16kHz
            sf.write(temp_path, audio_float, samplerate=16000)
            
            # NeMo devuelve una tupla dependiendo de la versión
            transcription = self.model.transcribe([temp_path])
            
            if isinstance(transcription, tuple):
                transcription = transcription[0]
            
            if isinstance(transcription, list) and len(transcription) > 0:
                result = transcription[0]
                if hasattr(result, 'text'):
                    return result.text
                return str(result)
            
            if hasattr(transcription, 'text'):
                return transcription.text
            return str(transcription)
        finally:
            # Eliminar archivo de audio temporal
            if os.path.exists(temp_path):
                os.remove(temp_path)

def main():
    print(json.dumps({"type": "status", "state": "Cargando modelo. Puede tomar unos minutos si es la primera vez..."}), flush=True)
    try:
        # Aquí el usuario puede saber si ya lo descargó por el log
        model_name = os.getenv("PARAKEET_MODEL_PATH", "nvidia/parakeet-tdt-0.6b-v3")
        transcriber = ParakeetTranscriber(model_name=model_name)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to load model: {e}"}), flush=True)
        sys.exit(1)

    # Let the parent process know we are ready
    print(json.dumps({"type": "status", "state": "ready"}), flush=True)

    while True:
        line = sys.stdin.readline()
        if not line: # EOF reached
            break
        
        line = line.strip()
        if not line:
            continue
            
        try:
            msg = json.loads(line)
            if msg.get("type") == "transcribe":
                audio_data = msg.get("audio", "")
                text = transcriber.transcribe(audio_data)
                result = {"type": "transcript", "text": text}
                print(json.dumps(result), flush=True)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"Error transcribiendo: {str(e)}"}), flush=True)

if __name__ == "__main__":
    main()
