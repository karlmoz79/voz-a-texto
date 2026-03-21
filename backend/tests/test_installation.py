import os
import subprocess
import tempfile
from pathlib import Path
import unittest

from voz_a_texto.desktop.autostart import AUTOSTART_FILENAME
from voz_a_texto.desktop.installation import (
    DesktopInstallationError,
    DesktopInstallationService,
)


def write_backend_source(root):
    (root / "pyproject.toml").write_text("[project]\nname = 'backend'\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "desktop_app.py").write_text("print('desktop')\n", encoding="utf-8")
    (scripts_dir / "__pycache__").mkdir(parents=True, exist_ok=True)
    (scripts_dir / "__pycache__" / "desktop_app.pyc").write_text("", encoding="utf-8")

    package_dir = root / "voz_a_texto" / "desktop"
    package_dir.mkdir(parents=True, exist_ok=True)
    (root / "voz_a_texto" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")


class DesktopInstallationServiceTestCase(unittest.TestCase):
    def test_install_creates_runtime_launcher_and_application_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_backend_root = temp_path / "source-backend"
            source_backend_root.mkdir(parents=True, exist_ok=True)
            write_backend_source(source_backend_root)

            uv_path = temp_path / "bin" / "uv"
            uv_path.parent.mkdir(parents=True, exist_ok=True)
            uv_path.write_text("", encoding="utf-8")

            commands = []

            def fake_runner(args, cwd=None, **_kwargs):
                commands.append({"args": args, "cwd": cwd})
                python_path = Path(cwd) / ".venv" / "bin" / "python"
                python_path.parent.mkdir(parents=True, exist_ok=True)
                python_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

            home_dir = temp_path / "home"
            data_home = temp_path / "data"
            service = DesktopInstallationService(
                env={"HOME": str(home_dir), "XDG_DATA_HOME": str(data_home)},
                platform_name="linux",
                source_backend_root=source_backend_root,
                uv_executable=uv_path,
                runner=fake_runner,
            )

            result = service.install()

            self.assertEqual(commands[0]["args"], [str(uv_path.resolve()), "sync", "--frozen"])
            self.assertTrue(result.backend_root.exists())
            self.assertTrue((result.backend_root / "scripts" / "desktop_app.py").exists())
            self.assertTrue((result.backend_root / "voz_a_texto" / "desktop" / "app.py").exists())
            self.assertFalse((result.backend_root / "scripts" / "__pycache__").exists())

            launcher_text = result.launcher_path.read_text(encoding="utf-8")
            self.assertIn(str(result.backend_root / ".venv" / "bin" / "python"), launcher_text)
            self.assertIn(str(result.backend_root / "scripts" / "desktop_app.py"), launcher_text)
            self.assertTrue(os.access(result.launcher_path, os.X_OK))

            desktop_entry = result.application_entry_path.read_text(encoding="utf-8")
            self.assertIn(f'Exec="{result.launcher_path}"', desktop_entry)
            self.assertIn(f'TryExec="{result.launcher_path}"', desktop_entry)

    def test_uninstall_removes_runtime_launcher_desktop_entry_and_autostart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_backend_root = temp_path / "source-backend"
            source_backend_root.mkdir(parents=True, exist_ok=True)
            write_backend_source(source_backend_root)

            uv_path = temp_path / "bin" / "uv"
            uv_path.parent.mkdir(parents=True, exist_ok=True)
            uv_path.write_text("", encoding="utf-8")

            def fake_runner(args, cwd=None, **_kwargs):
                python_path = Path(cwd) / ".venv" / "bin" / "python"
                python_path.parent.mkdir(parents=True, exist_ok=True)
                python_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

            home_dir = temp_path / "home"
            data_home = temp_path / "data"
            service = DesktopInstallationService(
                env={"HOME": str(home_dir), "XDG_DATA_HOME": str(data_home)},
                platform_name="linux",
                source_backend_root=source_backend_root,
                uv_executable=uv_path,
                runner=fake_runner,
            )
            result = service.install()

            autostart_path = home_dir / ".config" / "autostart" / AUTOSTART_FILENAME
            autostart_path.parent.mkdir(parents=True, exist_ok=True)
            autostart_path.write_text("test", encoding="utf-8")

            config_path = home_dir / ".config" / "voz-a-texto" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("{}", encoding="utf-8")

            service.uninstall()

            self.assertFalse(result.install_root.exists())
            self.assertFalse(result.launcher_path.exists())
            self.assertFalse(result.application_entry_path.exists())
            self.assertFalse(autostart_path.exists())
            self.assertTrue(config_path.exists())

    def test_install_fails_with_clear_error_when_uv_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_backend_root = temp_path / "source-backend"
            source_backend_root.mkdir(parents=True, exist_ok=True)
            write_backend_source(source_backend_root)

            service = DesktopInstallationService(
                env={"HOME": str(temp_path / "home"), "XDG_DATA_HOME": str(temp_path / "data")},
                platform_name="linux",
                source_backend_root=source_backend_root,
                which=lambda _name: None,
            )

            with self.assertRaises(DesktopInstallationError) as context:
                service.install()

            self.assertEqual(
                str(context.exception),
                "No se encontro `uv`. Instala uv antes de preparar la instalacion desktop.",
            )


if __name__ == "__main__":
    unittest.main()
