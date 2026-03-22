from dataclasses import dataclass

FASTCONFORMER_ES_KEY = "fastconformer_es"
WHISPER_SMALL_KEY = "whisper_small"
WHISPER_BASE_KEY = "whisper_base"
WHISPER_TINY_KEY = "whisper_tiny"
WHISPER_MEDIUM_KEY = "whisper_medium"
PARAKEET_V3_KEY = "parakeet_v3"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    key: str
    label: str
    model_id: str


MODEL_PROFILES = {
    FASTCONFORMER_ES_KEY: ModelProfile(
        key=FASTCONFORMER_ES_KEY,
        label="Fast Conformer (Solo Español • Rápido y Preciso • ~ 480 MB)",
        model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
    ),
    WHISPER_SMALL_KEY: ModelProfile(
        key=WHISPER_SMALL_KEY,
        label="Whisper Small (Multilenguaje • Equilibrado • ~ 244 MB)",
        model_id="small",
    ),
    WHISPER_BASE_KEY: ModelProfile(
        key=WHISPER_BASE_KEY,
        label="Whisper Base (Multilenguaje • Rápido • ~ 142 MB)",
        model_id="base",
    ),
    WHISPER_TINY_KEY: ModelProfile(
        key=WHISPER_TINY_KEY,
        label="Whisper Tiny (Multilenguaje • Muy Rápido • ~ 75 MB)",
        model_id="tiny",
    ),
    WHISPER_MEDIUM_KEY: ModelProfile(
        key=WHISPER_MEDIUM_KEY,
        label="Whisper Medium (Multilenguaje • Preciso • ~ 760 MB)",
        model_id="medium",
    ),
    PARAKEET_V3_KEY: ModelProfile(
        key=PARAKEET_V3_KEY,
        label="Parakeet V3 (Solo Inglés • Preciso • ~ 1.2 GB)",
        model_id="nvidia/parakeet-tdt-0.6b-v3",
    ),
}

DEFAULT_MODEL_KEY = FASTCONFORMER_ES_KEY


def normalize_model_key(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in MODEL_PROFILES:
            return normalized
    return DEFAULT_MODEL_KEY


def get_model_profile(value=None):
    return MODEL_PROFILES[normalize_model_key(value)]


def find_model_key_by_id(model_id):
    if not isinstance(model_id, str):
        return None

    normalized = model_id.strip()
    if not normalized:
        return None

    for key, profile in MODEL_PROFILES.items():
        if profile.model_id == normalized:
            return key

    return None
