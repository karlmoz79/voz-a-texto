#!/usr/bin/env python3
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main():
    from voz_a_texto.desktop.qt_runtime import get_qt_startup_error

    startup_error = get_qt_startup_error()
    if startup_error:
        print(startup_error, file=sys.stderr)
        return 1

    try:
        from voz_a_texto.desktop.app import main as desktop_main
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "PySide6 no esta instalado. Ejecuta `cd backend && uv sync` para instalar "
                "las dependencias del shell de escritorio.",
                file=sys.stderr,
            )
            return 1
        raise

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
