from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon
import os

from ..models import MODEL_PROFILES
from .state import (
    STATUS_ERROR,
    STATUS_LOADING,
    STATUS_PROCESSING,
    STATUS_READY,
    STATUS_RECORDING,
    status_label,
)
from .paths import APP_DISPLAY_NAME


class TrayController(QObject):
    show_settings_requested = Signal()
    model_selected = Signal(str)
    native_typing_toggled = Signal(bool)
    autostart_toggled = Signal(bool)
    export_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        icon_path = os.path.join(base_dir, "assets", "icon.png")
        tray_idle_path = os.path.join(base_dir, "assets", "tray_idle.png")
        tray_recording_path = os.path.join(base_dir, "assets", "tray_recording.png")
        tray_processing_path = os.path.join(base_dir, "assets", "tray_processing.png")

        self.icon_paths = {
            "idle": tray_idle_path,
            "recording": tray_recording_path,
            "processing": tray_processing_path,
        }
        self._current_icon_key = None

        if os.path.exists(tray_idle_path):
            tray_icon = QIcon(tray_idle_path)
            if parent and os.path.exists(icon_path):
                parent.setWindowIcon(QIcon(icon_path))
        else:
            tray_icon = QApplication.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            )

        self.tray_icon = QSystemTrayIcon(tray_icon, parent)
        self.menu = QMenu()
        self.status_action = QAction("Estado: Listo", self.menu)
        self.status_action.setEnabled(False)

        self.open_action = QAction("Abrir ajustes", self.menu)
        self.model_menu = QMenu("Modelo activo", self.menu)
        self.native_typing_action = QAction("Dictado nativo", self.menu)
        self.native_typing_action.setCheckable(True)
        self.autostart_action = QAction("Iniciar con la sesion", self.menu)
        self.autostart_action.setCheckable(True)
        self.export_action = QAction("Exportar texto", self.menu)
        self.quit_action = QAction("Salir", self.menu)

        self.model_group = QActionGroup(self)
        self.model_group.setExclusive(True)
        self.model_actions = {}

        for profile in MODEL_PROFILES.values():
            action = QAction(profile.label, self.model_menu)
            action.setCheckable(True)
            action.setData(profile.key)
            self.model_group.addAction(action)
            self.model_menu.addAction(action)
            self.model_actions[profile.key] = action

        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        self.menu.addAction(self.open_action)
        self.menu.addMenu(self.model_menu)
        self.menu.addAction(self.native_typing_action)
        self.menu.addAction(self.autostart_action)
        self.menu.addAction(self.export_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.tray_icon.setContextMenu(self.menu)

        self.open_action.triggered.connect(self.show_settings_requested)
        self.native_typing_action.toggled.connect(self.native_typing_toggled)
        self.autostart_action.toggled.connect(self.autostart_toggled)
        self.export_action.triggered.connect(self.export_requested)
        self.quit_action.triggered.connect(self.quit_requested)
        self.model_group.triggered.connect(self._emit_model_selected)
        self.tray_icon.activated.connect(self._handle_activation)

    def show(self):
        self.tray_icon.show()

    def show_message(self, title, message):
        self.tray_icon.showMessage(title, message, self.tray_icon.icon())

    def apply_state(self, shell_state):
        label = status_label(shell_state.status)
        self.status_action.setText(f"Estado: {label}")
        self.tray_icon.setToolTip(f"{APP_DISPLAY_NAME} - {label}")
        self.export_action.setEnabled(shell_state.can_export)
        self._set_checkable_action(
            self.native_typing_action, shell_state.native_typing_enabled
        )
        self._set_checkable_action(self.autostart_action, shell_state.launch_at_login)
        models_enabled = shell_state.status != STATUS_LOADING

        if shell_state.status == STATUS_RECORDING:
            icon_key = "recording"
        elif shell_state.status in (STATUS_PROCESSING, STATUS_LOADING):
            icon_key = "processing"
        else:
            icon_key = "idle"

        icon_path = self.icon_paths.get(icon_key)
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, "rb") as f:
                data = f.read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.tray_icon.setIcon(QIcon(pixmap))
                self._current_icon_key = icon_key
            else:
                self.tray_icon.setIcon(
                    QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_MediaVolume
                    )
                )
        else:
            self.tray_icon.setIcon(
                QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
            )

        for action in self.model_actions.values():
            action.setEnabled(models_enabled)

        selected_action = self.model_actions.get(shell_state.active_model)
        if selected_action:
            previous = selected_action.blockSignals(True)
            selected_action.setChecked(True)
            selected_action.blockSignals(previous)

    def _emit_model_selected(self, action):
        model_key = action.data()
        if model_key:
            self.model_selected.emit(model_key)

    def _handle_activation(self, reason):
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_settings_requested.emit()

    def _set_checkable_action(self, action, value):
        previous = action.blockSignals(True)
        action.setChecked(value)
        action.blockSignals(previous)
