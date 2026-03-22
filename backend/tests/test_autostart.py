import tempfile
from pathlib import Path
import unittest

from voz_a_texto.desktop.autostart import AUTOSTART_FILENAME, AutostartError, AutostartService


class AutostartServiceTestCase(unittest.TestCase):
    def test_enable_prefers_installed_launcher_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            launcher_path = temp_path / "voz-a-texto"
            launcher_path.write_text("", encoding="utf-8")

            service = AutostartService(
                autostart_dir=temp_path / "autostart",
                platform_name="linux",
                launcher_executable=launcher_path,
            )

            entry_path = service.enable()

            entry_text = entry_path.read_text(encoding="utf-8")
            self.assertIn(f'TryExec="{launcher_path}"', entry_text)
            self.assertIn(f'Exec="{launcher_path}"', entry_text)

    def test_enable_writes_desktop_entry_with_desktop_shell_exec(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_path = temp_path / "python"
            script_path = temp_path / "desktop_app.py"
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")

            service = AutostartService(
                autostart_dir=temp_path / "autostart",
                platform_name="linux",
                python_executable=python_path,
                desktop_script_path=script_path,
            )

            entry_path = service.enable()

            self.assertEqual(entry_path.name, AUTOSTART_FILENAME)
            self.assertTrue(entry_path.exists())
            entry_text = entry_path.read_text(encoding="utf-8")
            self.assertIn("Name=VoxFlow", entry_text)
            self.assertIn(f'Exec="{python_path}" "{script_path}"', entry_text)

    def test_disable_removes_existing_autostart_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            entry_path = temp_path / AUTOSTART_FILENAME
            entry_path.write_text("test", encoding="utf-8")
            service = AutostartService(autostart_dir=temp_path)

            service.disable()

            self.assertFalse(entry_path.exists())

    def test_enable_fails_when_platform_is_not_linux(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_path = temp_path / "python"
            script_path = temp_path / "desktop_app.py"
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            service = AutostartService(
                autostart_dir=temp_path / "autostart",
                platform_name="darwin",
                python_executable=python_path,
                desktop_script_path=script_path,
            )

            with self.assertRaises(AutostartError) as context:
                service.enable()

            self.assertEqual(str(context.exception), "El inicio automatico solo esta soportado en Linux.")

    def test_enable_fails_when_desktop_entrypoint_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_path = temp_path / "python"
            python_path.write_text("", encoding="utf-8")
            service = AutostartService(
                autostart_dir=temp_path / "autostart",
                platform_name="linux",
                python_executable=python_path,
                desktop_script_path=temp_path / "missing.py",
            )

            with self.assertRaises(AutostartError) as context:
                service.enable()

            self.assertIn("No se encontro el entrypoint del shell desktop", str(context.exception))


if __name__ == "__main__":
    unittest.main()
