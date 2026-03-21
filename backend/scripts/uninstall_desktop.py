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
        service.uninstall()
    except DesktopInstallationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Instalacion desktop eliminada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
