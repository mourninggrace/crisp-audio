"""QApplication bootstrap."""
from __future__ import annotations

from crisp import APP_NAME


def run(argv: list[str]) -> int:
    from PySide6 import QtWidgets

    from crisp.core.ffmpeg import configure_pydub
    from crisp.gui.main_window import MainWindow
    from crisp.gui.settings_dialog import load_settings
    from crisp.gui.themes import apply_theme

    configure_pydub()  # wire ffmpeg up front so export "just works"

    app = QtWidgets.QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    # Bump the base font to something readable.
    font = app.font()
    font.setPointSize(11)
    app.setFont(font)

    # Apply persisted theme before the window draws anything.
    settings = load_settings()
    apply_theme(app, settings.get("theme", "dark_default"))

    window = MainWindow()
    window.show()
    return app.exec()
