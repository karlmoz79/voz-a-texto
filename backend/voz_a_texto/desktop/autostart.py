import os
from pathlib import Path
import sys

from .paths import APP_DISPLAY_NAME, DESKTOP_ENTRY_FILENAME, default_home_dir, default_launcher_path

AUTOSTART_FILENAME = DESKTOP_ENTRY_FILENAME


def default_autostart_dir(env=None):
    current_env = os.environ if env is None else env
    xdg_config_home = current_env.get("XDG_CONFIG_HOME")
    if isinstance(xdg_config_home, str) and xdg_config_home.strip():
        base_dir = Path(xdg_config_home).expanduser()
    else:
        base_dir = default_home_dir(current_env) / ".config"
    return base_dir / "autostart"


def _escape_exec_arg(value):
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("$", "\\$")
    escaped = escaped.replace("`", "\\`")
    return f'"{escaped}"'


class AutostartError(RuntimeError):
    pass


class AutostartService:
    def __init__(
        self,
        autostart_dir=None,
        env=None,
        platform_name=None,
        python_executable=None,
        desktop_script_path=None,
        launcher_executable=None,
    ):
        self._env = os.environ if env is None else env
        self._platform_name = platform_name or sys.platform
        self._autostart_dir = (
            Path(autostart_dir) if autostart_dir else default_autostart_dir(self._env)
        )
        backend_root = Path(__file__).resolve().parents[2]
        self._python_executable = (
            Path(python_executable) if python_executable else Path(sys.executable)
        ).resolve()
        self._desktop_script_path = (
            Path(desktop_script_path)
            if desktop_script_path
            else backend_root / "scripts" / "desktop_app.py"
        ).resolve()
        self._launcher_executable = (
            Path(launcher_executable)
            if launcher_executable
            else default_launcher_path(self._env)
        ).expanduser()

    @property
    def entry_path(self):
        return self._autostart_dir / AUTOSTART_FILENAME

    def is_enabled(self):
        return self.entry_path.exists()

    def sync_enabled(self, is_enabled):
        if is_enabled:
            return self.enable()
        self.disable()
        return self.entry_path

    def enable(self):
        self._ensure_linux_desktop()
        self._ensure_entrypoint_exists()

        try:
            self._autostart_dir.mkdir(parents=True, exist_ok=True)
            self.entry_path.write_text(self.render_desktop_entry(), encoding="utf-8")
        except OSError as exc:
            raise AutostartError(
                f"No se pudo escribir el archivo de autostart: {exc}"
            ) from exc

        return self.entry_path

    def disable(self):
        if not self.entry_path.exists():
            return
        try:
            self.entry_path.unlink()
        except OSError as exc:
            raise AutostartError(
                f"No se pudo eliminar el archivo de autostart: {exc}"
            ) from exc

    def render_desktop_entry(self):
        exec_command = self.build_exec_command()
        try_exec = self.build_try_exec()
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            f"Name={APP_DISPLAY_NAME}\n"
            f"Comment=Shell desktop local de {APP_DISPLAY_NAME}\n"
            f"TryExec={try_exec}\n"
            f"Exec={exec_command}\n"
            "Terminal=false\n"
            "StartupNotify=false\n"
            "Icon=audio-input-microphone\n"
            "Categories=Utility;AudioVideo;\n"
            "X-GNOME-Autostart-enabled=true\n"
        )

    def build_exec_command(self):
        if self._launcher_executable.exists():
            return _escape_exec_arg(str(self._launcher_executable))
        return " ".join(
            [
                _escape_exec_arg(str(self._python_executable)),
                _escape_exec_arg(str(self._desktop_script_path)),
            ]
        )

    def build_try_exec(self):
        if self._launcher_executable.exists():
            return _escape_exec_arg(str(self._launcher_executable))
        return _escape_exec_arg(str(self._python_executable))

    def _ensure_linux_desktop(self):
        if not self._platform_name.startswith("linux"):
            raise AutostartError("El inicio automatico solo esta soportado en Linux.")

    def _ensure_entrypoint_exists(self):
        if self._launcher_executable.exists():
            return
        if not self._python_executable.exists():
            raise AutostartError(
                f"No se encontro el interprete de Python para autostart: {self._python_executable}"
            )
        if not self._desktop_script_path.exists():
            raise AutostartError(
                f"No se encontro el entrypoint del shell desktop: {self._desktop_script_path}"
            )
