"""Light / dark appearance. Mode is 'system' (follow Windows / macOS), 'light' or 'dark'.
Every color the app uses comes from here, so text is always readable on its background."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication

LIGHT = {
    "bg": "#f6f8fb", "surface": "#ffffff", "alt": "#fafbfd", "border": "#e3e8ef", "input_border": "#cfd8e3",
    "text": "#1f2a3a", "muted": "#5b6b82", "side_text": "#33415c", "hover": "#e8f0fe", "selection": "#dbe8fd",
    "selection_text": "#1f2a3a", "accent": "#1a73e8", "accent_hover": "#1765cc", "accent_soft": "#e8f0fe",
    "accent_text": "#1a73e8", "ok": "#188038", "bad": "#d93025", "progress_bg": "#eef1f5", "tooltip": "#1f2a3a",
}
DARK = {
    "bg": "#16191d", "surface": "#1f2329", "alt": "#24292f", "border": "#323842", "input_border": "#444c58",
    "text": "#e7eaee", "muted": "#9aa5b4", "side_text": "#c9d1db", "hover": "#2a3443", "selection": "#27415f",
    "selection_text": "#ffffff", "accent": "#4c8dff", "accent_hover": "#6aa1ff", "accent_soft": "#22344d",
    "accent_text": "#8ab4ff", "ok": "#5fcf80", "bad": "#ff7b72", "progress_bg": "#2b3139", "tooltip": "#2b3139",
}

QSS = """
QWidget {{ color: {text}; }}
QMainWindow, QDialog, QMessageBox, QTabWidget::pane, QTabWidget > QWidget {{ background: {bg}; }}
QToolBar {{ background: {surface}; border: none; border-bottom: 1px solid {border}; padding: 6px; spacing: 6px; }}
QToolButton {{ padding: 6px 12px; border-radius: 6px; color: {text}; font-weight: 500; background: transparent; }}
QToolButton:hover {{ background: {hover}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QToolButton#primary {{ background: {accent}; color: #ffffff; }}
QToolButton#primary:hover {{ background: {accent_hover}; }}
QListWidget {{ background: {surface}; border: none; border-right: 1px solid {border}; font-size: 13px; padding-top: 8px; }}
QListWidget::item {{ padding: 9px 14px; border-radius: 6px; margin: 1px 6px; color: {side_text}; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {accent_soft}; color: {accent_text}; font-weight: 600; }}
QDialog QListWidget {{ border: 1px solid {border}; border-radius: 6px; }}
QTableView {{ outline: 0; background: {surface}; border: none; gridline-color: transparent; color: {text};
             selection-background-color: {selection}; selection-color: {selection_text};
             alternate-background-color: {alt}; }}
QHeaderView::section {{ background: {surface}; border: none; border-bottom: 1px solid {border};
                       padding: 7px; font-weight: 600; color: {muted}; }}
QTableCornerButton::section {{ background: {surface}; border: none; }}
QStatusBar {{ background: {surface}; border-top: 1px solid {border}; color: {muted}; }}
QStatusBar QLabel {{ color: {muted}; }}
QPushButton {{ padding: 6px 14px; border-radius: 6px; border: 1px solid {input_border}; background: {surface}; color: {text}; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:default, QPushButton#primary {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
QPushButton:disabled {{ color: {muted}; }}
QLineEdit, QSpinBox, QComboBox, QTimeEdit {{ padding: 5px; border: 1px solid {input_border}; border-radius: 5px;
             background: {surface}; color: {text}; selection-background-color: {accent}; selection-color: #ffffff; }}
QComboBox QAbstractItemView {{ background: {surface}; color: {text}; selection-background-color: {selection};
             selection-color: {selection_text}; border: 1px solid {border}; }}
QCheckBox, QLabel, QRadioButton {{ color: {text}; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {input_border}; border-radius: 4px; background: {surface}; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check}); }}
QTabBar::tab {{ background: {bg}; color: {muted}; padding: 7px 14px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {accent_text}; border-bottom: 2px solid {accent}; }}
QMenu {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {hover}; color: {text}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 6px; }}
QToolTip {{ background: {tooltip}; color: #ffffff; border: none; padding: 5px 8px; }}
QProgressBar {{ background: {progress_bg}; border: 1px solid {border}; border-radius: 5px; text-align: center; color: {text}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {input_border}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {input_border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""

MODES = ("system", "light", "dark")
_current = dict(LIGHT)
_mode = "system"
_applying = False


def system_is_dark():
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:  # noqa  (very old Qt: assume light)
        return False


def is_dark(mode=None):
    mode = mode or _mode
    return system_is_dark() if mode == "system" else mode == "dark"


def mode():
    return _mode


def colors():
    """The colors in use right now (for code that paints by hand)."""
    return _current


def _check_icon():
    """A white tick for checked boxes (written once next to the app's data)."""
    import os
    from settings import data_dir
    path = os.path.join(data_dir(), "check.svg")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                    '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="#ffffff" stroke-width="2.2" '
                    'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return path.replace("\\", "/")


def qss(c=LIGHT):
    try:
        check = _check_icon()
    except OSError:
        check = ""
    return QSS.format(check=check, **c)


def _palette(c):
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["bg"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["surface"], QPalette.ColorRole.AlternateBase: c["alt"],
        QPalette.ColorRole.Text: c["text"], QPalette.ColorRole.Button: c["surface"],
        QPalette.ColorRole.ButtonText: c["text"], QPalette.ColorRole.Highlight: c["accent"],
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: c["tooltip"],
        QPalette.ColorRole.ToolTipText: "#ffffff", QPalette.ColorRole.PlaceholderText: c["muted"],
        QPalette.ColorRole.Link: c["accent_text"], QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Mid: c["border"], QPalette.ColorRole.Midlight: c["alt"],
        QPalette.ColorRole.Dark: c["input_border"], QPalette.ColorRole.Shadow: "#000000",
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["muted"]))
    return p


def apply(mode="system", app=None):
    """Switch the whole app (all windows, dialogs, menus) to a mode, immediately."""
    global _mode, _applying
    if _applying:
        return
    _applying = True
    try:
        app = app or QApplication.instance()
        _mode = mode if mode in MODES else "system"
        _tell_qt(app, _mode)
        _paint(app, DARK if is_dark() else LIGHT)
    finally:
        _applying = False


def _tell_qt(app, mode):
    """Let Qt / the OS know too, so native parts (e.g. the Windows 11 title bar) match. Qt 6.8+."""
    hints = app.styleHints()
    try:
        if mode == "system":
            hints.unsetColorScheme()
        else:
            hints.setColorScheme(Qt.ColorScheme.Dark if mode == "dark" else Qt.ColorScheme.Light)
    except AttributeError:
        pass


def _paint(app, c):
    _current.clear()
    _current.update(c)
    app.setStyle("Fusion")             # same look on Windows and macOS, and it honours the palette fully
    app.setPalette(_palette(c))
    app.setStyleSheet(qss(c))
    for w in app.topLevelWidgets():    # repaint anything already on screen
        w.update()


def follow_system(app, get_mode):
    """Re-apply when the user switches Windows / macOS between light and dark (only in 'system' mode)."""
    try:
        app.styleHints().colorSchemeChanged.connect(lambda _s: apply(get_mode(), app) if get_mode() == "system" else None)
    except Exception:  # noqa
        pass
