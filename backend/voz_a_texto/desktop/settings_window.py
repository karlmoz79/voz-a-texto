from PySide6.QtCore import Qt, Signal, Property, QRectF, QPoint, QTimer
from PySide6.QtGui import (
    QKeyEvent,
    QKeySequence,
    QPainter,
    QColor,
    QBrush,
    QPen,
    QPainterPath,
    QIcon,
    QFont,
    QMouseEvent,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QProgressBar,
)

from ..models import MODEL_PROFILES
from .state import STATUS_LOADING, STATUS_RECORDING, status_label
from .theme import (
    STYLESHEET,
    COLOR_FOREST_GREEN,
    COLOR_SAGE_LIGHT,
    COLOR_TAUPE,
    COLOR_CREAM,
    COLOR_DARK_SURFACE,
    COLOR_DARK_BASE,
)

# ======================= Custom Widgets =========================


class HotkeyInputWidget(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("Toca las teclas...")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
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
            key_str = QKeySequence(key).toString(
                QKeySequence.SequenceFormat.PortableText
            )
            if key_str:
                parts.append(key_str)

        if parts:
            self.setText(" + ".join(parts))
        event.accept()


class CustomComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLOR_TAUPE))
        # Draw a custom arrow at the right side
        rect = self.rect()
        arrow_w = 8
        arrow_h = 5
        x = rect.width() - 18
        y = rect.height() // 2 - arrow_h // 2 + 1
        poly = QPolygon()
        poly.append(QPoint(x, y))
        poly.append(QPoint(x + arrow_w, y))
        poly.append(QPoint(x + arrow_w // 2, y + arrow_h))
        p.drawPolygon(poly)


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = (
            QColor(COLOR_SAGE_LIGHT)
            if self.isChecked()
            else QColor("rgba(0, 0, 0, 0.2)")
        )
        knob_color = (
            QColor(COLOR_DARK_SURFACE) if self.isChecked() else QColor(COLOR_TAUPE)
        )

        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 13, 13)
        p.fillPath(path, QBrush(bg_color))

        knob_radius = 10
        margin = 3
        # Calculate knob X position
        x_calc = (
            rect.width() - (knob_radius * 2) - margin if self.isChecked() else margin
        )

        knob_rect = QRectF(x_calc, margin, knob_radius * 2, knob_radius * 2)

        # Subtle drop shadow for knob
        shadow_rect = QRectF(x_calc, margin + 1, knob_radius * 2, knob_radius * 2)
        p.setBrush(QColor(0, 0, 0, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(shadow_rect)

        p.setBrush(QBrush(knob_color))
        p.drawEllipse(knob_rect)


class FormRow(QWidget):
    def __init__(self, label_text, widget, icon=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {COLOR_CREAM}; font-size: 14px; font-weight: 500;")

        if icon:
            info_icon = QLabel("ⓘ")
            info_icon.setStyleSheet(f"color: {COLOR_TAUPE}; font-size: 14px;")
            if isinstance(icon, str):
                info_icon.setToolTip(icon)
            layout.addWidget(lbl)
            layout.addWidget(info_icon)
            layout.addStretch()
        else:
            layout.addWidget(lbl)
            layout.addStretch()

        layout.addWidget(widget)


# ======================= Main Window =========================


class SettingsWindow(QWidget):
    model_selected = Signal(str)
    native_typing_toggled = Signal(bool)
    autostart_toggled = Signal(bool)
    export_requested = Signal()
    clear_requested = Signal()
    delete_model_requested = Signal(str)
    hotkey_changed = Signal(str)
    mic_selected = Signal(str)
    language_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoxFlow")
        self.resize(800, 600)

        # Frameless Window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Core data
        self._current_hotkey_text = ""
        self._drag_pos = None
        self._was_loading_model = False

        # Container for shadow effect
        self.main_container = QWidget(self)
        self.main_container.setObjectName("mainWindow")
        self.main_container.setStyleSheet(STYLESHEET)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.main_container.setGraphicsEffect(shadow)

        root_outer = QVBoxLayout(self)
        root_outer.setContentsMargins(20, 20, 20, 20)
        root_outer.addWidget(self.main_container)

        root_layout = QHBoxLayout(self.main_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---------------- SIDEBAR ----------------
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 24, 0, 24)

        self.logo_lbl = QLabel("VoxFlow")
        self.logo_lbl.setObjectName("appLogo")
        self.logo_lbl.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        sidebar_layout.addWidget(self.logo_lbl)

        self.menu_list = QListWidget()
        self.menu_list.setObjectName("sidebarMenu")
        self.menu_list.setCursor(Qt.CursorShape.PointingHandCursor)
        # Typographic minimalist menu items
        self.menu_items = [
            ("Inicio", 0),
            ("Modelos", 1),
            ("Historial", 2),
            ("Avanzado", 3),
            ("Acerca de", 4),
        ]
        for name, page_idx in self.menu_items:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, page_idx)
            self.menu_list.addItem(item)
        self.menu_list.setCurrentRow(0)
        self.menu_list.currentRowChanged.connect(self._change_page)

        sidebar_layout.addWidget(self.menu_list)

        # Bottom left status
        self.model_status_lbl = QLabel("● Parakeet V3")
        self.model_status_lbl.setStyleSheet(
            f"color: {COLOR_CREAM}; font-size: 12px; font-weight: 500; padding: 10px 20px; opacity: 0.8;"
        )
        sidebar_layout.addWidget(self.model_status_lbl)

        root_layout.addWidget(self.sidebar)

        # ---------------- MAIN CONTENT ----------------
        self.content_area = QWidget()
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Top Bar (Close Button & Drag Handle implicitly)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(40, 40)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {COLOR_TAUPE}; border: none; font-size: 16px; border-top-right-radius: 12px; }}
            QPushButton:hover {{ color: {COLOR_CREAM}; background-color: rgba(255, 90, 90, 0.4); }}
        """)
        self.close_btn.clicked.connect(self.close)
        top_bar.addWidget(self.close_btn)
        content_layout.addLayout(top_bar)

        self.stack = QStackedWidget()
        self._build_inicio_page()        # 0: Inicio
        self._build_modelos_page()       # 1: Modelos
        self._build_historial_page()     # 2: Historial
        self._build_avanzado_page()      # 3: Avanzado
        self._build_acerca_page()        # 4: Acerca de

        content_layout.addWidget(self.stack)

        # Bottom right status
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(
            "color: #FF6B6B; font-size: 11px; padding: 0px 32px;"
        )
        self.error_label.hide()

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.error_label)
        bottom_layout.addStretch()

        import datetime
        year = datetime.datetime.now().year
        self.footer_lbl = QLabel(f"© {year} VoxFlow. Todos los derechos reservados. • v0.1.0")
        self.footer_lbl.setStyleSheet(
            f"color: {COLOR_TAUPE}; font-size: 11px; padding: 10px 32px;"
        )
        bottom_layout.addWidget(self.footer_lbl)

        content_layout.addLayout(bottom_layout)

        root_layout.addWidget(self.content_area)

        # Functional mappings
        self.status_value = QLabel("Listo")

        # Connections
        self.hotkey_apply_btn.clicked.connect(self._emit_hotkey_changed)
        self.hotkey_input.returnPressed.connect(self._emit_hotkey_changed)
        self.model_combo.currentIndexChanged.connect(self._emit_model_selected)
        self.native_typing_checkbox.toggled.connect(self.native_typing_toggled)
        self.autostart_checkbox.toggled.connect(self.autostart_toggled.emit)
        self.export_button.clicked.connect(self._emit_export_requested)
        self.clear_button.clicked.connect(self._emit_clear_requested)
        self.delete_model_btn.clicked.connect(self._emit_delete_model_requested)
        self.mic_combo.currentTextChanged.connect(self._emit_mic_selected)
        self.lang_combo.currentIndexChanged.connect(self._emit_language_selected)

    # ---------- Frameless Window Drag Support ----------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked inside a widget that handles mousePress (like input, button)
            child = self.childAt(event.position().toPoint())
            if isinstance(
                child,
                (
                    QPushButton,
                    QAbstractButton,
                    QLineEdit,
                    QComboBox,
                    QListWidget,
                    QPlainTextEdit,
                    QSlider,
                ),
            ):
                return

            # Start drag
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()

    # ----------------------------------------------------

    def _build_inicio_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 0, 32, 24)
        layout.setSpacing(16)

        # INICIO
        h1 = QLabel("INICIO")
        h1.setObjectName("sectionHeader")
        layout.addWidget(h1)

        self.current_model_label = QLabel("Modelo actual: Cargando...")
        self.current_model_label.setStyleSheet(f"color: {COLOR_FOREST_GREEN}; font-size: 13px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(self.current_model_label)

        self.vu_meter = QProgressBar()
        self.vu_meter.setRange(0, 100)
        self.vu_meter.setFixedHeight(4)
        self.vu_meter.setTextVisible(False)
        self.vu_meter.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_FOREST_GREEN};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.vu_meter)

        self.live_transcript_view = QPlainTextEdit()
        self.live_transcript_view.setReadOnly(True)
        self.live_transcript_view.setPlaceholderText("La transcripción actual o más reciente aparecerá aquí...")
        self.live_transcript_view.setMinimumHeight(150)
        self.live_transcript_view.setStyleSheet("""
            QPlainTextEdit {
                font-size: 15px; 
            }
        """)
        layout.addWidget(self.live_transcript_view)

        inicio_actions_layout = QHBoxLayout()
        inicio_actions_layout.setContentsMargins(0, 0, 0, 16)
        
        info_lbl = QLabel("Este texto es temporal. Se borra tras iniciar nueva grabación.")
        info_lbl.setStyleSheet(f"color: {COLOR_TAUPE}; font-size: 12px; opacity: 0.8;")
        
        self.copy_inicio_btn = QPushButton("Copiar texto")
        self.copy_inicio_btn.setProperty("class", "secondaryBtn")
        self.copy_inicio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_inicio_btn.clicked.connect(self._copy_inicio_transcript)

        inicio_actions_layout.addWidget(info_lbl)
        inicio_actions_layout.addStretch()
        inicio_actions_layout.addWidget(self.copy_inicio_btn)
        layout.addLayout(inicio_actions_layout)

        # Controles debajo de la caja de texto
        self.mic_combo = CustomComboBox()
        layout.addWidget(FormRow("Micrófono", self.mic_combo))

        self.lang_combo = CustomComboBox()
        self.lang_combo.addItems(["Auto-detectar", "Español", "Inglés"])
        self.lang_combo.setToolTip(
            "⚠️ 'Auto-detectar' hace la transcripción mucho más lenta en CPU.\n"
            "Se recomienda seleccionar un idioma fijo."
        )
        lang_tooltip = "Forzar un idioma evita la detección automática,\nque es muy lenta en CPU (puede tardar 10-20s extra)."
        layout.addWidget(FormRow("Forzar Idioma (Whisper)", self.lang_combo, icon=lang_tooltip))

        self.native_typing_checkbox = ToggleSwitch()
        layout.addWidget(FormRow("Dictado Nativo", self.native_typing_checkbox))

        # Atajo
        atajo_container = QWidget()
        atajo_layout = QHBoxLayout(atajo_container)
        atajo_layout.setContentsMargins(0, 0, 0, 0)
        self.hotkey_input = HotkeyInputWidget()
        self.hotkey_apply_btn = QPushButton("⟳")
        self.hotkey_apply_btn.setProperty("class", "iconBtn")
        self.hotkey_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        atajo_layout.addWidget(self.hotkey_input)
        atajo_layout.addWidget(self.hotkey_apply_btn)
        tooltip_text = "Para cambiar tu combinación de teclas, da clic en el cuadro, presiona la combinación deseada y \nluego pulsa el botón con la flecha curva (Actualizar) para que quede activa.\nReinicia la aplicación si usaste Wayland o tienes un conflicto en Linux."
        layout.addWidget(FormRow("Atajo de Transcripción", atajo_container, icon=tooltip_text))



        layout.addStretch()
        self.stack.addWidget(page)

    def _build_modelos_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 0, 32, 32)
        layout.setSpacing(16)

        h1 = QLabel("MODELOS")
        h1.setObjectName("sectionHeader")
        layout.addWidget(h1)

        self.avail_combo = CustomComboBox()
        for profile in MODEL_PROFILES.values():
            self.avail_combo.addItem(profile.label, profile.key)

        self.btn_use_avail = QPushButton("Descargar / Usar")
        self.btn_use_avail.setProperty("class", "primaryBtn")
        self.btn_use_avail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_use_avail.clicked.connect(self._emit_use_avail_model)

        avail_layout = QHBoxLayout()
        avail_layout.setContentsMargins(0, 0, 0, 0)
        avail_layout.addWidget(self.avail_combo)
        avail_layout.addWidget(self.btn_use_avail)

        avail_wrapper = QWidget()
        avail_wrapper.setLayout(avail_layout)

        layout.addWidget(FormRow("Modelos Disponibles", avail_wrapper))

        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 0)
        self.download_progress.setFixedHeight(2)
        self.download_progress.setTextVisible(False)
        self.download_progress.setStyleSheet(
            "QProgressBar { background-color: rgba(0,0,0,0.2); border: none; }"
            "QProgressBar::chunk { background-color: #4CAF50; }"
        )
        self.download_progress.hide()

        self.download_success_lbl = QLabel("✓ Modelo listo y descargado.")
        self.download_success_lbl.setStyleSheet("color: #4CAF50; font-size: 12px; margin-left: 16px;")
        self.download_success_lbl.hide()

        layout.addWidget(self.download_progress)
        layout.addWidget(self.download_success_lbl)

        self.model_combo = CustomComboBox()
        # the model_combo items will be populated dynamically in apply_state
        layout.addWidget(FormRow("Modelo Activo", self.model_combo))

        self.delete_model_btn = QPushButton("Eliminar modelo de la PC")
        self.delete_model_btn.setProperty("class", "secondaryBtn")
        self.delete_model_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_model_btn.setStyleSheet("""
            QPushButton {
                color: #FF6B6B; 
                border: 1px solid rgba(255, 107, 107, 0.3); 
                background: transparent; 
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 107, 107, 0.1);
            }
        """)

        tooltip_text = "Libera el espacio en disco borrando el modelo actualmente activo."
        layout.addWidget(FormRow("Almacenamiento Local", self.delete_model_btn, icon=tooltip_text))

        self.delete_success_lbl = QLabel("✓ Modelo borrado exitosamente del disco duro.")
        self.delete_success_lbl.setStyleSheet("color: #4CAF50; font-size: 12px; margin-left: 16px;")
        self.delete_success_lbl.hide()

        layout.addWidget(self.delete_success_lbl)

        layout.addStretch()
        self.stack.addWidget(page)

    def _build_avanzado_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 0, 32, 32)
        layout.setSpacing(16)

        h1 = QLabel("AVANZADO")
        h1.setObjectName("sectionHeader")
        layout.addWidget(h1)

        self.autostart_checkbox = ToggleSwitch()
        self.autostart_checkbox.setChecked(False)
        layout.addWidget(FormRow("Iniciar con la sesión", self.autostart_checkbox))

        layout.addStretch()
        self.stack.addWidget(page)

    def _build_historial_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 0, 32, 24)
        layout.setSpacing(16)

        h1 = QLabel("HISTORIAL")
        h1.setObjectName("sectionHeader")
        layout.addWidget(h1)

        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        layout.addWidget(self.transcript_view)

        self.export_button = QPushButton("Exportar texto")
        self.export_button.setProperty("class", "primaryBtn")
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button = QPushButton("Borrar historial")
        self.clear_button.setProperty("class", "primaryBtn")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.clear_button)
        h_layout.addStretch()
        h_layout.addWidget(self.export_button)
        layout.addLayout(h_layout)

        self.stack.addWidget(page)

    def _build_acerca_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 0, 32, 32)
        layout.setSpacing(16)

        h1 = QLabel("ACERCA DE")
        h1.setObjectName("sectionHeader")
        layout.addWidget(h1)

        lbl = QLabel(
            "VoxFlow\nVersión 0.7.12\n\nDiseñado con mentalidad local y alta estética."
        )
        lbl.setStyleSheet(f"color: {COLOR_CREAM}; font-size: 14px; line-height: 1.5;")
        layout.addWidget(lbl)

        layout.addStretch()
        self.stack.addWidget(page)

    def _change_page(self, index):
        if 0 <= index < len(self.menu_items):
            page_idx = self.menu_items[index][1]
            self.stack.setCurrentIndex(page_idx)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def apply_state(self, shell_state):
        self.status_value.setText(status_label(shell_state.status))
        self.model_status_lbl.setText(f"● {status_label(shell_state.status)}")

        if not self.hotkey_input.hasFocus():
            self.hotkey_input.setText(shell_state.hotkey)
            self._current_hotkey_text = shell_state.hotkey

        current_keys = [self.model_combo.itemData(i, Qt.ItemDataRole.UserRole) for i in range(self.model_combo.count())]
        new_keys = list(shell_state.downloaded_models)
        if current_keys != new_keys:
            previous = self.model_combo.blockSignals(True)
            self.model_combo.clear()
            from ..models import get_model_profile
            for key in shell_state.downloaded_models:
                try:
                    profile = get_model_profile(key)
                    self.model_combo.addItem(profile.label, profile.key)
                except Exception:
                    pass
            self.model_combo.blockSignals(previous)

        self.model_combo.setEnabled(shell_state.status != STATUS_LOADING)
        self.avail_combo.setEnabled(shell_state.status != STATUS_LOADING)
        self.btn_use_avail.setEnabled(shell_state.status != STATUS_LOADING)
        self.delete_model_btn.setEnabled(shell_state.status != STATUS_LOADING)

        is_loading = (shell_state.status == STATUS_LOADING)
        if is_loading:
            self.download_progress.show()
            self.download_success_lbl.hide()
            self._was_loading_model = True
        else:
            self.download_progress.hide()
            if self._was_loading_model:
                self._was_loading_model = False
                if not shell_state.error_message:
                    self.download_success_lbl.show()
                    QTimer.singleShot(4000, self.download_success_lbl.hide)

        self._set_combo_value(self.model_combo, shell_state.active_model)
        self._set_combo_value(self.avail_combo, shell_state.active_model)
        
        if shell_state.active_model:
            profile = MODEL_PROFILES.get(shell_state.active_model)
            if profile:
                self.current_model_label.setText(f"Modelo en uso: {profile.label}")
        else:
            self.current_model_label.setText("Modelo en uso: Ninguno / Cargando...")

        self._set_checkbox_value(
            self.native_typing_checkbox, shell_state.native_typing_enabled
        )
        self._set_checkbox_value(self.autostart_checkbox, shell_state.launch_at_login)
        self.export_button.setEnabled(shell_state.can_export)

        if shell_state.last_transcript:
            self.transcript_view.setPlainText(shell_state.last_transcript)
        else:
            self.transcript_view.clear()

        if shell_state.current_transcript:
            self.live_transcript_view.setPlainText(shell_state.current_transcript)
        else:
            self.live_transcript_view.clear()

        self.mic_combo.blockSignals(True)
        if self.mic_combo.count() != len(shell_state.input_devices_list):
            self.mic_combo.clear()
            self.mic_combo.addItems(shell_state.input_devices_list)
        if shell_state.input_device and self.mic_combo.findText(shell_state.input_device) >= 0:
            self.mic_combo.setCurrentText(shell_state.input_device)
        self.mic_combo.blockSignals(False)

        self.lang_combo.blockSignals(True)
        is_whisper = "fastconformer" not in shell_state.active_model and "parakeet" not in shell_state.active_model.lower()
        self.lang_combo.setEnabled(is_whisper)
        lang_idx = {"auto": 0, "es": 1, "en": 2}.get(shell_state.language, 0)
        self.lang_combo.setCurrentIndex(lang_idx)
        self.lang_combo.blockSignals(False)

        if shell_state.status != STATUS_RECORDING:
            self.vu_meter.setValue(0)

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

    def show_delete_success(self):
        self.delete_success_lbl.show()
        QTimer.singleShot(4000, self.delete_success_lbl.hide)

    def _emit_model_selected(self):
        model_key = self.model_combo.currentData(Qt.ItemDataRole.UserRole)
        if model_key:
            self.model_selected.emit(model_key)

    def _emit_hotkey_changed(self):
        new_hotkey = self.hotkey_input.text()
        if new_hotkey:
            self.hotkey_apply_btn.clearFocus()
            self.hotkey_input.clearFocus()
            self.hotkey_changed.emit(new_hotkey)

    def _emit_mic_selected(self, mic_name):
        self.mic_selected.emit(mic_name)
    
    def _emit_language_selected(self, index):
        lang = {0: "auto", 1: "es", 2: "en"}.get(index, "auto")
        self.language_selected.emit(lang)

    def _copy_inicio_transcript(self):
        self.copy_inicio_btn.clearFocus()
        text = self.live_transcript_view.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.copy_inicio_btn.setText("✓ Copiado")
            QTimer.singleShot(2000, lambda: self.copy_inicio_btn.setText("Copiar texto"))

    def _emit_export_requested(self):
        self.export_button.clearFocus()
        self.export_requested.emit()

    def _emit_clear_requested(self):
        self.clear_button.clearFocus()
        self.clear_requested.emit()

    def _emit_delete_model_requested(self):
        self.delete_model_btn.clearFocus()
        model_key = self.model_combo.currentData(Qt.ItemDataRole.UserRole)
        if model_key:
            self.delete_model_requested.emit(model_key)

    def _emit_use_avail_model(self):
        self.btn_use_avail.clearFocus()
        model_key = self.avail_combo.currentData(Qt.ItemDataRole.UserRole)
        if model_key:
            self.model_selected.emit(model_key)

    def _set_checkbox_value(self, checkbox, value):
        previous = checkbox.blockSignals(True)
        checkbox.setChecked(value)
        checkbox.blockSignals(previous)

    def _set_combo_value(self, combo, target_value):
        index = combo.findData(target_value, role=Qt.ItemDataRole.UserRole)
        if index == -1:
            return
        previous = combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(previous)
