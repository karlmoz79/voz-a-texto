import base64
import unittest

from voz_a_texto.app_config import RuntimeConfig
from voz_a_texto.asr import MODEL_STATE_ERROR, MODEL_STATE_READY, ModelManager
from voz_a_texto.models import FASTCONFORMER_ES_KEY, WHISPER_SMALL_KEY


class FakeModel:
    def __init__(self, result_text):
        self.result_text = result_text
        self.transcribe_calls = []

    def transcribe(self, paths):
        self.transcribe_calls.append(list(paths))
        return [self.result_text]


class ModelManagerTestCase(unittest.TestCase):
    def test_load_active_model_reuses_same_loaded_model(self):
        created_models = []

        def fake_loader(model_id):
            model = FakeModel(result_text=model_id)
            created_models.append(model)
            return model

        manager = ModelManager(
            runtime_config=RuntimeConfig(
                active_model=FASTCONFORMER_ES_KEY,
                model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
                max_audio_sec=30,
                native_typing_enabled=True,
                hotkey="Alt+Z",
                launch_at_login=False,
            ),
            model_loader=fake_loader,
        )

        first_model = manager.load_active_model()
        second_model = manager.load_active_model()

        self.assertIs(first_model, second_model)
        self.assertEqual(len(created_models), 1)
        self.assertEqual(manager.state, MODEL_STATE_READY)

    def test_load_model_updates_runtime_config_when_switching_models(self):
        manager = ModelManager(
            runtime_config=RuntimeConfig(
                active_model=FASTCONFORMER_ES_KEY,
                model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
                max_audio_sec=30,
                native_typing_enabled=True,
                hotkey="Alt+Z",
                launch_at_login=False,
            ),
            model_loader=lambda model_id: FakeModel(result_text=model_id),
        )

        manager.load_model("small")

        self.assertEqual(manager.runtime_config.active_model, WHISPER_SMALL_KEY)
        self.assertEqual(manager.loaded_model_id, "small")
        self.assertEqual(manager.state, MODEL_STATE_READY)

    def test_transcribe_base64_uses_loaded_model_and_returns_text(self):
        model = FakeModel(result_text="hola mundo")
        manager = ModelManager(
            runtime_config=RuntimeConfig(
                active_model=FASTCONFORMER_ES_KEY,
                model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
                max_audio_sec=30,
                native_typing_enabled=True,
                hotkey="Alt+Z",
                launch_at_login=False,
            ),
            model_loader=lambda _model_id: model,
        )

        audio_base64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
        transcription = manager.transcribe_base64(audio_base64)

        self.assertEqual(transcription, "hola mundo")
        self.assertEqual(len(model.transcribe_calls), 1)

    def test_switch_active_model_keeps_previous_model_when_new_load_fails(self):
        def fake_loader(model_id):
            if model_id == "small":
                raise RuntimeError("boom")
            return FakeModel(result_text=model_id)

        manager = ModelManager(
            runtime_config=RuntimeConfig(
                active_model=FASTCONFORMER_ES_KEY,
                model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
                max_audio_sec=30,
                native_typing_enabled=True,
                hotkey="Alt+Z",
                launch_at_login=False,
            ),
            model_loader=fake_loader,
        )

        manager.load_active_model()

        with self.assertRaises(RuntimeError):
            manager.switch_active_model("small")

        self.assertTrue(manager.has_loaded_model())
        self.assertEqual(manager.loaded_model_id, "nvidia/stt_es_fastconformer_hybrid_large_pc")
        self.assertEqual(manager.runtime_config.active_model, FASTCONFORMER_ES_KEY)
        self.assertEqual(manager.state, MODEL_STATE_ERROR)


if __name__ == "__main__":
    unittest.main()
