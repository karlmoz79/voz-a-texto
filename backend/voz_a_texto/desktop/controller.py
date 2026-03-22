import threading
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer, QDir, QUrl
from PySide6.QtWidgets import QApplication, QFileDialog, QSystemTrayIcon
from PySide6.QtNetwork import QLocalServer
from PySide6.QtMultimedia import QSoundEffect

from ..app_config import load_app_config, resolve_runtime_config, save_app_config
from ..asr import ModelManager
from ..models import get_model_profile
from .autostart import AutostartError, AutostartService
from .audio_capture import AudioCaptureService, get_input_devices
from .paths import APP_DISPLAY_NAME
from .hotkey_service import GlobalHotkeyService
from .native_typing import NativeTypingError, NativeTypingService
from .transcript_store import TranscriptStore
from .settings_window import SettingsWindow
from .recording_popup import RecordingPopup
from .state import (
    STATUS_ERROR,
    STATUS_LOADING,
    STATUS_PROCESSING,
    STATUS_READY,
    STATUS_RECORDING,
    create_shell_state,
)
from .tray import TrayController


class TranscriptionSignals(QObject):
    completed = Signal(str)
    failed = Signal(str)


class ModelLoadSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class DesktopShellController(QObject):
    def __init__(self, app, config_path=None):
        super().__init__()
        self.app = app
        self.config_path = config_path
        self.app_config = load_app_config(config_path)
        self.runtime_config = resolve_runtime_config(stored_config=self.app_config)

        downloaded_models = self._check_downloaded_models()
        self.shell_state = create_shell_state(
            self.runtime_config,
            downloaded_models=downloaded_models,
            input_devices_list=tuple(get_input_devices()),
        )
        self.model_manager = ModelManager(self.runtime_config)
        self.audio_capture_service = AudioCaptureService()
        self.hotkey_service = GlobalHotkeyService(self.runtime_config.hotkey)
        self.autostart_service = AutostartService()
        self.native_typing_service = NativeTypingService()
        self.transcript_store = TranscriptStore()
        self.transcription_signals = TranscriptionSignals()
        self.model_load_signals = ModelLoadSignals()
        self._model_load_in_progress = False
        self._native_typing_support_checked = False

        self.settings_window = SettingsWindow()
        self.recording_popup = RecordingPopup()
        self.recording_popup.set_callbacks(
            on_stop=self.handle_recording_stop, on_cancel=self.handle_recording_cancel
        )
        self.tray_controller = TrayController(parent=app)

        self.start_beep = QSoundEffect(self)
        self.start_beep.setSource(
            QUrl.fromLocalFile(
                str(Path(__file__).parent.parent.parent / "assets" / "notification.wav")
            )
        )
        self.start_beep.setVolume(0.8)

        self.complete_beep = QSoundEffect(self)
        self.complete_beep.setSource(
            QUrl.fromLocalFile(
                str(Path(__file__).parent.parent.parent / "assets" / "notification.wav")
            )
        )
        self.complete_beep.setVolume(0.5)

        self._wire_signals()
        self._apply_state()

    def start(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_controller.show()
        else:
            self.show_settings()
        self._reconcile_launch_at_login()
        self._preload_active_model()
        self.hotkey_service.start()

        self.ipc_server = QLocalServer()
        self.ipc_server.removeServer("vox_flow_ipc")
        if self.ipc_server.listen("vox_flow_ipc"):
            self.ipc_server.newConnection.connect(self._on_ipc_connection)

    def _on_ipc_connection(self):
        socket = self.ipc_server.nextPendingConnection()
        socket.readyRead.connect(lambda: self._handle_ipc(socket))

    def _handle_ipc(self, socket):
        msg = socket.readAll().data().decode("utf-8")
        if msg == "show_ui":
            self.show_settings()
            self.settings_window.raise_()

    def shutdown(self):
        self.hotkey_service.stop()
        if self.audio_capture_service.is_recording:
            self.audio_capture_service.stop_recording()

    def show_settings(self):
        self.settings_window.present()

    def set_last_transcript(self, text):
        self.transcript_store.append(text)
        self._replace_state(last_transcript=self.transcript_store.full_text)

    def set_error(self, message):
        self._replace_state(status=STATUS_ERROR, error_message=message)

    def clear_error(self):
        status = (
            STATUS_READY
            if self.shell_state.status == STATUS_ERROR
            else self.shell_state.status
        )
        self._replace_state(status=status, error_message=None)

    def _wire_signals(self):
        self.app.aboutToQuit.connect(self.shutdown)

        self.tray_controller.show_settings_requested.connect(self.show_settings)
        self.tray_controller.model_selected.connect(self._set_active_model)
        self.tray_controller.native_typing_toggled.connect(
            self._set_native_typing_enabled
        )
        self.tray_controller.autostart_toggled.connect(self._set_launch_at_login)
        self.tray_controller.export_requested.connect(self._export_transcript)
        self.tray_controller.quit_requested.connect(self.app.quit)

        self.settings_window.model_selected.connect(self._set_active_model)
        self.settings_window.native_typing_toggled.connect(
            self._set_native_typing_enabled
        )
        self.settings_window.autostart_toggled.connect(self._set_launch_at_login)
        self.settings_window.export_requested.connect(self._export_transcript)
        self.settings_window.clear_requested.connect(self._clear_transcript)
        self.settings_window.delete_model_requested.connect(self._delete_model)
        self.settings_window.hotkey_changed.connect(self._set_hotkey)
        self.settings_window.mic_selected.connect(self._set_mic_selected)
        self.settings_window.language_selected.connect(self._set_language_selected)

        self.hotkey_service.activated.connect(self._handle_hotkey_pressed)
        self.hotkey_service.released.connect(self._handle_hotkey_released)
        self.hotkey_service.error.connect(self.set_error)
        self.transcription_signals.completed.connect(
            self._handle_transcription_completed
        )
        self.transcription_signals.failed.connect(self._handle_transcription_failed)
        self.model_load_signals.completed.connect(self._handle_model_load_completed)
        self.model_load_signals.failed.connect(self._handle_model_load_failed)

        self.vu_timer = QTimer()
        self.vu_timer.timeout.connect(self._update_vu_meter)
        self.vu_timer.start(50)

    def _set_active_model(self, model_key):
        profile = get_model_profile(model_key)
        if (
            self.app_config.active_model == profile.key
            and self.shell_state.active_model == profile.key
            and self.model_manager.loaded_model_id == profile.model_id
        ):
            return

        if self.shell_state.status in {STATUS_RECORDING, STATUS_PROCESSING}:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                "No se puede cambiar el modelo mientras hay un dictado en curso.",
            )
            return

        if self._model_load_in_progress:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                "Ya hay una carga de modelo en progreso.",
            )
            return

        self._begin_model_load(profile, persist_config=True, announce_success=True)

    def _check_downloaded_models(self):
        from ..models import MODEL_PROFILES
        from ..asr import is_model_downloaded

        downloaded = []
        for profile in MODEL_PROFILES.values():
            if is_model_downloaded(profile.model_id):
                downloaded.append(profile.key)
        return tuple(downloaded)

    def _delete_model(self, model_key):
        from ..models import get_model_profile
        from ..asr import delete_model_cache

        profile = get_model_profile(model_key)

        success = delete_model_cache(profile.model_id)
        if success:
            downloaded = self._check_downloaded_models()
            self._replace_state(downloaded_models=downloaded)
            self.settings_window.show_delete_success()
            self.tray_controller.show_message(
                APP_DISPLAY_NAME, f"Archivos de {profile.label} eliminados del disco."
            )
        else:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                f"El modelo {profile.label} no ocupaba espacio localmente.",
            )

    def _set_mic_selected(self, mic_name):
        self.app_config = replace(self.app_config, input_device=mic_name)
        self.runtime_config = replace(self.runtime_config, input_device=mic_name)
        self._persist_config()
        self._replace_state(input_device=mic_name)

    def _set_language_selected(self, lang):
        self.app_config = replace(self.app_config, language=lang)
        self.runtime_config = replace(self.runtime_config, language=lang)
        self._persist_config()
        self._replace_state(language=lang)

    def _set_native_typing_enabled(self, is_enabled):
        if self.app_config.native_typing_enabled == is_enabled:
            return

        if is_enabled:
            environment_error = self.native_typing_service.get_environment_error()
            if environment_error:
                self._disable_native_typing(environment_error, persist_config=False)
                return

        self._sync_native_typing_enabled(is_enabled, persist_config=True)
        self._replace_state(native_typing_enabled=is_enabled, error_message=None)

    def _set_hotkey(self, new_hotkey):
        if not new_hotkey or self.app_config.hotkey == new_hotkey:
            return

        try:
            self.hotkey_service.update_hotkey(new_hotkey)
        except ValueError as exc:
            self.tray_controller.show_message(APP_DISPLAY_NAME, f"Atajo invalido: {exc}")
            self.settings_window.apply_state(self.shell_state)
            return
        except Exception as exc:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME, f"Error al cambiar atajo: {exc}"
            )
            self.settings_window.apply_state(self.shell_state)
            return

        self.app_config = replace(self.app_config, hotkey=new_hotkey)
        self.runtime_config = replace(self.runtime_config, hotkey=new_hotkey)
        save_app_config(self.app_config, self.config_path)
        self._replace_state(hotkey=new_hotkey)
        self.tray_controller.show_message(
            APP_DISPLAY_NAME, f"Atajo actualizado: {new_hotkey}"
        )

    def _set_launch_at_login(self, is_enabled):
        if self.app_config.launch_at_login == is_enabled:
            return

        try:
            self.autostart_service.sync_enabled(is_enabled)
        except AutostartError as exc:
            self._replace_state(error_message=str(exc))
            self.tray_controller.show_message(APP_DISPLAY_NAME, str(exc))
            return

        self._sync_launch_at_login(is_enabled, persist_config=True)
        self._replace_state(launch_at_login=is_enabled)
        self.tray_controller.show_message(
            APP_DISPLAY_NAME,
            "Inicio automatico activado."
            if is_enabled
            else "Inicio automatico desactivado.",
        )

    def _update_vu_meter(self):
        if self.shell_state.status == STATUS_RECORDING:
            val = self.audio_capture_service.current_level * 100
            self.settings_window.vu_meter.setValue(int(val))

    def _handle_hotkey_pressed(self):
        if self.shell_state.status == STATUS_LOADING or self._model_load_in_progress:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                "El modelo aun se esta cargando. Intenta de nuevo en unos segundos.",
            )
            return

        if self.shell_state.status in {STATUS_RECORDING, STATUS_PROCESSING}:
            return

        if not self.model_manager.has_loaded_model():
            message = (
                self.shell_state.error_message
                or "Aun no hay ningun modelo listo para transcribir."
            )
            self.set_error(message)
            self.tray_controller.show_message(APP_DISPLAY_NAME, message)
            return

        self.clear_error()
        start_error = self.audio_capture_service.start_recording(
            self.runtime_config.max_audio_sec,
            input_device=self.runtime_config.input_device,
        )
        if start_error:
            self.set_error(start_error)
            self.tray_controller.show_message(APP_DISPLAY_NAME, start_error)
            return

        self.start_beep.play()
        self.recording_popup.show()
        self._replace_state(
            status=STATUS_RECORDING, error_message=None, current_transcript=""
        )

    def _handle_hotkey_released(self):
        """
        No detenemos la grabación al soltar las teclas.
        La grabación continúa hasta que se pulse el botón de Stop o Cancelar en el popup.
        """
        pass

    def handle_recording_cancel(self):
        """Descarta la grabación actual sin procesar."""
        if self.shell_state.status != STATUS_RECORDING:
            return

        self.audio_capture_service.stop_recording()
        self.recording_popup.hide()
        self._replace_state(status=STATUS_READY, error_message=None)

    def handle_recording_stop(self):
        """Detiene la grabación y procesa el audio."""
        if self.shell_state.status != STATUS_RECORDING:
            return

        capture_result = self.audio_capture_service.stop_recording()
        self.recording_popup.hide()
        if capture_result.error_message:
            self.set_error(capture_result.error_message)
            self.tray_controller.show_message(
                APP_DISPLAY_NAME, capture_result.error_message
            )
            return

        if capture_result.too_long:
            message = f"El audio supero el maximo de {self.runtime_config.max_audio_sec} segundos."
            self.set_error(message)
            self.tray_controller.show_message(APP_DISPLAY_NAME, message)
            return

        if not capture_result.audio_bytes:
            self.recording_popup.hide()
            self._replace_state(status=STATUS_READY, error_message=None)
            return

        model_id = self.runtime_config.model_id
        self._replace_state(status=STATUS_PROCESSING, error_message=None)
        worker = threading.Thread(
            target=self._run_transcription,
            args=(capture_result.audio_bytes, model_id),
            daemon=True,
        )
        worker.start()

    def _run_transcription(self, audio_bytes, model_id):
        try:
            text = self.model_manager.transcribe_bytes(
                audio_bytes, model_id=model_id, language=self.runtime_config.language
            ).strip()
        except Exception as exc:
            self.transcription_signals.failed.emit(f"Error transcribiendo: {exc}")
            return

        self.transcription_signals.completed.emit(text)

    def _handle_transcription_completed(self, text):
        self.recording_popup.hide()
        if text:
            self.transcript_store.append(text)
            next_transcript = self.transcript_store.full_text

            if self.runtime_config.native_typing_enabled:
                try:
                    self.native_typing_service.type_text(text)
                except NativeTypingError as exc:
                    if exc.disable_feature:
                        self._disable_native_typing(
                            str(exc),
                            persist_config=True,
                            extra_state={
                                "status": STATUS_READY,
                                "last_transcript": next_transcript,
                                "current_transcript": text,
                            },
                        )
                    else:
                        self._replace_state(
                            status=STATUS_READY,
                            last_transcript=next_transcript,
                            current_transcript=text,
                            error_message=str(exc),
                        )
                        self.tray_controller.show_message(APP_DISPLAY_NAME, str(exc))
                    return
                except Exception as exc:
                    message = f"No se pudo dictar el texto en la ventana activa: {exc}"
                    self._replace_state(
                        status=STATUS_READY,
                        last_transcript=next_transcript,
                        current_transcript=text,
                        error_message=message,
                    )
                    self.tray_controller.show_message(APP_DISPLAY_NAME, message)
                    return

            self._replace_state(
                status=STATUS_READY,
                last_transcript=next_transcript,
                current_transcript=text,
                error_message=None,
            )
            self.complete_beep.play()
            return

        self._replace_state(
            status=STATUS_READY, current_transcript="", error_message=None
        )

    def _handle_transcription_failed(self, message):
        self.recording_popup.hide()
        self.set_error(message)
        self.tray_controller.show_message(APP_DISPLAY_NAME, message)

    def _preload_active_model(self):
        if self._model_load_in_progress:
            return

        profile = get_model_profile(self.runtime_config.active_model)
        self._begin_model_load(profile, persist_config=False, announce_success=False)

    def _begin_model_load(self, profile, persist_config, announce_success):
        if self._model_load_in_progress:
            return False

        self._model_load_in_progress = True
        self._replace_state(status=STATUS_LOADING, error_message=None)
        worker = threading.Thread(
            target=self._run_model_load,
            args=(
                {
                    "model_key": profile.key,
                    "model_id": profile.model_id,
                    "model_label": profile.label,
                    "persist_config": persist_config,
                    "announce_success": announce_success,
                },
            ),
            daemon=True,
        )
        worker.start()
        return True

    def _run_model_load(self, context):
        try:
            self.model_manager.switch_active_model(context["model_id"])
        except Exception as exc:
            self.model_load_signals.failed.emit(
                {
                    **context,
                    "message": f"No se pudo cargar {context['model_label']}: {exc}",
                }
            )
            return

        self.model_load_signals.completed.emit(context)

    def _handle_model_load_completed(self, context):
        self._model_load_in_progress = False
        self.runtime_config = replace(
            self.runtime_config,
            active_model=context["model_key"],
            model_id=context["model_id"],
        )
        self.model_manager.runtime_config = self.runtime_config

        if context["persist_config"]:
            self.app_config = replace(
                self.app_config, active_model=context["model_key"]
            )
            self._persist_config()

        downloaded = self._check_downloaded_models()
        self._replace_state(
            status=STATUS_READY,
            active_model=context["model_key"],
            error_message=None,
            downloaded_models=downloaded,
        )

        if context["announce_success"]:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                f"Modelo activo: {context['model_label']}",
            )

        if not self._native_typing_support_checked:
            self._native_typing_support_checked = True
            self._validate_native_typing_support()

    def _handle_model_load_failed(self, context):
        self._model_load_in_progress = False
        self.set_error(context["message"])
        self.tray_controller.show_message(APP_DISPLAY_NAME, context["message"])

    def _export_transcript(self):
        if not self.transcript_store.can_export:
            self.tray_controller.show_message(
                APP_DISPLAY_NAME,
                "Aun no hay ninguna transcripcion para exportar.",
            )
            return

        default_path = Path.home() / "transcripcion.txt"
        target_path, _selected_filter = QFileDialog.getSaveFileName(
            self.settings_window,
            "Exportar transcripcion",
            str(default_path),
            "Text Files (*.txt);;All Files (*)",
        )
        if not target_path:
            return

        try:
            self.transcript_store.export_to_file(target_path)
        except (OSError, ValueError) as exc:
            self._replace_state(error_message=f"No se pudo exportar el texto: {exc}")
            self.tray_controller.show_message(
                APP_DISPLAY_NAME, "No se pudo exportar la transcripcion."
            )
            return

        self._replace_state(error_message=None)
        self.tray_controller.show_message(
            APP_DISPLAY_NAME, "Transcripcion exportada correctamente."
        )

    def _clear_transcript(self):
        self.transcript_store.clear()
        self._replace_state(last_transcript="", error_message=None)

    def _persist_config(self):
        save_app_config(self.app_config, self.config_path)

    def _sync_native_typing_enabled(self, is_enabled, persist_config):
        self.app_config = replace(self.app_config, native_typing_enabled=is_enabled)
        self.runtime_config = replace(
            self.runtime_config, native_typing_enabled=is_enabled
        )
        self.model_manager.runtime_config = self.runtime_config
        if persist_config:
            self._persist_config()

    def _sync_launch_at_login(self, is_enabled, persist_config):
        self.app_config = replace(self.app_config, launch_at_login=is_enabled)
        self.runtime_config = replace(self.runtime_config, launch_at_login=is_enabled)
        self.model_manager.runtime_config = self.runtime_config
        if persist_config:
            self._persist_config()

    def _reconcile_launch_at_login(self):
        desired_enabled = self.runtime_config.launch_at_login
        try:
            self.autostart_service.sync_enabled(desired_enabled)
        except AutostartError as exc:
            if desired_enabled:
                self._sync_launch_at_login(False, persist_config=True)
                self._replace_state(launch_at_login=False, error_message=str(exc))
            else:
                self._replace_state(error_message=str(exc))
            self.tray_controller.show_message(APP_DISPLAY_NAME, str(exc))

    def _validate_native_typing_support(self):
        if not self.runtime_config.native_typing_enabled:
            return

        environment_error = self.native_typing_service.get_environment_error()
        if environment_error:
            self._disable_native_typing(environment_error, persist_config=True)

    def _disable_native_typing(self, message, persist_config, extra_state=None):
        if (
            self.runtime_config.native_typing_enabled
            or self.app_config.native_typing_enabled
        ):
            self._sync_native_typing_enabled(False, persist_config=persist_config)

        changes = {
            "native_typing_enabled": False,
            "error_message": message,
        }
        if extra_state:
            changes.update(extra_state)
        self._replace_state(**changes)
        self.tray_controller.show_message(APP_DISPLAY_NAME, message)

    def _replace_state(
        self,
        status=None,
        active_model=None,
        native_typing_enabled=None,
        hotkey=None,
        launch_at_login=None,
        language=None,
        input_device=None,
        last_transcript=None,
        current_transcript=None,
        error_message=None,
        downloaded_models=None,
    ):
        changes = {}
        if status is not None:
            changes["status"] = status
        if active_model is not None:
            changes["active_model"] = active_model
        if native_typing_enabled is not None:
            changes["native_typing_enabled"] = native_typing_enabled
        if hotkey is not None:
            changes["hotkey"] = hotkey
        if launch_at_login is not None:
            changes["launch_at_login"] = launch_at_login
        if language is not None:
            changes["language"] = language
        if input_device is not None:
            changes["input_device"] = input_device
        if last_transcript is not None:
            changes["last_transcript"] = last_transcript
        if current_transcript is not None:
            changes["current_transcript"] = current_transcript
        if error_message is not None:
            changes["error_message"] = error_message
        if downloaded_models is not None:
            changes["downloaded_models"] = downloaded_models
        self.shell_state = replace(self.shell_state, **changes)
        self._apply_state()

    def _apply_state(self):
        self.settings_window.apply_state(self.shell_state)
        self.tray_controller.apply_state(self.shell_state)
