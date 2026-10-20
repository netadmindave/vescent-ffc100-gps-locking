"""Dark instrument theme (matches the mockups)."""
from __future__ import annotations

BG = "#0E1115"
CHROME = "#12161B"
PANEL = "#161A20"
INPUT = "#0F1318"
LINE = "#2A313B"
LINE2 = "#39424E"
TEXT = "#E7EAEE"
MUTED = "#9AA4B0"
DIM = "#7F8A97"
BLUE = "#5AA2FF"
BLUE_BTN = "#2F6FD6"
OK = "#62E3AE"
OK_BG = "#11352A"
WARN = "#FFC266"
WARN_BG = "#3A2C12"
BAD = "#FF8F94"
BAD_BG = "#3D1A1D"
IDLE = "#B3BCC7"
IDLE_BG = "#252B33"
TRACE = ["#F4D23C", "#3FD5E8", "#E35FD0", "#5A8CFF"]   # Rigol channel colours
PLOT1, PLOT2, PLOT3 = "#7DB5FF", "#FFC266", "#62E3AE"

FONT_SANS = "IBM Plex Sans, Segoe UI, Arial"
FONT_MONO = "IBM Plex Mono, Consolas, Menlo, monospace"

QSS = f"""
* {{ font-family: {FONT_SANS}; font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; border: none; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#chrome {{ background: {CHROME}; border-bottom: 1px solid {LINE}; }}
QLabel#panelTitle {{ font-size: 11px; font-weight: 600; letter-spacing: 1px; color: #C9D0D8; }}
QLabel#lbl {{ font-size: 12px; color: {MUTED}; }}
QLabel#ro {{ font-family: {FONT_MONO}; font-size: 14px; }}
QLabel#big {{ font-family: {FONT_MONO}; font-size: 24px; font-weight: 500; }}
QLabel#h1 {{ font-size: 21px; font-weight: 600; }}
QLabel#mono {{ font-family: {FONT_MONO}; font-size: 12px; color: {MUTED}; }}
QLabel#hint {{ font-size: 12px; color: #A9B4C2; background: #161C24; border-radius: 6px; padding: 6px 9px; }}
QLabel#info {{ font-size: 12px; color: #B9C6D6; background: #18202B; border-radius: 6px; padding: 6px 9px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {INPUT}; border: 1px solid {LINE2}; border-radius: 6px; padding: 5px 8px;
    font-family: {FONT_MONO}; font-size: 13px; min-height: 22px; selection-background-color: {BLUE_BTN}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {BLUE}; }}
QLineEdit[changed="true"], QDoubleSpinBox[changed="true"], QComboBox[changed="true"] {{ border-color: {WARN}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {LINE2}; selection-background-color: #2A3442; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px; border: none; subcontrol-origin: border; }}
QPushButton {{ background: #232A35; border: 1px solid #3A4350; border-radius: 6px; padding: 6px 12px;
    font-weight: 500; min-height: 20px; }}
QPushButton:hover {{ background: #2B3340; }}
QPushButton:disabled {{ color: #5E6773; border-color: #2C333D; background: #1A1F26; }}
QPushButton[kind="primary"] {{ background: {BLUE_BTN}; border-color: {BLUE_BTN}; color: white; }}
QPushButton[kind="danger"] {{ background: #3A1E22; border-color: #7A3038; color: #FFD3D6; }}
QPushButton[kind="ok"] {{ background: #12402F; border-color: #1F6B4E; color: #7AF0BE; }}
QPushButton[kind="primary"]:disabled, QPushButton[kind="danger"]:disabled, QPushButton[kind="ok"]:disabled {{
    color: #5E6773; border-color: #2C333D; background: #1A1F26; }}
QPushButton[seg="true"] {{ border-radius: 0; background: {CHROME}; color: #A3ACB8; }}
QPushButton[seg="true"]:checked {{ background: #2A3442; color: white; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {LINE2}; border-radius: 3px; background: {INPUT}; }}
QCheckBox::indicator:checked {{ background: {BLUE_BTN}; border-color: {BLUE_BTN}; }}
QTableWidget, QListWidget, QTreeWidget {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 6px;
    gridline-color: #20262E; font-family: {FONT_MONO}; font-size: 12px; }}
QHeaderView::section {{ background: {CHROME}; color: {MUTED}; border: none; border-bottom: 1px solid {LINE};
    padding: 5px; font-family: {FONT_SANS}; font-size: 11px; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: #22303F; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: #A3ACB8; padding: 8px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: white; border-bottom: 2px solid {BLUE}; }}
QProgressBar {{ background: {INPUT}; border: 1px solid {LINE2}; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {BLUE_BTN}; border-radius: 4px; }}
QSlider::groove:horizontal {{ height: 6px; background: {LINE2}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; margin: -6px 0; border-radius: 8px; background: {BLUE}; }}
QSlider::sub-page:horizontal {{ background: {BLUE_BTN}; border-radius: 3px; }}
QMenuBar {{ background: {CHROME}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: #2A3442; }}
QMenu {{ background: {PANEL}; border: 1px solid {LINE2}; }}
QStatusBar {{ background: #0B0E12; border-top: 1px solid {LINE}; }}
QStatusBar QLabel {{ font-family: {FONT_MONO}; font-size: 11px; color: {MUTED}; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {LINE2}; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {LINE2}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

PILL = {
    "ok": (OK_BG, OK), "warn": (WARN_BG, WARN), "bad": (BAD_BG, BAD), "idle": (IDLE_BG, IDLE),
}
