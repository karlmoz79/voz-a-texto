import base64
from dataclasses import replace
import os
import tempfile
import threading
import wave

from .models import find_model_key_by_id

MODEL_STATE_IDLE = "idle"
MODEL_STATE_LOADING = "loading"
MODEL_STATE_READY = "ready"
MODEL_STATE_ERROR = "error"


def normalize_transcription(transcription):
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


def is_model_downloaded(model_id):
    if model_id in ("tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"):
        repo_id = f"Systran/faster-whisper-{model_id}"
    else:
        repo_id = model_id
    
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    folder_name = "models--" + repo_id.replace("/", "--")
    folder_path = os.path.join(cache_dir, folder_name)
    
    return os.path.exists(folder_path)


def delete_model_cache(model_id):
    import shutil
    if model_id in ("tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"):
        repo_id = f"Systran/faster-whisper-{model_id}"
    else:
        repo_id = model_id
    
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    folder_name = "models--" + repo_id.replace("/", "--")
    folder_path = os.path.join(cache_dir, folder_name)
    
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        return True
    return False


def load_pretrained_model(model_id):
    if model_id in (
        "tiny",
        "base",
        "small",
        "medium",
        "large-v1",
        "large-v2",
        "large-v3",
    ):
        from faster_whisper import WhisperModel

        threads = os.cpu_count() or 4
        num_workers = min(2, threads)
        model = WhisperModel(
            model_id,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
            num_workers=num_workers,
        )

        def _warmup_whisper(wm):
            """Warmup del modelo con audio silencioso para reducir latencia inicial."""
            import numpy as np
            import tempfile
            import wave

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                # 1 segundo de audio silencioso a 16kHz
                silence = np.zeros(16000, dtype=np.float32)
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes((silence * 32767).astype(np.int16).tobytes())
                wm.transcribe(tmp_path, beam_size=1, vad_filter=True, language="es")
            except Exception:
                pass
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        _warmup_whisper(model)

        class FasterWhisperWrapper:
            def __init__(self, wm):
                self.wm = wm

            def transcribe(self, paths, **kwargs):
                results = []
                for path in paths:
                    segments, _ = self.wm.transcribe(
                        path, beam_size=1, condition_on_previous_text=False, vad_filter=True, **kwargs
                    )
                    text = " ".join(
                        [segment.text.strip() for segment in segments]
                    ).strip()
                    results.append(text)
                return results

        return FasterWhisperWrapper(model)

    import torch
    from nemo.collections.asr.models import ASRModel

    torch.set_num_threads(os.cpu_count() or 4)
    torch.set_grad_enabled(False)
    model = ASRModel.from_pretrained(model_id)
    model.eval()

    if not torch.cuda.is_available():
        pass  # threads ya configurados arriba

    return model


class ModelManager:
    def __init__(self, runtime_config, model_loader=None):
        self.runtime_config = runtime_config
        self._model_loader = model_loader or load_pretrained_model
        self._model = None
        self._loaded_model_id = None
        self._lock = threading.RLock()
        self.state = MODEL_STATE_IDLE
        self.last_error = None

    @property
    def loaded_model_id(self):
        with self._lock:
            return self._loaded_model_id

    def has_loaded_model(self):
        with self._lock:
            return self._model is not None

    def load_active_model(self):
        return self.switch_active_model(self.runtime_config.model_id)

    def load_model(self, model_id):
        return self.switch_active_model(model_id)

    def switch_active_model(self, model_id):
        target_model_id = self._normalize_model_id(model_id)

        with self._lock:
            if self._model is not None and self._loaded_model_id == target_model_id:
                self.state = MODEL_STATE_READY
                self.last_error = None
                self._update_runtime_config(target_model_id)
                return self._model

            self.state = MODEL_STATE_LOADING
            self.last_error = None

        try:
            model = self._model_loader(target_model_id)
        except Exception as exc:
            with self._lock:
                self.state = MODEL_STATE_ERROR
                self.last_error = str(exc)
            raise

        with self._lock:
            self._model = model
            self._loaded_model_id = target_model_id
            self._update_runtime_config(target_model_id)
            self.state = MODEL_STATE_READY
            self.last_error = None
            return self._model

    def unload_model(self):
        with self._lock:
            self._model = None
            self._loaded_model_id = None
            self.state = MODEL_STATE_IDLE
            self.last_error = None

    def transcribe_base64(self, audio_base64, model_id=None):
        audio_bytes = base64.b64decode(audio_base64)
        return self.transcribe_bytes(audio_bytes, model_id=model_id)

    def transcribe_bytes(self, audio_bytes, model_id=None, language=None):
        if not audio_bytes:
            return ""

        model = self.load_model(model_id) if model_id else self.load_active_model()
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)

            kwargs = {}
            if language and language != "auto":
                kwargs["language"] = language

            try:
                transcription = model.transcribe([temp_path], **kwargs)
            except TypeError:
                # Fallback for models like NeMo that do not accept kwargs
                transcription = model.transcribe([temp_path])
                
            return normalize_transcription(transcription)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _normalize_model_id(self, model_id):
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Model ID vacio")
        return model_id.strip()

    def _update_runtime_config(self, model_id):
        resolved_model_key = find_model_key_by_id(model_id)
        if resolved_model_key:
            self.runtime_config = replace(
                self.runtime_config,
                active_model=resolved_model_key,
                model_id=model_id,
            )
