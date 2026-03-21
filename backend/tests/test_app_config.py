import tempfile
from pathlib import Path
import unittest

from voz_a_texto.app_config import (
    AppConfig,
    DEFAULT_HOTKEY,
    DEFAULT_MAX_AUDIO_SEC,
    load_app_config,
    resolve_runtime_config,
    save_app_config,
)
from voz_a_texto.models import FASTCONFORMER_ES_KEY, WHISPER_SMALL_KEY


class AppConfigTestCase(unittest.TestCase):
    def test_load_app_config_returns_defaults_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "missing.json"
            config = load_app_config(config_path)

        self.assertEqual(config.active_model, FASTCONFORMER_ES_KEY)
        self.assertEqual(config.max_audio_sec, DEFAULT_MAX_AUDIO_SEC)
        self.assertEqual(config.hotkey, DEFAULT_HOTKEY)
        self.assertTrue(config.native_typing_enabled)

    def test_save_round_trip_preserves_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            original = AppConfig(
                active_model=WHISPER_SMALL_KEY,
                max_audio_sec=45,
                native_typing_enabled=False,
                hotkey="Ctrl+Space",
                launch_at_login=True,
            )

            written_path = save_app_config(original, config_path)
            reloaded = load_app_config(written_path)

        self.assertEqual(reloaded, original)

    def test_runtime_config_prefers_explicit_env_values(self):
        stored_config = AppConfig(
            active_model=WHISPER_SMALL_KEY,
            max_audio_sec=99,
            native_typing_enabled=False,
            hotkey="Alt+Z",
            launch_at_login=False,
        )

        runtime_config = resolve_runtime_config(
            env={
                "ASR_MODEL_ID": "nvidia/stt_es_fastconformer_hybrid_large_pc",
                "ASR_MAX_AUDIO_SEC": "18",
            },
            stored_config=stored_config,
        )

        self.assertEqual(runtime_config.active_model, FASTCONFORMER_ES_KEY)
        self.assertEqual(runtime_config.model_id, "nvidia/stt_es_fastconformer_hybrid_large_pc")
        self.assertEqual(runtime_config.max_audio_sec, 18)
        self.assertFalse(runtime_config.used_legacy_model_env)
        self.assertFalse(runtime_config.used_legacy_max_audio_env)

    def test_runtime_config_accepts_legacy_env_aliases(self):
        runtime_config = resolve_runtime_config(
            env={
                "PARAKEET_MODEL_PATH": "small",
                "PARAKEET_MAX_AUDIO_SEC": "12",
            },
            stored_config=AppConfig(),
        )

        self.assertEqual(runtime_config.active_model, WHISPER_SMALL_KEY)
        self.assertEqual(runtime_config.model_id, "small")
        self.assertEqual(runtime_config.max_audio_sec, 12)
        self.assertTrue(runtime_config.used_legacy_model_env)
        self.assertTrue(runtime_config.used_legacy_max_audio_env)


if __name__ == "__main__":
    unittest.main()
