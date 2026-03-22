import sys

from PySide6.QtWidgets import QApplication

from .controller import DesktopShellController
from .single_instance import SingleInstanceGuard
from PySide6.QtCore import QDir, QTimer
from PySide6.QtNetwork import QLocalSocket
from pathlib import Path


def main(argv=None):
    argv_list = argv or sys.argv
    app = QApplication(argv_list)
    app.setApplicationDisplayName("VoxFlow")
    app.setApplicationName("vox-flow")
    app.setQuitOnLastWindowClosed(False)

    guard = SingleInstanceGuard()
    if not guard.try_acquire():
        if "--ui" in argv_list:
            socket = QLocalSocket()
            socket.connectToServer("vox_flow_ipc")
            if socket.waitForConnected(500):
                socket.write(b"show_ui")
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
        print("VoxFlow ya se esta ejecutando.", file=sys.stderr)
        return 1

    app.aboutToQuit.connect(guard.release)

    controller = DesktopShellController(app)
    controller.start()

    if "--ui" in argv_list:
        QTimer.singleShot(100, controller.show_settings)

    return app.exec()
