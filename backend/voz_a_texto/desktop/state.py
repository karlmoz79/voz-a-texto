from dataclasses import dataclass

from ..app_config import RuntimeConfig

STATUS_LOADING = "loading"
STATUS_READY = "ready"
STATUS_RECORDING = "recording"
STATUS_PROCESSING = "processing"
STATUS_ERROR = "error"


@dataclass(frozen=True, slots=True)
class DesktopShellState:
    status: str
    active_model: str
    native_typing_enabled: bool
    hotkey: str
    launch_at_login: bool
    language: str
    input_device: str | None
    last_transcript: str = ""
    current_transcript: str = ""
    error_message: str | None = None
    downloaded_models: tuple = ()
    input_devices_list: tuple = ()

    @property
    def can_export(self):
        return bool(self.last_transcript.strip())


def create_shell_state(runtime_config: RuntimeConfig, downloaded_models: tuple = (), input_devices_list: tuple = ()):
    return DesktopShellState(
        status=STATUS_READY,
        active_model=runtime_config.active_model,
        native_typing_enabled=runtime_config.native_typing_enabled,
        hotkey=runtime_config.hotkey,
        launch_at_login=runtime_config.launch_at_login,
        language=runtime_config.language,
        input_device=runtime_config.input_device,
        downloaded_models=downloaded_models,
        input_devices_list=input_devices_list,
    )


def status_label(status: str):
    return {
        STATUS_LOADING: "Cargando modelo...",
        STATUS_READY: "Listo",
        STATUS_RECORDING: "Grabando...",
        STATUS_PROCESSING: "Procesando transcripcion...",
        STATUS_ERROR: "Error",
    }.get(status, "Inactivo")
