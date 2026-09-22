"""Dark instrument-panel theme with JetBrains Mono throughout."""
import os

from PyQt5.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette

BG = "#0d0f12"
PANEL = "#14171c"
PANEL2 = "#1a1e25"
RAISED = "#222731"
BORDER = "#2a303b"
TEXT = "#d8dee9"
DIM = "#7a8494"
FAINT = "#4a525f"
AMBER = "#ffb347"
AMBER_DIM = "#6b4a1c"
CYAN = "#5ec8e5"
GREEN = "#6fd08c"
RED = "#ff6b6b"
LCD_BG = "#120e07"

FONT_FAMILY = "JetBrains Mono"


ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def load_bundled_fonts():
    """Register the bundled JetBrains Mono so the app looks the same on any PC."""
    fonts = os.path.join(ASSETS, "fonts")
    if os.path.isdir(fonts):
        for name in os.listdir(fonts):
            if name.lower().endswith(".ttf"):
                QFontDatabase.addApplicationFont(os.path.join(fonts, name))


def pick_font_family() -> str:
    load_bundled_fonts()
    families = set(QFontDatabase().families())
    for name in (FONT_FAMILY, "JetBrainsMono", "Cascadia Mono", "Consolas"):
        if name in families:
            return name
    return "Monospace"


def mono(size: float = 10, bold: bool = False) -> QFont:
    f = QFont(FAMILY or FONT_FAMILY)
    f.setPointSizeF(size)
    f.setBold(bold)
    f.setStyleHint(QFont.Monospace)
    return f


FAMILY = None


def apply(app):
    global FAMILY
    FAMILY = pick_font_family()
    app.setFont(mono(10))
    pal = QPalette()
    for role, color in [
        (QPalette.Window, BG), (QPalette.Base, PANEL), (QPalette.AlternateBase, PANEL2),
        (QPalette.Text, TEXT), (QPalette.WindowText, TEXT), (QPalette.ButtonText, TEXT),
        (QPalette.Button, RAISED), (QPalette.Highlight, "#3a2c14"),
        (QPalette.HighlightedText, AMBER), (QPalette.ToolTipBase, PANEL2),
        (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, FAINT),
    ]:
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    icon = os.path.join(ASSETS, "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    apply_stylesheet(app)


STYLESHEET = """
* {{ font-family: "{FAMILY_CSS}"; }}
QWidget {{ color: {TEXT}; background: transparent; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {BG}; }}
QMainWindow::separator {{ background: {BORDER}; width: 1px; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}

QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#section {{ color: {DIM}; font-size: 8pt; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#badge {{ color: {AMBER}; border: 1px solid {AMBER_DIM}; border-radius: 4px;
               padding: 1px 6px; font-weight: bold; }}
QLabel#badgeCyan {{ color: {CYAN}; border: 1px solid #1f4a57; border-radius: 4px;
                   padding: 1px 6px; font-weight: bold; }}

QPushButton, QToolButton {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 12px; color: {TEXT};
}}
QPushButton:hover, QToolButton:hover {{ border-color: {AMBER_DIM}; background: #272d38; }}
QPushButton:pressed, QToolButton:pressed {{ background: #1b1f27; }}
QPushButton:disabled, QToolButton:disabled {{ color: {FAINT}; border-color: #1f242c; }}
QPushButton:checked, QToolButton:checked {{ background: #3a2c14; border-color: {AMBER}; color: {AMBER}; }}
QPushButton#primary {{ background: {AMBER}; color: #1a1206; border: none; font-weight: bold; }}
QPushButton#primary:hover {{ background: #ffc36e; }}
QPushButton#primary:disabled {{ background: {AMBER_DIM}; color: #2a1e0c; }}
QPushButton#danger {{ color: {RED}; }}
QPushButton#key {{ padding: 9px 4px; font-weight: bold; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 8px; selection-background-color: #3a2c14; selection-color: {AMBER};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {AMBER}; }}
QLabel#bigFreq {{ color: {AMBER}; font-size: 30pt; font-weight: bold; }}
QLineEdit#freqEntry {{ font-size: 20pt; padding: 6px 10px; color: {AMBER}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid {DIM}; margin-right: 6px; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; border: 1px solid {BORDER};
    selection-background-color: #3a2c14; selection-color: {AMBER}; outline: 0; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; background: {PANEL}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {DIM}; padding: 8px 18px; border: none;
               border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {AMBER}; border-bottom: 2px solid {AMBER}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QTableView {{ background: {PANEL}; alternate-background-color: #171b21; border: none;
             gridline-color: #1d222a; selection-background-color: #3a2c14;
             selection-color: {AMBER}; outline: 0; }}
QTableView::item {{ padding: 0 6px; }}
QHeaderView::section {{ background: {PANEL}; color: {DIM}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 6px; font-size: 8pt; }}
QTableCornerButton::section {{ background: {PANEL}; border: none; }}
QTableView::indicator {{ width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid {FAINT}; background: {PANEL2}; }}
QTableView::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid {FAINT}; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 7px;
    border: 1px solid {FAINT}; background: {PANEL2}; }}
QRadioButton::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}

QPlainTextEdit {{ background: {PANEL}; border: none; selection-background-color: #3a2c14; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {RAISED}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {RAISED}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QProgressBar {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;
               height: 10px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {AMBER}; border-radius: 4px; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {DIM}; }}
QStatusBar::item {{ border: none; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: #3a2c14; color: {AMBER}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QDialog {{ background: {BG}; }}
QSplitter::handle {{ background: transparent; }}
"""


def apply_stylesheet(app):
    values = {k: v for k, v in globals().items() if k.isupper()}
    values["FAMILY_CSS"] = FAMILY or FONT_FAMILY
    app.setStyleSheet(STYLESHEET.format(**values))
