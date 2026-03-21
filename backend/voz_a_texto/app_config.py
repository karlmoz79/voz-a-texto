from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from .models import find_model_key_by_id, get_model_profile, normalize_model_key

APP_CONFIG_DIRNAME = "voz-a-texto"
CONFIG_FILENAME = "config.json"
DEFAULT_MAX_AUDIO_SEC = 30
DEFAULT_HOTKEY = "Ctrl+Space"


def read_non_empty_string(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def read_positive_int(value, fallback):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def read_bool(value, fallback):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


@dataclass(frozen=True, slots=True)
class AppConfig:
    active_model: str = normalize_model_key(None)
    max_audio_sec: int = DEFAULT_MAX_AUDIO_SEC
    native_typing_enabled: bool = True
    hotkey: str = DEFAULT_HOTKEY
    launch_at_login: bool = False

    @classmethod
    def from_dict(cls, payload=None):
        data = payload if isinstance(payload, dict) else {}
        hotkey = read_non_empty_string(data.get("hotkey")) or DEFAULT_HOTKEY
        return cls(
            active_model=normalize_model_key(data.get("active_model")),
            max_audio_sec=read_positive_int(data.get("max_audio_sec"), DEFAULT_MAX_AUDIO_SEC),
            native_typing_enabled=read_bool(data.get("native_typing_enabled"), True),
            hotkey=hotkey,
            launch_at_login=read_bool(data.get("launch_at_login"), False),
        )


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    active_model: str
    model_id: str
    max_audio_sec: int
    native_typing_enabled: bool
    hotkey: str
    launch_at_login: bool
    used_legacy_model_env: bool = False
    used_legacy_max_audio_env: bool = False


def default_config_dir():
    xdg_config_home = read_non_empty_string(os.environ.get("XDG_CONFIG_HOME"))
    base_dir = Path(xdg_config_home).expanduser() if xdg_config_home else Path.home() / ".config"
    return base_dir / APP_CONFIG_DIRNAME


def default_config_path():
    return default_config_dir() / CONFIG_FILENAME


def load_app_config(path=None):
    config_path = Path(path).expanduser() if path else default_config_path()

    try:
        raw_payload = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppConfig()
    except OSError:
        return AppConfig()

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return AppConfig()

    return AppConfig.from_dict(payload)


def save_app_config(config, path=None):
    config_path = Path(path).expanduser() if path else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(asdict(config), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


def resolve_runtime_config(env=None, stored_config=None):
    current_env = os.environ if env is None else env
    base_config = stored_config or load_app_config()

    model_id_from_current_env = read_non_empty_string(current_env.get("ASR_MODEL_ID"))
    model_id_from_legacy_env = read_non_empty_string(current_env.get("PARAKEET_MODEL_PATH"))

    if model_id_from_current_env or model_id_from_legacy_env:
        model_id = model_id_from_current_env or model_id_from_legacy_env
        active_model = find_model_key_by_id(model_id) or base_config.active_model
    else:
        active_model = normalize_model_key(base_config.active_model)
        model_id = get_model_profile(active_model).model_id

    max_audio_from_current_env = current_env.get("ASR_MAX_AUDIO_SEC")
    max_audio_from_legacy_env = current_env.get("PARAKEET_MAX_AUDIO_SEC")
    max_audio_value = max_audio_from_current_env
    if max_audio_value is None:
        max_audio_value = max_audio_from_legacy_env
    if max_audio_value is None:
        max_audio_value = base_config.max_audio_sec

    return RuntimeConfig(
        active_model=normalize_model_key(active_model),
        model_id=model_id,
        max_audio_sec=read_positive_int(max_audio_value, DEFAULT_MAX_AUDIO_SEC),
        native_typing_enabled=base_config.native_typing_enabled,
        hotkey=base_config.hotkey,
        launch_at_login=base_config.launch_at_login,
        used_legacy_model_env=not model_id_from_current_env and bool(model_id_from_legacy_env),
        used_legacy_max_audio_env=max_audio_from_current_env is None and max_audio_from_legacy_env is not None,
    )
