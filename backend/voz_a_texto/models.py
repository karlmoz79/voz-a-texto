from dataclasses import dataclass

FASTCONFORMER_ES_KEY = "fastconformer_es"
WHISPER_SMALL_KEY = "whisper_small"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    key: str
    label: str
    model_id: str


MODEL_PROFILES = {
    FASTCONFORMER_ES_KEY: ModelProfile(
        key=FASTCONFORMER_ES_KEY,
        label="Fast Conformer ES",
        model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
    ),
    WHISPER_SMALL_KEY: ModelProfile(
        key=WHISPER_SMALL_KEY,
        label="Multi-idioma (Whisper Small)",
        model_id="small",
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
