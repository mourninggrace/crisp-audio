"""QApplication bootstrap."""
from __future__ import annotations

from crisp import APP_NAME


def run(argv: list[str]) -> int:
    from PySide6 import QtWidgets

    from crisp.core.ffmpeg import configure_pydub
    from crisp.gui.main_window import MainWindow

    configure_pydub()  # wire ffmpeg up front so export "just works"

    app = QtWidgets.QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()
