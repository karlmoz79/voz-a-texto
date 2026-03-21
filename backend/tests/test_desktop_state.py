import unittest

from voz_a_texto.app_config import RuntimeConfig
from voz_a_texto.desktop.state import create_shell_state
from voz_a_texto.models import FASTCONFORMER_ES_KEY


class DesktopStateTestCase(unittest.TestCase):
    def test_create_shell_state_uses_runtime_config_defaults(self):
        runtime_config = RuntimeConfig(
            active_model=FASTCONFORMER_ES_KEY,
            model_id="nvidia/stt_es_fastconformer_hybrid_large_pc",
            max_audio_sec=30,
            native_typing_enabled=True,
            hotkey="Alt+Z",
            launch_at_login=False,
        )

        shell_state = create_shell_state(runtime_config)

        self.assertEqual(shell_state.active_model, FASTCONFORMER_ES_KEY)
        self.assertEqual(shell_state.hotkey, "Alt+Z")
        self.assertTrue(shell_state.native_typing_enabled)
        self.assertFalse(shell_state.launch_at_login)
        self.assertFalse(shell_state.can_export)


if __name__ == "__main__":
    unittest.main()
