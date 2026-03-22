from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
    QApplication,
)
import math

from .theme import (
    COLOR_FOREST_GREEN,
    COLOR_SAGE_LIGHT,
    COLOR_TAUPE,
    COLOR_CREAM,
    COLOR_DARK_SURFACE,
)


class WaveWidget(QWidget):
    """Barras verticales animadas estilo 'audio waveform'."""

    BAR_COUNT = 8
    BAR_WIDTH = 4
    BAR_SPACING = 3
    MAX_HEIGHT = 28
    MIN_HEIGHT = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        total_w = self.BAR_COUNT * (self.BAR_WIDTH + self.BAR_SPACING) - self.BAR_SPACING
        self.setFixedSize(total_w + 8, 40)
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_update)
        self._timer.start(80)  # ~12 fps, movimiento suave

    def _tick_update(self):
        self._tick += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = self._tick * 0.18
        cx = self.width() // 2
        cy = self.height() // 2
        total_w = self.BAR_COUNT * (self.BAR_WIDTH + self.BAR_SPACING) - self.BAR_SPACING
        x_start = cx - total_w // 2

        for i in range(self.BAR_COUNT):
            # Cada barra oscila con fase distinta para efecto de ola
            phase = i * (math.pi / (self.BAR_COUNT / 2))
            height = self.MIN_HEIGHT + (self.MAX_HEIGHT - self.MIN_HEIGHT) * (
                0.5 + 0.5 * math.sin(t + phase)
            )
            height = int(height)

            x = x_start + i * (self.BAR_WIDTH + self.BAR_SPACING)
            y = cy - height // 2

            color = QColor(COLOR_SAGE_LIGHT)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            # Barras con esquinas redondeadas
            painter.drawRoundedRect(x, y, self.BAR_WIDTH, height, 2, 2)


class RecordingPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self._setup_ui()
        self._center_on_screen()

    def _setup_ui(self):
        container = QWidget(self)
        container.setObjectName("popupContainer")
        container.setStyleSheet(f"""
            QWidget#popupContainer {{
                background-color: {COLOR_DARK_SURFACE};
                border-radius: 20px;
                border: 1px solid rgba(131, 169, 144, 0.2);
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # ── Botón cerrar (✕) ──────────────────────────────────
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(220, 80, 80, 0.25);
                color: #e06060;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(220, 80, 80, 0.55);
                color: #ffffff;
            }}
        """)
        self.close_btn.clicked.connect(self._on_cancel)

        # ── Waveform ──────────────────────────────────────────
        self.wave_widget = WaveWidget()

        # ── Botón stop (■) ────────────────────────────────────
        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(220, 80, 80, 0.85);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(220, 60, 60, 1.0);
            }}
        """)
        self.stop_btn.clicked.connect(self._on_stop)

        layout.addWidget(self.close_btn)
        layout.addWidget(self.wave_widget)
        layout.addWidget(self.stop_btn)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(container)

    def _center_on_screen(self):
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                self.move(
                    screen_geo.left() + (screen_geo.width() - self.width()) // 2,
                    screen_geo.bottom() - self.height() - 60,
                )

    def showEvent(self, event):
        self._center_on_screen()
        super().showEvent(event)

    def set_stop_callback(self, callback):
        # Mantenemos por retrocompatibilidad pero redirigimos
        self._stop_callback = callback

    def set_callbacks(self, on_stop, on_cancel=None):
        """
        on_stop   → se llama al pulsar ■ (confirmar grabación)
        on_cancel → se llama al pulsar ✕ (descartar grabación)
        """
        self._stop_callback = on_stop
        self._cancel_callback = on_cancel

    def _on_cancel(self):
        """X: detiene la grabación y cierra sin procesar."""
        if hasattr(self, "_cancel_callback") and self._cancel_callback:
            self._cancel_callback()
        self.hide()

    def _on_stop(self):
        """■: detiene la grabación y procesa el audio."""
        if hasattr(self, "_stop_callback") and self._stop_callback:
            self._stop_callback()
        self.hide()