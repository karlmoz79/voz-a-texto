import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from .autostart import AutostartService
from .paths import (
    APP_DISPLAY_NAME,
    DESKTOP_ENTRY_FILENAME,
    default_applications_dir,
    default_install_root,
    default_launcher_dir,
)


def _escape_desktop_arg(value):
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("$", "\\$")
    escaped = escaped.replace("`", "\\`")
    if " " in escaped:
        return f'"{escaped}"'
    return escaped


class DesktopInstallationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DesktopInstallationResult:
    install_root: Path
    backend_root: Path
    launcher_path: Path
    application_entry_path: Path


class DesktopInstallationService:
    def __init__(
        self,
        *,
        env=None,
        platform_name=None,
        source_backend_root=None,
        install_root=None,
        launcher_dir=None,
        applications_dir=None,
        autostart_dir=None,
        uv_executable=None,
        runner=None,
        which=None,
    ):
        self._env = os.environ if env is None else env
        self._platform_name = platform_name or sys.platform
        self._source_backend_root = (
            Path(source_backend_root) if source_backend_root else Path(__file__).resolve().parents[2]
        ).resolve()
        self._install_root = (
            Path(install_root) if install_root else default_install_root(self._env)
        ).expanduser()
        self._launcher_dir = (
            Path(launcher_dir) if launcher_dir else default_launcher_dir(self._env)
        ).expanduser()
        self._applications_dir = (
            Path(applications_dir) if applications_dir else default_applications_dir(self._env)
        ).expanduser()
        self._autostart_dir = Path(autostart_dir).expanduser() if autostart_dir else None
        self._uv_executable = Path(uv_executable).expanduser() if uv_executable else None
        self._runner = runner or subprocess.run
        self._which = which or shutil.which

    @property
    def install_root(self):
        return self._install_root

    @property
    def installed_backend_root(self):
        return self._install_root / "backend"

    @property
    def launcher_path(self):
        return self._launcher_dir / "voz-a-texto"

    @property
    def application_entry_path(self):
        return self._applications_dir / DESKTOP_ENTRY_FILENAME

    def install(self):
        self._ensure_linux_desktop()
        uv_path = self._resolve_uv_executable()
        self._ensure_source_backend()

        staging_root = self._build_staging_root()
        self._cleanup_path(staging_root)

        try:
            staging_backend_root = staging_root / "backend"
            self._copy_backend_tree(staging_backend_root)
            self._run_uv_sync(uv_path, staging_backend_root)
            self._replace_install_root(staging_root)
            self._write_launcher()
            self._write_application_entry()
        finally:
            self._cleanup_path(staging_root)

        return DesktopInstallationResult(
            install_root=self.install_root,
            backend_root=self.installed_backend_root,
            launcher_path=self.launcher_path,
            application_entry_path=self.application_entry_path,
        )

    def uninstall(self):
        self._cleanup_autostart()
        self._cleanup_path(self.application_entry_path)
        self._cleanup_path(self.launcher_path)
        self._cleanup_path(self.install_root)

    def render_launcher_script(self):
        backend_root = self.installed_backend_root
        python_path = backend_root / ".venv" / "bin" / "python"
        desktop_script_path = backend_root / "scripts" / "desktop_app.py"
        return "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                f"BACKEND_ROOT={self._shell_quote(str(backend_root))}",
                f"PYTHON_BIN={self._shell_quote(str(python_path))}",
                f"DESKTOP_SCRIPT={self._shell_quote(str(desktop_script_path))}",
                'cd "$BACKEND_ROOT"',
                'exec "$PYTHON_BIN" "$DESKTOP_SCRIPT" "$@"',
                "",
            ]
        )

    def render_application_entry(self):
        launcher_path = self.launcher_path
        escaped_launcher = _escape_desktop_arg(str(launcher_path))
        icon_path = self.installed_backend_root / "assets" / "icon.png"
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            f"Name={APP_DISPLAY_NAME}\n"
            f"Comment=Shell desktop local de {APP_DISPLAY_NAME}\n"
            f"TryExec={escaped_launcher}\n"
            f"Exec={escaped_launcher} --ui\n"
            "Terminal=false\n"
            "StartupNotify=false\n"
            f"Icon={icon_path}\n"
            "Categories=Utility;AudioVideo;\n"
        )

    def _resolve_uv_executable(self):
        uv_candidate = self._uv_executable
        if uv_candidate is None:
            resolved = self._which("uv")
            uv_candidate = Path(resolved).expanduser() if resolved else None

        if uv_candidate is None or not uv_candidate.exists():
            raise DesktopInstallationError(
                "No se encontro `uv`. Instala uv antes de preparar la instalacion desktop."
            )

        return uv_candidate.resolve()

    def _ensure_source_backend(self):
        required_paths = [
            self._source_backend_root / "pyproject.toml",
            self._source_backend_root / "uv.lock",
            self._source_backend_root / "scripts" / "desktop_app.py",
            self._source_backend_root / "voz_a_texto",
        ]
        missing_paths = [path for path in required_paths if not path.exists()]
        if missing_paths:
            missing = ", ".join(str(path) for path in missing_paths)
            raise DesktopInstallationError(
                f"No se pudo preparar la instalacion desktop. Faltan archivos requeridos: {missing}"
            )

    def _copy_backend_tree(self, target_backend_root):
        target_backend_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._source_backend_root / "pyproject.toml", target_backend_root / "pyproject.toml")
        shutil.copy2(self._source_backend_root / "uv.lock", target_backend_root / "uv.lock")
        shutil.copytree(
            self._source_backend_root / "scripts",
            target_backend_root / "scripts",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            self._source_backend_root / "voz_a_texto",
            target_backend_root / "voz_a_texto",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        if (self._source_backend_root / "assets").exists():
            shutil.copytree(
                self._source_backend_root / "assets",
                target_backend_root / "assets",
            )

    def _run_uv_sync(self, uv_path, backend_root):
        try:
            completed = self._runner(
                [str(uv_path), "sync", "--frozen"],
                cwd=str(backend_root),
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise DesktopInstallationError(
                f"No se pudo ejecutar `uv sync --frozen`: {exc}"
            ) from exc

        if completed.returncode == 0:
            return

        output = completed.stderr.strip() or completed.stdout.strip() or "uv sync fallo."
        raise DesktopInstallationError(
            f"No se pudo preparar el entorno Python de la app desktop: {output}"
        )

    def _write_launcher(self):
        python_path = self.installed_backend_root / ".venv" / "bin" / "python"
        desktop_script_path = self.installed_backend_root / "scripts" / "desktop_app.py"
        if not python_path.exists():
            raise DesktopInstallationError(
                f"No se encontro el runtime instalado en {python_path} despues de `uv sync --frozen`."
            )
        if not desktop_script_path.exists():
            raise DesktopInstallationError(
                f"No se encontro el entrypoint desktop instalado en {desktop_script_path}."
            )

        self._launcher_dir.mkdir(parents=True, exist_ok=True)
        self.launcher_path.write_text(self.render_launcher_script(), encoding="utf-8")
        current_mode = self.launcher_path.stat().st_mode
        self.launcher_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _write_application_entry(self):
        self._applications_dir.mkdir(parents=True, exist_ok=True)
        self.application_entry_path.write_text(self.render_application_entry(), encoding="utf-8")

    def _replace_install_root(self, staging_root):
        self.install_root.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_path(self.install_root)
        shutil.move(str(staging_root), str(self.install_root))

    def _cleanup_autostart(self):
        autostart_service = AutostartService(
            autostart_dir=self._autostart_dir,
            env=self._env,
            platform_name=self._platform_name,
            launcher_executable=self.launcher_path,
        )
        autostart_service.disable()

    def _build_staging_root(self):
        return self.install_root.parent / f".{self.install_root.name}-staging"

    def _ensure_linux_desktop(self):
        if not self._platform_name.startswith("linux"):
            raise DesktopInstallationError(
                "La instalacion desktop solo esta soportada en Linux."
            )

    def _cleanup_path(self, path):
        if not path.exists():
            return
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            return
        path.unlink()

    def _shell_quote(self, value):
        escaped = value.replace("'", "'\"'\"'")
        return f"'{escaped}'"
