from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtGui import QKeyEvent, QKeySequence
from ..models import MODEL_PROFILES
from .state import STATUS_LOADING, status_label


class HotkeyInputWidget(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("Toca las teclas...")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            super().keyPressEvent(event)
            return

        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Super")

        if key == Qt.Key.Key_Space:
            parts.append("Space")
        else:
            key_str = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)
            if key_str:
                parts.append(key_str)

        if parts:
            self.setText("+".join(parts))
        event.accept()


class SettingsWindow(QWidget):
    model_selected = Signal(str)
    native_typing_toggled = Signal(bool)
    autostart_toggled = Signal(bool)
    export_requested = Signal()
    hotkey_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voz a Texto")
        self.resize(520, 420)

        self.status_value = QLabel("Listo")
        self.model_combo = QComboBox()
        self.hotkey_input = HotkeyInputWidget()
        self.hotkey_apply_btn = QPushButton("Cambiar")
        self.native_typing_checkbox = QCheckBox("Dictado nativo")
        self.autostart_checkbox = QCheckBox("Iniciar con la sesion")
        self.error_label = QLabel("")
        self.transcript_view = QPlainTextEdit()
        self.export_button = QPushButton("Exportar texto")
        self.close_button = QPushButton("Ocultar")

        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Aun no hay transcripciones en esta sesion.")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        for profile in MODEL_PROFILES.values():
            self.model_combo.addItem(profile.label, profile.key)

        form_layout = QFormLayout()
        form_layout.addRow("Estado", self.status_value)
        form_layout.addRow("Modelo activo", self.model_combo)
        
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(self.hotkey_input)
        hotkey_layout.addWidget(self.hotkey_apply_btn)
        form_layout.addRow("Hotkey", hotkey_layout)

        button_row = QHBoxLayout()
        button_row.addWidget(self.export_button)
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)

        root_layout = QVBoxLayout()
        root_layout.addLayout(form_layout)
        root_layout.addWidget(self.native_typing_checkbox)
        root_layout.addWidget(self.autostart_checkbox)
        root_layout.addWidget(self.error_label)
        root_layout.addWidget(QLabel("Historial reciente"))
        root_layout.addWidget(self.transcript_view, 1)
        root_layout.addLayout(button_row)
        self.setLayout(root_layout)

        self.model_combo.currentIndexChanged.connect(self._emit_model_selected)
        self.native_typing_checkbox.toggled.connect(self.native_typing_toggled)
        self.autostart_checkbox.toggled.connect(self.autostart_toggled)
        self.export_button.clicked.connect(self.export_requested)
        self.hotkey_apply_btn.clicked.connect(self._emit_hotkey_changed)
        self.hotkey_input.returnPressed.connect(self._emit_hotkey_changed)
        self.close_button.clicked.connect(self.hide)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def apply_state(self, shell_state):
        self.status_value.setText(status_label(shell_state.status))
        if not self.hotkey_input.hasFocus():
            self.hotkey_input.setText(shell_state.hotkey)
        self.model_combo.setEnabled(shell_state.status != STATUS_LOADING)
        self._set_combo_value(shell_state.active_model)
        self._set_checkbox_value(self.native_typing_checkbox, shell_state.native_typing_enabled)
        self._set_checkbox_value(self.autostart_checkbox, shell_state.launch_at_login)
        self.export_button.setEnabled(shell_state.can_export)
        if shell_state.last_transcript:
            self.transcript_view.setPlainText(shell_state.last_transcript)
        else:
            self.transcript_view.clear()
        if shell_state.error_message:
            self.error_label.setText(shell_state.error_message)
            self.error_label.show()
        else:
            self.error_label.clear()
            self.error_label.hide()

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _emit_model_selected(self):
        model_key = self.model_combo.currentData(Qt.ItemDataRole.UserRole)
        if model_key:
            self.model_selected.emit(model_key)

    def _emit_hotkey_changed(self):
        new_hotkey = self.hotkey_input.text().strip()
        if new_hotkey:
            self.hotkey_input.clearFocus()
            self.hotkey_changed.emit(new_hotkey)

    def _set_checkbox_value(self, checkbox, value):
        previous = checkbox.blockSignals(True)
        checkbox.setChecked(value)
        checkbox.blockSignals(previous)

    def _set_combo_value(self, target_value):
        index = self.model_combo.findData(target_value, role=Qt.ItemDataRole.UserRole)
        if index == -1:
            return
        previous = self.model_combo.blockSignals(True)
        self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(previous)
