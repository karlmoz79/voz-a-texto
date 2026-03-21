import unittest

from voz_a_texto.desktop.qt_runtime import get_qt_startup_error


class QtRuntimeTestCase(unittest.TestCase):
    def test_returns_none_on_non_linux(self):
        error = get_qt_startup_error(
            env={"DISPLAY": ":0"},
            platform_name="darwin",
        )

        self.assertIsNone(error)

    def test_returns_none_when_wayland_is_forced(self):
        error = get_qt_startup_error(
            env={"QT_QPA_PLATFORM": "wayland"},
            platform_name="linux",
            load_library=lambda _name: (_ for _ in ()).throw(AssertionError("should not load")),
        )

        self.assertIsNone(error)

    def test_returns_clear_error_when_xcb_cursor_library_is_missing(self):
        def missing_loader(_name):
            raise OSError("not found")

        error = get_qt_startup_error(
            env={"DISPLAY": ":0"},
            platform_name="linux",
            load_library=missing_loader,
        )

        self.assertIn("libxcb-cursor0", error)
        self.assertIn("sudo apt install libxcb-cursor0", error)

    def test_returns_none_when_xcb_cursor_library_is_available(self):
        error = get_qt_startup_error(
            env={"DISPLAY": ":0"},
            platform_name="linux",
            load_library=lambda _name: object(),
        )

        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
