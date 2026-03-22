from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from voz_a_texto.app_config import AppConfig, RuntimeConfig, load_app_config
from voz_a_texto.desktop.autostart import AutostartError
from voz_a_texto.desktop.controller import DesktopShellController
from voz_a_texto.desktop.native_typing import NativeTypingError
from voz_a_texto.desktop.state import STATUS_ERROR, STATUS_READY
from voz_a_texto.models import FASTCONFORMER_ES_KEY, WHISPER_SMALL_KEY


FASTCONFORMER_MODEL_ID = "nvidia/stt_es_fastconformer_hybrid_large_pc"
WHISPER_MODEL_ID = "small"


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FakeApp:
    def __init__(self):
        self.aboutToQuit = FakeSignal()
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class FakeSettingsWindow:
    def __init__(self):
        self.model_selected = FakeSignal()
        self.native_typing_toggled = FakeSignal()
        self.autostart_toggled = FakeSignal()
        self.export_requested = FakeSignal()
        self.clear_requested = FakeSignal()
        self.delete_model_requested = FakeSignal()
        self.hotkey_changed = FakeSignal()
        self.mic_selected = FakeSignal()
        self.language_selected = FakeSignal()
        self.last_state = None
        self.presented = False

    def apply_state(self, shell_state):
        self.last_state = shell_state

    def present(self):
        self.presented = True


class FakeRecordingPopup:
    def __init__(self):
        self.shown = False
        self.hidden = False
        self._stop_callback = None
        self._cancel_callback = None

    def show(self):
        self.shown = True

    def hide(self):
        self.hidden = True

    def set_stop_callback(self, callback):
        self._stop_callback = callback

    def set_callbacks(self, on_stop, on_cancel=None):
        self._stop_callback = on_stop
        self._cancel_callback = on_cancel



class FakeTrayController:
    def __init__(self, parent=None):
        self.parent = parent
        self.show_settings_requested = FakeSignal()
        self.model_selected = FakeSignal()
        self.native_typing_toggled = FakeSignal()
        self.autostart_toggled = FakeSignal()
        self.export_requested = FakeSignal()
        self.quit_requested = FakeSignal()
        self.last_state = None
        self.messages = []
        self.shown = False

    def apply_state(self, shell_state):
        self.last_state = shell_state

    def show(self):
        self.shown = True

    def show_message(self, title, message):
        self.messages.append((title, message))


class FakeHotkeyService:
    def __init__(self, hotkey):
        self.hotkey = hotkey
        self.activated = FakeSignal()
        self.released = FakeSignal()
        self.error = FakeSignal()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakeAudioCaptureService:
    def __init__(self):
        self.is_recording = False
        self.start_calls = []
        self.current_level = 0.0

    def start_recording(self, max_audio_sec, input_device=None):
        self.start_calls.append(max_audio_sec)
        self.is_recording = True
        return None

    def stop_recording(self):
        self.is_recording = False

        class FakeResult:
            def __init__(self):
                self.audio_bytes = b"fake-audio-content"
                self.too_long = False
                self.error_message = None

        return FakeResult()




class FakeModelManager:
    def __init__(self, runtime_config):
        self.runtime_config = runtime_config
        self.loaded = False
        self.switch_calls = []

    @property
    def loaded_model_id(self):
        return self.runtime_config.model_id if self.loaded else None

    def has_loaded_model(self):
        return self.loaded

    def switch_active_model(self, model_id):
        self.switch_calls.append(model_id)
        self.loaded = True

    def transcribe_bytes(self, audio_bytes, model_id=None):
        return ""


class FakeNativeTypingService:
    def __init__(self):
        self.environment_error = None
        self.type_error = None
        self.typed_texts = []

    def get_environment_error(self):
        return self.environment_error

    def type_text(self, text, append_space=True, backspaces=0, delay_ms=1):
        if self.type_error:
            raise self.type_error
        self.typed_texts.append(
            {
                "text": text,
                "append_space": append_space,
                "backspaces": backspaces,
                "delay_ms": delay_ms,
            }
        )


class FakeAutostartService:
    def __init__(self):
        self.enabled = False
        self.sync_error = None
        self.sync_calls = []

    def sync_enabled(self, is_enabled):
        self.sync_calls.append(is_enabled)
        if self.sync_error:
            raise self.sync_error
        self.enabled = is_enabled


class DesktopShellControllerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.app = FakeApp()
        self.runtime_config = RuntimeConfig(
            active_model=FASTCONFORMER_ES_KEY,
            model_id=FASTCONFORMER_MODEL_ID,
            max_audio_sec=30,
            native_typing_enabled=True,
            hotkey="Alt+Z",
            launch_at_login=False,
            language="auto",
            input_device=None,
        )
        self.patchers = [
            patch("voz_a_texto.desktop.controller.SettingsWindow", FakeSettingsWindow),
            patch("voz_a_texto.desktop.controller.RecordingPopup", FakeRecordingPopup),
            patch("voz_a_texto.desktop.controller.TrayController", FakeTrayController),
            patch(
                "voz_a_texto.desktop.controller.GlobalHotkeyService", FakeHotkeyService
            ),
            patch(
                "voz_a_texto.desktop.controller.AudioCaptureService",
                FakeAudioCaptureService,
            ),
            patch("voz_a_texto.desktop.controller.ModelManager", FakeModelManager),
            patch(
                "voz_a_texto.desktop.controller.QSystemTrayIcon.isSystemTrayAvailable",
                return_value=True,
            ),
            patch(
                "voz_a_texto.desktop.controller.load_app_config",
                return_value=AppConfig(),
            ),
            patch(
                "voz_a_texto.desktop.controller.resolve_runtime_config",
                return_value=self.runtime_config,
            ),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.controller = DesktopShellController(self.app, config_path=self.config_path)
        self.controller.autostart_service = FakeAutostartService()
        self.controller.native_typing_service = FakeNativeTypingService()

    def test_hotkey_press_requires_a_loaded_model(self):
        self.controller._handle_hotkey_pressed()

        self.assertEqual(self.controller.shell_state.status, STATUS_ERROR)
        self.assertEqual(self.controller.audio_capture_service.start_calls, [])
        self.assertIn(
            "Aun no hay ningun modelo listo", self.controller.shell_state.error_message
        )
        self.assertEqual(
            self.controller.tray_controller.messages[-1][1],
            "Aun no hay ningun modelo listo para transcribir.",
        )

    def test_handle_model_load_completed_updates_state_and_persists_model(self):
        context = {
            "model_key": WHISPER_SMALL_KEY,
            "model_id": WHISPER_MODEL_ID,
            "model_label": "Multi-idioma (Whisper Small)",
            "persist_config": True,
            "announce_success": True,
        }

        self.controller._handle_model_load_completed(context)

        self.assertEqual(self.controller.shell_state.status, STATUS_READY)
        self.assertEqual(self.controller.shell_state.active_model, WHISPER_SMALL_KEY)
        self.assertEqual(self.controller.runtime_config.active_model, WHISPER_SMALL_KEY)
        self.assertEqual(self.controller.runtime_config.model_id, WHISPER_MODEL_ID)
        self.assertEqual(self.controller.app_config.active_model, WHISPER_SMALL_KEY)
        persisted_config = load_app_config(self.config_path)
        self.assertEqual(persisted_config.active_model, WHISPER_SMALL_KEY)
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            ("VoxFlow", "Modelo activo: Multi-idioma (Whisper Small)"),
        )

    def test_set_active_model_retries_when_selected_model_is_not_loaded(self):
        with patch.object(
            self.controller, "_begin_model_load", return_value=True
        ) as begin_model_load:
            self.controller._set_active_model(FASTCONFORMER_ES_KEY)

        begin_model_load.assert_called_once()

    def test_handle_model_load_failed_preserves_previous_model_selection(self):
        previous_active_model = self.controller.shell_state.active_model

        self.controller._handle_model_load_failed(
            {"message": "No se pudo cargar: boom"}
        )

        self.assertEqual(self.controller.shell_state.status, STATUS_ERROR)
        self.assertEqual(
            self.controller.shell_state.active_model, previous_active_model
        )
        self.assertEqual(self.controller.app_config.active_model, FASTCONFORMER_ES_KEY)
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            ("VoxFlow", "No se pudo cargar: boom"),
        )

    def test_set_launch_at_login_persists_when_autostart_succeeds(self):
        self.controller._set_launch_at_login(True)

        self.assertEqual(self.controller.autostart_service.sync_calls, [True])
        self.assertTrue(self.controller.shell_state.launch_at_login)
        self.assertTrue(self.controller.app_config.launch_at_login)
        self.assertTrue(self.controller.runtime_config.launch_at_login)
        persisted_config = load_app_config(self.config_path)
        self.assertTrue(persisted_config.launch_at_login)
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            ("VoxFlow", "Inicio automatico activado."),
        )

    def test_set_launch_at_login_keeps_previous_state_when_autostart_fails(self):
        self.controller.autostart_service.sync_error = AutostartError(
            "No se pudo escribir el archivo de autostart: permiso denegado"
        )

        self.controller._set_launch_at_login(True)

        self.assertFalse(self.controller.shell_state.launch_at_login)
        self.assertFalse(self.controller.app_config.launch_at_login)
        self.assertFalse(self.controller.runtime_config.launch_at_login)
        persisted_config = load_app_config(self.config_path)
        self.assertFalse(persisted_config.launch_at_login)
        self.assertEqual(
            self.controller.shell_state.error_message,
            "No se pudo escribir el archivo de autostart: permiso denegado",
        )
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            (
                "VoxFlow",
                "No se pudo escribir el archivo de autostart: permiso denegado",
            ),
        )

    def test_start_reconciles_launch_at_login_with_autostart_service(self):
        self.controller.app_config = replace(
            self.controller.app_config, launch_at_login=True
        )
        self.controller.runtime_config = replace(
            self.controller.runtime_config, launch_at_login=True
        )
        self.controller.model_manager.runtime_config = self.controller.runtime_config
        self.controller.shell_state = replace(
            self.controller.shell_state, launch_at_login=True
        )

        with patch.object(
            self.controller, "_preload_active_model"
        ) as preload_active_model:
            self.controller.start()

        preload_active_model.assert_called_once()
        self.assertEqual(self.controller.autostart_service.sync_calls, [True])
        self.assertTrue(self.controller.tray_controller.shown)
        self.assertTrue(self.controller.hotkey_service.started)

    def test_start_disables_launch_at_login_when_reconcile_fails(self):
        self.controller.app_config = replace(
            self.controller.app_config, launch_at_login=True
        )
        self.controller.runtime_config = replace(
            self.controller.runtime_config, launch_at_login=True
        )
        self.controller.model_manager.runtime_config = self.controller.runtime_config
        self.controller.shell_state = replace(
            self.controller.shell_state, launch_at_login=True
        )
        self.controller.autostart_service.sync_error = AutostartError(
            "No se encontro el interprete de Python para autostart: /missing/python"
        )

        with patch.object(self.controller, "_preload_active_model"):
            self.controller.start()

        self.assertFalse(self.controller.shell_state.launch_at_login)
        self.assertFalse(self.controller.app_config.launch_at_login)
        self.assertFalse(self.controller.runtime_config.launch_at_login)
        persisted_config = load_app_config(self.config_path)
        self.assertFalse(persisted_config.launch_at_login)
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            (
                "VoxFlow",
                "No se encontro el interprete de Python para autostart: /missing/python",
            ),
        )

    def test_handle_transcription_completed_types_text_when_native_typing_is_enabled(
        self,
    ):
        self.controller._handle_transcription_completed("hola mundo")

        self.assertEqual(
            self.controller.native_typing_service.typed_texts,
            [
                {
                    "text": "hola mundo",
                    "append_space": True,
                    "backspaces": 0,
                    "delay_ms": 1,
                }
            ],
        )
        self.assertEqual(self.controller.shell_state.status, STATUS_READY)
        self.assertEqual(self.controller.shell_state.last_transcript, "hola mundo")
        self.assertIsNone(self.controller.shell_state.error_message)

    def test_handle_transcription_completed_keeps_transcript_when_native_typing_fails(
        self,
    ):
        self.controller.native_typing_service.type_error = NativeTypingError(
            "No hay una ventana enfocada compatible para dictado nativo."
        )

        self.controller._handle_transcription_completed("hola mundo")

        self.assertEqual(self.controller.shell_state.status, STATUS_READY)
        self.assertEqual(self.controller.shell_state.last_transcript, "hola mundo")
        self.assertEqual(
            self.controller.shell_state.error_message,
            "No hay una ventana enfocada compatible para dictado nativo.",
        )
        self.assertTrue(self.controller.shell_state.native_typing_enabled)
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            (
                "VoxFlow",
                "No hay una ventana enfocada compatible para dictado nativo.",
            ),
        )

    def test_handle_transcription_completed_disables_native_typing_when_environment_is_invalid(
        self,
    ):
        self.controller.native_typing_service.type_error = NativeTypingError(
            "No se encontro `xdotool` en PATH. Instala xdotool para usar dictado nativo.",
            disable_feature=True,
        )

        self.controller._handle_transcription_completed("hola mundo")

        self.assertEqual(self.controller.shell_state.status, STATUS_READY)
        self.assertEqual(self.controller.shell_state.last_transcript, "hola mundo")
        self.assertFalse(self.controller.shell_state.native_typing_enabled)
        self.assertFalse(self.controller.app_config.native_typing_enabled)
        self.assertFalse(self.controller.runtime_config.native_typing_enabled)
        self.assertEqual(
            self.controller.shell_state.error_message,
            "No se encontro `xdotool` en PATH. Instala xdotool para usar dictado nativo.",
        )
        self.assertEqual(
            self.controller.tray_controller.messages[-1],
            (
                "VoxFlow",
                "No se encontro `xdotool` en PATH. Instala xdotool para usar dictado nativo.",
            ),
        )

    def test_clear_transcript(self):
        self.controller.transcript_store.append("texto uno")
        self.controller.transcript_store.append("texto dos")
        self.assertEqual(self.controller.transcript_store.count, 2)
        self.assertTrue(bool(self.controller.transcript_store.full_text))

        self.controller._clear_transcript()

        self.assertEqual(self.controller.transcript_store.count, 0)
        self.assertEqual(self.controller.shell_state.last_transcript, "")

        self.controller.transcript_store.append("texto nuevo")
        self.assertEqual(self.controller.transcript_store.count, 1)
        self.assertEqual(self.controller.transcript_store.full_text, "texto nuevo")


    def test_hotkey_release_does_not_stop_recording(self):
        self.controller.model_manager.loaded = True
        self.controller._handle_hotkey_pressed()
        self.assertTrue(self.controller.audio_capture_service.is_recording)

        self.controller._handle_hotkey_released()
        # La grabación debe continuar (nueva funcionalidad)
        self.assertTrue(self.controller.audio_capture_service.is_recording)

    def test_handle_recording_stop_stops_and_processes(self):
        self.controller.model_manager.loaded = True
        self.controller._handle_hotkey_pressed()

        with patch("voz_a_texto.desktop.controller.threading.Thread") as MockThread:
            self.controller.handle_recording_stop()
            self.assertFalse(self.controller.audio_capture_service.is_recording)
            self.assertTrue(self.controller.recording_popup.hidden)
            # Debe iniciar el hilo de procesamiento
            MockThread.assert_called_once()

    def test_handle_recording_cancel_stops_without_processing(self):
        self.controller.model_manager.loaded = True
        self.controller._handle_hotkey_pressed()

        with patch("voz_a_texto.desktop.controller.threading.Thread") as MockThread:
            self.controller.handle_recording_cancel()
            self.assertFalse(self.controller.audio_capture_service.is_recording)
            self.assertTrue(self.controller.recording_popup.hidden)
            # No debe iniciar procesamiento
            MockThread.assert_not_called()
            self.assertEqual(self.controller.shell_state.status, STATUS_READY)


if __name__ == "__main__":
    unittest.main()
