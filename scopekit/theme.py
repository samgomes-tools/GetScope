"""Tema visual padrão dos apps *Scope (azul-escuro, destaque azul-claro, botão verde)."""
import os
import tempfile

BG = "#1b2838"
HEADER = "#171a21"
PANEL = "#16202d"
PANEL_ALT = "#1a2533"
INPUT = "#0f1620"
INPUT_BORDER = "#2a3f5a"
TEXT = "#c7d5e0"
MUTED = "#8f98a0"
TITLE = "#ffffff"
ACCENT = "#66c0f4"
GREEN = "#a4d007"
WARN = "#ffcf6b"
ERROR = "#ff6b6b"
FONT = '"Motiva Sans", "Noto Sans", "Segoe UI", "Cantarell", "Arial"'
MONO = '"JetBrains Mono", "DejaVu Sans Mono", monospace'

_ARROWS = {}


def _arrow_png(direction="down", color=ACCENT):
    """Gera uma seta em PNG (bordas CSS viram quadrados em alguns estilos)."""
    key = (direction, color)
    if key in _ARROWS:
        return _ARROWS[key]
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPolygonF
    from PySide6.QtCore import Qt, QPointF
    pm = QPixmap(10, 10)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    if direction == "down":
        pts = [QPointF(1, 3), QPointF(9, 3), QPointF(5, 8)]
    else:
        pts = [QPointF(1, 7), QPointF(9, 7), QPointF(5, 2)]
    p.drawPolygon(QPolygonF(pts))
    p.end()
    d = os.path.join(tempfile.gettempdir(), f"scopekit-{os.getuid()}")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"arrow-{direction}-{color.strip('#')}.png")
    pm.save(path)
    _ARROWS[key] = path
    return path


def build_qss():
    down = _arrow_png("down")
    up = _arrow_png("up")
    return f"""
* {{ font-family: {FONT}; font-size: 10pt; color: {TEXT}; }}
QWidget {{ background: transparent; }}
QMainWindow, QDialog, QWidget#Root {{ background: {BG}; }}
QToolTip {{ background: #3d4450; color: #dcdedf; border: 1px solid #2a3f5a; padding: 4px 6px; }}
QLabel#Title {{ color: {TITLE}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Section {{ color: {ACCENT}; font-size: 9pt; font-weight: 700; letter-spacing: 1px; }}
QLabel#Key {{ color: {MUTED}; }}
QLabel#Val {{ color: {TEXT}; }}

/* ---- cabeçalho ---- */
QWidget#Header {{ background: {HEADER}; border-bottom: 1px solid #0e1116; }}
QLabel#AppName {{ color: #dcdedf; font-size: 15pt; font-weight: 800; letter-spacing: 3px; }}

QWidget#Toolbar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1f2c3b, stop:1 {BG});
                   border-bottom: 1px solid #0e141b; }}
QFrame#VSep {{ background: #2a3f5a; max-width: 1px; min-width: 1px; }}
QWidget#Side {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #213449, stop:0.35 {BG}, stop:1 {BG});
                border-left: 1px solid #0e141b; }}
QWidget#Banner {{ background: #3a2f1c; }}
QLabel#BannerText {{ color: {WARN}; }}
QWidget#Card {{ background: {PANEL}; border: 1px solid #22313f; }}
QWidget#DlgHead {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2a475e, stop:1 {BG}); }}
QLabel#DlgTitle {{ color: #ffffff; font-size: 13pt; font-weight: 800; letter-spacing: 1.5px; }}

/* ---- botões ---- */
QPushButton {{ background: #2a3f5a; color: {ACCENT}; border: none; border-radius: 3px;
               min-height: 32px; padding: 0 16px; font-weight: 600; }}
QPushButton:hover {{ background: {ACCENT}; color: #ffffff; }}
QPushButton:pressed {{ background: #417a9b; color: #ffffff; }}
QPushButton:disabled {{ background: #232d39; color: #4f5a66; }}
QPushButton[kind="green"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #75b022, stop:1 #588a1b);
                             color: #ffffff; font-weight: 700; }}
QPushButton[kind="green"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8ed629, stop:1 #6aa621); }}
QPushButton[kind="green"]:disabled {{ background: #2c3a22; color: #5d6b4c; }}
QPushButton[kind="blue"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #47bfff, stop:1 #1a44c2);
                            color: #ffffff; font-weight: 700; }}
QPushButton[kind="blue"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #66ccff, stop:1 #2a5ae0); }}
QPushButton[kind="blue"]:disabled {{ background: #1f2f45; color: #4f6070; }}
QPushButton[kind="danger"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #c43d3d, stop:1 #8f2424);
                              color: #ffffff; font-weight: 700; }}
QPushButton[kind="danger"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dd5050, stop:1 #a83030); }}
QPushButton[kind="danger"]:disabled {{ background: #3a2526; color: #6e5050; }}
QPushButton[kind="cancel"] {{ background: #3d4450; color: #dcdedf; }}
QPushButton[kind="cancel"]:hover {{ background: #4e5664; color: #ffffff; }}
QPushButton[kind="tool"] {{ background: transparent; color: {TEXT}; min-height: 30px; padding: 0 10px; font-weight: 600; }}
QPushButton[kind="tool"]:hover {{ background: #2a3f5a; color: #ffffff; }}
QPushButton[kind="tool"]:disabled {{ background: transparent; color: #4f5a66; }}
QPushButton[kind="nav"] {{ background: transparent; color: #dcdedf; font-size: 11pt; font-weight: 800;
                           min-height: 54px; max-height: 54px; padding: 0 14px; border-radius: 0;
                           border-bottom: 3px solid transparent; letter-spacing: 1px; }}
QPushButton[kind="nav"]:hover {{ color: #ffffff; background: transparent; }}
QPushButton[kind="nav"][active="true"] {{ color: {ACCENT}; border-bottom: 3px solid #1a9fff; }}
QPushButton[kind="pill"] {{ border-radius: 13px; min-height: 26px; max-height: 26px; padding: 0 12px;
                            font-size: 9pt; font-weight: 700; background: #1f3a20; color: {GREEN}; }}
QPushButton[kind="pill"][state="warn"] {{ background: #3a2f1c; color: {WARN}; }}
QPushButton[kind="pill"][state="error"] {{ background: #3a1c1c; color: {ERROR}; }}
QPushButton[kind="pill"]:hover {{ background: #2a475e; color: #ffffff; }}
QPushButton[kind="big"] {{ min-height: 46px; font-size: 11.5pt; font-weight: 800; letter-spacing: 1px; }}

/* ---- campos ---- */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{ background: {INPUT}; border: 1px solid {INPUT_BORDER};
    border-radius: 3px; padding: 4px 8px; min-height: 24px; selection-background-color: #2a475e; color: {TEXT}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit#BigUrl {{ font-size: 11.5pt; min-height: 34px; padding: 4px 12px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{ background: #3d4450; color: #dcdedf; border: 1px solid #2a3f5a;
    selection-background-color: #dcdedf; selection-color: #171a21; outline: none; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 18px; background: transparent; }}
QSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QPlainTextEdit#Console {{ font-family: {MONO}; font-size: 9pt; background: #0b0f14; color: #a7b6c2; border-color: #1c2733; }}

QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator, QTreeWidget::indicator {{ width: 15px; height: 15px;
    background: {INPUT}; border: 1px solid #4b6477; border-radius: 2px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QTreeWidget::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,fx:0.5,fy:0.5,
    stop:0 {ACCENT}, stop:0.55 {ACCENT}, stop:0.65 {INPUT}); border-color: {ACCENT}; }}

/* ---- listas e tabelas ---- */
QTreeWidget, QTableWidget, QListWidget {{ background: {PANEL}; alternate-background-color: {PANEL_ALT};
    border: 1px solid #0e141b; outline: none; }}
QTreeWidget::item, QTableWidget::item, QListWidget::item {{ padding: 4px 2px; min-height: 26px; border: none; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: #223246; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3d6c8d, stop:1 #2a475e); color: #ffffff; }}
QHeaderView {{ background: #1f2c3b; }}
QHeaderView::section {{ background: #1f2c3b; color: {MUTED}; font-size: 8pt; font-weight: 700; border: none;
    border-right: 1px solid #16202d; padding: 6px 8px; text-transform: uppercase; }}

QProgressBar {{ background: {INPUT}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 4px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #47bfff, stop:1 #1a44c2); }}
QProgressBar[state="done"]::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #a4d007, stop:1 #588a1b); }}
QProgressBar[state="error"]::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff6b6b, stop:1 #c43d3d); }}
QProgressBar[state="paused"]::chunk {{ background: #4b6477; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #3d4b5c; border-radius: 4px; min-height: 30px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #3d4b5c; border-radius: 4px; min-width: 30px; margin: 2px; }}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollArea {{ border: none; }}

QMenu {{ background: #3d4450; border: 1px solid #2a3f5a; padding: 4px 0; }}
QMenu::item {{ padding: 6px 22px; color: #dcdedf; }}
QMenu::item:selected {{ background: #dcdedf; color: #171a21; }}
QMenu::separator {{ height: 1px; background: #2a3f5a; margin: 4px 8px; }}
QStatusBar {{ background: {HEADER}; color: {MUTED}; border-top: 1px solid #0e1116; }}
QStatusBar QLabel {{ color: {MUTED}; }}
QSplitter::handle {{ background: #0e141b; }}
"""
