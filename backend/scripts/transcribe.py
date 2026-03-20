#!/usr/bin/env python3
import base64
import json
import os
import sys
import tempfile
import wave

import torch
from nemo.collections.asr.models import ASRModel

DEFAULT_ASR_MODEL_ID = "nvidia/stt_es_fastconformer_hybrid_large_pc"


def resolve_model_id():
    current_model_id = os.getenv("ASR_MODEL_ID", "").strip()
    legacy_model_id = os.getenv("PARAKEET_MODEL_PATH", "").strip()
    return current_model_id or legacy_model_id or DEFAULT_ASR_MODEL_ID


class LocalTranscriber:
    def __init__(self, model_name=DEFAULT_ASR_MODEL_ID):
        self.model = ASRModel.from_pretrained(model_name)
        self.model.eval()

        if not torch.cuda.is_available():
            torch.set_num_threads(os.cpu_count() or 4)
            torch.set_grad_enabled(False)

    def transcribe(self, audio_base64):
        audio_bytes = base64.b64decode(audio_base64)
        if not audio_bytes:
            return ""

        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)

            transcription = self.model.transcribe([temp_path])

            if isinstance(transcription, tuple):
                transcription = transcription[0]

            if isinstance(transcription, list) and transcription:
                result = transcription[0]
                if hasattr(result, "text"):
                    return result.text
                return str(result)

            if hasattr(transcription, "text"):
                return transcription.text
            return str(transcription)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def main():
    print(json.dumps({"type": "status", "state": "loading_model"}), flush=True)

    try:
        transcriber = LocalTranscriber(model_name=resolve_model_id())
    except Exception as exc:
        print(json.dumps({"type": "error", "message": f"Failed to load model: {exc}"}), flush=True)
        sys.exit(1)

    print(json.dumps({"type": "status", "state": "ready"}), flush=True)

    while True:
        line = sys.stdin.readline()
        if not line:
            break

        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            if msg.get("type") != "transcribe":
                continue

            text = transcriber.transcribe(msg.get("audio", ""))
            print(json.dumps({"type": "transcript", "text": text}), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as exc:
            print(json.dumps({"type": "error", "message": f"Error transcribiendo: {exc}"}), flush=True)


if __name__ == "__main__":
    main()
