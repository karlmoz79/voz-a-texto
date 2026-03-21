from dataclasses import dataclass
import threading


TARGET_SAMPLE_RATE = 16000
PCM16_BYTES_PER_SAMPLE = 2
DEFAULT_BLOCKSIZE = 1600


@dataclass(frozen=True, slots=True)
class AudioCaptureResult:
    audio_bytes: bytes
    too_long: bool = False
    error_message: str | None = None


class RecordingBuffer:
    def __init__(self, max_audio_sec, sample_rate=TARGET_SAMPLE_RATE):
        self.max_audio_sec = max_audio_sec
        self.sample_rate = sample_rate
        self.max_bytes = int(max_audio_sec * sample_rate * PCM16_BYTES_PER_SAMPLE)
        self.total_bytes = 0
        self.recording_too_long = False
        self._chunks = []

    def append(self, chunk):
        if self.recording_too_long or not chunk:
            return

        remaining_bytes = self.max_bytes - self.total_bytes
        if remaining_bytes <= 0:
            self.recording_too_long = True
            return

        if len(chunk) > remaining_bytes:
            self._chunks.append(chunk[:remaining_bytes])
            self.total_bytes += remaining_bytes
            self.recording_too_long = True
            return

        self._chunks.append(chunk)
        self.total_bytes += len(chunk)

    def consume(self):
        return b"".join(self._chunks)


class AudioCaptureService:
    def __init__(self, sample_rate=TARGET_SAMPLE_RATE, blocksize=DEFAULT_BLOCKSIZE):
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self._lock = threading.Lock()
        self._stream = None
        self._buffer = None
        self._last_error = None
        self._recording = False

    @property
    def is_recording(self):
        return self._recording

    def start_recording(self, max_audio_sec):
        if self._recording:
            return None

        import sounddevice as sd

        buffer = RecordingBuffer(max_audio_sec=max_audio_sec, sample_rate=self.sample_rate)
        self._buffer = buffer
        self._last_error = None

        def callback(indata, _frames, _time, status):
            with self._lock:
                if status and self._last_error is None:
                    self._last_error = str(status)
                if self._buffer is not None:
                    self._buffer.append(bytes(indata))

        try:
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.blocksize,
                callback=callback,
            )
            stream.start()
        except Exception as exc:
            self._stream = None
            self._buffer = None
            self._recording = False
            return f"No se pudo iniciar la captura de audio: {exc}"

        self._stream = stream
        self._recording = True
        return None

    def stop_recording(self):
        with self._lock:
            stream = self._stream
            buffer = self._buffer
            error_message = self._last_error
            self._stream = None
            self._buffer = None
            self._last_error = None
            self._recording = False

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        if buffer is None:
            return AudioCaptureResult(audio_bytes=b"", error_message=error_message)

        return AudioCaptureResult(
            audio_bytes=buffer.consume(),
            too_long=buffer.recording_too_long,
            error_message=error_message,
        )
