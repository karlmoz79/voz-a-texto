# theme.py
# Contiene constantes visuales y estilos QSS globales para la interfaz

COLOR_FOREST_GREEN = "#406D5E"
COLOR_SAGE_LIGHT = "#83A990"
COLOR_TAUPE = "#A8937C"
COLOR_CREAM = "#E1D8C4"
COLOR_DARK_BASE = "#1E2220"  # Para fondo oscuro base
COLOR_DARK_SURFACE = "#252B28"  # Para superficies en modo oscuro

FONT_FAMILY = "Inter, 'Segoe UI', system-ui, sans-serif"

# Estilos unificados modernos y minimalistas sin bordes duros
STYLESHEET = f"""
QWidget#mainWindow {{
    background-color: {COLOR_DARK_SURFACE};
    border-radius: 12px;
}}
QWidget#sidebar {{
    background-color: {COLOR_FOREST_GREEN};
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
}}
QWidget#titleBar {{
    background-color: transparent;
}}
QLabel#appLogo {{
    color: {COLOR_CREAM};
    font-size: 28px;
    font-weight: 800;
    font-family: {FONT_FAMILY};
    padding: 10px 20px;
    letter-spacing: -0.5px;
}}
QListWidget#sidebarMenu {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget#sidebarMenu::item {{
    color: rgba(225, 216, 196, 0.7); /* COLOR_CREAM with opacity */
    padding: 12px 20px;
    font-size: 14px;
    font-family: {FONT_FAMILY};
    border-radius: 8px;
    margin: 4px 16px;
}}
QListWidget#sidebarMenu::item:hover {{
    background-color: rgba(225, 216, 196, 0.05); /* very low opacity COLOR_CREAM */
    cursor: pointinghand;
}}
QListWidget#sidebarMenu::item:selected {{
    background-color: rgba(225, 216, 196, 0.15); /* light COLOR_CREAM bg */
    color: {COLOR_CREAM};
    font-weight: 600;
}}
QLabel#sectionHeader {{
    color: {COLOR_TAUPE};
    font-size: 11px;
    font-weight: 700;
    font-family: {FONT_FAMILY};
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}

/* Base Form Inputs */
QComboBox, QLineEdit, QPlainTextEdit {{
    background-color: rgba(0, 0, 0, 0.15);
    border: 1px solid rgba(168, 147, 124, 0.2); /* COLOR_TAUPE subtle border */
    color: {COLOR_CREAM};
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 14px;
    font-family: {FONT_FAMILY};
    min-width: 150px;
}}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover {{
    background-color: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(131, 169, 144, 0.5); /* COLOR_SAGE_LIGHT hover border */
}}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {COLOR_SAGE_LIGHT};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
}}
QComboBox::down-arrow {{
    image: none; /* Quitamos la flecha por defecto, la pintaremos manual o con svg */
}}

/* List items inside combobox */
QComboBox QAbstractItemView {{
    background-color: {COLOR_DARK_BASE};
    border: 1px solid rgba(168, 147, 124, 0.2);
    border-radius: 6px;
    color: {COLOR_CREAM};
    selection-background-color: rgba(131, 169, 144, 0.15);
    selection-color: {COLOR_CREAM};
    padding: 4px;
}}

QPushButton.iconBtn {{
    background: transparent;
    color: {COLOR_TAUPE};
    font-size: 18px;
    border: none;
    border-radius: 6px;
}}
QPushButton.iconBtn:hover {{
    color: {COLOR_CREAM};
    background-color: rgba(225, 216, 196, 0.05);
}}

/* Primary Buttons */
QPushButton.primaryBtn {{
    background-color: {COLOR_SAGE_LIGHT};
    color: {COLOR_DARK_BASE};
    font-family: {FONT_FAMILY};
    font-size: 13px;
    font-weight: 600;
    padding: 8px 20px;
    border-radius: 6px;
    border: none;
}}
QPushButton.primaryBtn:hover {{
    background-color: #92bca0; /* Slightly lighter sage */
}}
QPushButton.primaryBtn:pressed {{
    background-color: #74967f; /* Slightly darker sage */
}}

/* Secondary Buttons */
QPushButton.secondaryBtn {{
    background-color: transparent;
    color: {COLOR_TAUPE};
    font-family: {FONT_FAMILY};
    font-size: 13px;
    font-weight: 500;
    padding: 8px 20px;
    border-radius: 6px;
    border: 1px solid {COLOR_TAUPE};
}}
QPushButton.secondaryBtn:hover {{
    color: {COLOR_CREAM};
    border-color: {COLOR_CREAM};
}}
QPushButton.secondaryBtn:pressed {{
    background-color: rgba(168, 147, 124, 0.1);
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(168, 147, 124, 0.3); /* COLOR_TAUPE handle */
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(168, 147, 124, 0.6);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
"""
