import os
from pathlib import Path


APP_DISPLAY_NAME = "VoxFlow"
APP_SLUG = "vox-flow"
LAUNCHER_FILENAME = APP_SLUG
DESKTOP_ENTRY_FILENAME = f"{APP_SLUG}.desktop"


def _read_non_empty_string(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def default_home_dir(env=None):
    current_env = os.environ if env is None else env
    configured_home = _read_non_empty_string(current_env.get("HOME"))
    if configured_home:
        return Path(configured_home).expanduser()
    return Path.home()


def default_data_home(env=None):
    current_env = os.environ if env is None else env
    configured_data_home = _read_non_empty_string(current_env.get("XDG_DATA_HOME"))
    if configured_data_home:
        return Path(configured_data_home).expanduser()
    return default_home_dir(current_env) / ".local" / "share"


def default_launcher_dir(env=None):
    return default_home_dir(env) / ".local" / "bin"


def default_launcher_path(env=None):
    return default_launcher_dir(env) / LAUNCHER_FILENAME


def default_applications_dir(env=None):
    return default_data_home(env) / "applications"


def default_install_root(env=None):
    return default_data_home(env) / APP_SLUG / "desktop"


def default_install_backend_root(env=None):
    return default_install_root(env) / "backend"
