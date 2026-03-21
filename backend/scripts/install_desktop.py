#!/usr/bin/env python3
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main():
    from voz_a_texto.desktop.installation import DesktopInstallationError, DesktopInstallationService

    service = DesktopInstallationService()
    try:
        result = service.install()
    except DesktopInstallationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Instalacion desktop completada.")
    print(f"Launcher: {result.launcher_path}")
    print(f"Menu: {result.application_entry_path}")
    print(f"Runtime: {result.backend_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
