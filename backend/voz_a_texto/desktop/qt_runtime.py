import ctypes
import os
import sys


def _read_non_empty_string(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _should_check_xcb_dependency(env):
    platform_hint = _read_non_empty_string(env.get("QT_QPA_PLATFORM"))
    if platform_hint:
        normalized = platform_hint.lower()
        if "wayland" in normalized:
            return False
        if "xcb" in normalized:
            return True

    session_type = _read_non_empty_string(env.get("XDG_SESSION_TYPE"))
    if session_type:
        normalized_session = session_type.lower()
        if normalized_session == "x11":
            return True
        if normalized_session == "wayland" and not _read_non_empty_string(env.get("DISPLAY")):
            return False

    return bool(_read_non_empty_string(env.get("DISPLAY")))


def get_qt_startup_error(env=None, platform_name=None, load_library=None):
    current_env = os.environ if env is None else env
    current_platform = platform_name or sys.platform
    if not current_platform.startswith("linux"):
        return None
    if not _should_check_xcb_dependency(current_env):
        return None

    loader = load_library or ctypes.CDLL
    try:
        loader("libxcb-cursor.so.0")
    except OSError:
        return (
            "Falta la libreria del sistema `libxcb-cursor0`, requerida por Qt para cargar "
            "el plugin `xcb`. En Linux Mint/Ubuntu/Debian instala `sudo apt install "
            "libxcb-cursor0` y vuelve a ejecutar `npm run desktop`."
        )

    return None
