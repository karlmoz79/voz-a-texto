import subprocess
import unittest

from voz_a_texto.desktop.native_typing import NativeTypingError, NativeTypingService


class NativeTypingServiceTestCase(unittest.TestCase):
    def test_type_text_checks_focus_and_uses_safe_args(self):
        commands = []

        def fake_runner(args, **_kwargs):
            commands.append(args)
            if args[1] == "getwindowfocus":
                return subprocess.CompletedProcess(args, 0, stdout="123\n", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        service = NativeTypingService(
            env={"DISPLAY": ":0", "PATH": "/usr/bin"},
            runner=fake_runner,
            which=lambda _command: "/usr/bin/xdotool",
        )

        service.type_text("hola mundo")

        self.assertEqual(commands[0], ["xdotool", "getwindowfocus"])
        self.assertEqual(
            commands[1],
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", "--", "hola mundo "],
        )

    def test_type_text_raises_clear_error_when_command_is_missing(self):
        service = NativeTypingService(
            env={"DISPLAY": ":0", "PATH": ""},
            which=lambda _command: None,
        )

        with self.assertRaises(NativeTypingError) as context:
            service.type_text("hola")

        self.assertTrue(context.exception.disable_feature)
        self.assertIn("No se encontro `xdotool` en PATH", str(context.exception))

    def test_get_environment_error_reports_wayland_without_x11(self):
        service = NativeTypingService(
            env={"XDG_SESSION_TYPE": "wayland", "PATH": "/usr/bin"},
            which=lambda _command: "/usr/bin/xdotool",
        )

        message = service.get_environment_error()

        self.assertEqual(
            message,
            "El dictado nativo requiere una sesion X11 compatible. Wayland puro no esta soportado.",
        )

    def test_type_text_raises_recoverable_error_when_focus_lookup_fails(self):
        def fake_runner(args, **_kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="no focus")

        service = NativeTypingService(
            env={"DISPLAY": ":0", "PATH": "/usr/bin"},
            runner=fake_runner,
            which=lambda _command: "/usr/bin/xdotool",
        )

        with self.assertRaises(NativeTypingError) as context:
            service.type_text("hola")

        self.assertFalse(context.exception.disable_feature)
        self.assertIn("No hay una ventana enfocada compatible", str(context.exception))


if __name__ == "__main__":
    unittest.main()
