from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, QStandardPaths


def default_lockfile_path():
    runtime_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    base_dir = Path(runtime_dir) if runtime_dir else Path(QDir.tempPath())
    return base_dir / "voz-a-texto-desktop.lock"


class SingleInstanceGuard:
    def __init__(self, lockfile_path=None):
        target_path = Path(lockfile_path) if lockfile_path else default_lockfile_path()
        self._lockfile = QLockFile(str(target_path))
        self._lockfile.setStaleLockTime(0)

    def try_acquire(self):
        return self._lockfile.tryLock(100)

    def release(self):
        if self._lockfile.isLocked():
            self._lockfile.unlock()
