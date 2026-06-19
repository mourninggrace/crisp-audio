"""QSS colour themes for Crisp.

Each theme is a dict with a ``name``, a ``stylesheet`` (QSS string), and an
optional ``dark`` flag.  The empty stylesheet is "System Default".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Theme:
    key: str
    name: str
    dark: bool
    stylesheet: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dark(key: str, name: str, bg: str, fg: str, accent: str, alt: str,
          border: str, hover: str, pressed: str) -> Theme:
    """Build a complete dark theme from a small palette."""
    qss = f"""
QWidget {{
    background-color: {bg};
    color: {fg};
    font-size: 12px;
}}
QMainWindow, QDialog {{
    background-color: {bg};
}}
QGroupBox {{
    border: 1px solid {border};
    border-radius: 4px;
    margin-top: 6px;
    padding-top: 6px;
    color: {fg};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    color: {accent};
}}
QGroupBox::indicator {{
    width: 13px; height: 13px;
}}
QSplitter::handle {{
    background-color: {border};
}}
QSplitter::handle:hover {{
    background-color: {accent};
}}
QTabWidget::pane {{
    border: 1px solid {border};
}}
QTabBar::tab {{
    background: {alt};
    color: {fg};
    padding: 4px 10px;
    border: 1px solid {border};
    border-bottom: none;
    border-radius: 3px 3px 0 0;
}}
QTabBar::tab:selected {{
    background: {bg};
    color: {accent};
    border-bottom: 1px solid {bg};
}}
QTabBar::tab:hover:!selected {{
    background: {hover};
}}
QPushButton {{
    background-color: {alt};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px 10px;
}}
QPushButton:hover {{
    background-color: {hover};
    border-color: {accent};
}}
QPushButton:pressed {{
    background-color: {pressed};
}}
QPushButton:disabled {{
    color: {border};
}}
QComboBox {{
    background-color: {alt};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 2px 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {alt};
    color: {fg};
    selection-background-color: {accent};
    selection-color: {bg};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {border};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 12px; height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: {accent};
}}
QSlider::sub-page:horizontal {{
    background: {accent};
    border-radius: 2px;
}}
QProgressBar {{
    background-color: {alt};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    color: {fg};
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 3px;
}}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {border};
    border-radius: 2px;
    background: {alt};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}
QRadioButton::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {border};
    border-radius: 7px;
    background: {alt};
}}
QRadioButton::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}
QScrollBar:vertical {{
    background: {alt};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {accent};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QLabel {{
    color: {fg};
}}
QStatusBar {{
    background: {alt};
    color: {fg};
    border-top: 1px solid {border};
}}
QMenuBar {{
    background: {alt};
    color: {fg};
    border-bottom: 1px solid {border};
}}
QMenuBar::item:selected {{
    background: {hover};
}}
QMenu {{
    background: {alt};
    color: {fg};
    border: 1px solid {border};
}}
QMenu::item:selected {{
    background: {accent};
    color: {bg};
}}
QListWidget {{
    background: {alt};
    color: {fg};
    border: 1px solid {border};
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background: {accent};
    color: {bg};
}}
QDialog {{
    background: {bg};
}}
"""
    return Theme(key=key, name=name, dark=True, stylesheet=qss.strip())


def _light(key: str, name: str, bg: str, fg: str, accent: str, alt: str,
           border: str, hover: str, pressed: str) -> Theme:
    t = _dark(key, name, bg, fg, accent, alt, border, hover, pressed)
    return Theme(key=t.key, name=t.name, dark=False, stylesheet=t.stylesheet)


# ---------------------------------------------------------------------------
# Theme catalogue
# ---------------------------------------------------------------------------

THEMES: dict[str, Theme] = {}

_raw = [
    # key, name, dark?, bg, fg, accent, alt, border, hover, pressed
    _dark("dark_default",   "Dark (default)",
          "#1e1e1e", "#d4d4d4", "#4ec9b0", "#252526", "#3c3c3c", "#2d2d2d", "#1a1a1a"),

    _dark("midnight_blue",  "Midnight Blue",
          "#0d1117", "#c9d1d9", "#58a6ff", "#161b22", "#30363d", "#1f2937", "#0a0e14"),

    _dark("charcoal_orange","Charcoal & Orange",
          "#1c1c1c", "#e0e0e0", "#f5a623", "#272727", "#3a3a3a", "#2e2e2e", "#141414"),

    _dark("deep_purple",    "Deep Purple",
          "#1a0a2e", "#e0d5f5", "#a855f7", "#250f3d", "#3b1f5e", "#2e1650", "#100520"),

    _dark("hacker_green",   "Hacker Green",
          "#0c0c0c", "#33ff33", "#00ff41", "#111111", "#1a2e1a", "#0f1f0f", "#050f05"),

    _light("light_clean",   "Light (clean)",
           "#f5f5f5", "#1e1e1e", "#007acc", "#ffffff", "#cccccc", "#e8e8e8", "#d0d0d0"),

    _light("warm_cream",    "Warm Cream",
           "#fdf6e3", "#3c3836", "#d65d0e", "#fffbf0", "#c9b89a", "#f0e8d0", "#e0d0b0"),
]

for t in _raw:
    THEMES[t.key] = t

THEME_KEYS: list[str] = list(THEMES.keys())
DEFAULT_THEME = "dark_default"


def apply_theme(app, key: str) -> None:
    """Apply a theme by key to the QApplication."""
    theme = THEMES.get(key, THEMES[DEFAULT_THEME])
    app.setStyleSheet(theme.stylesheet)
