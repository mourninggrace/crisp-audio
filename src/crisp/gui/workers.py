"""Background QThread workers so the UI never blocks during DSP.

DSP on a multi-minute clip can take seconds; running it on the GUI thread would
freeze the window. Each worker emits progress and a finished/failed signal.
"""
from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

from crisp.core.audio import AudioClip
from crisp.core.batch import BatchResult, process_folder
from crisp.core.engine import CleanupEngine, CleanupSettings
from crisp.core.presets import ExportSettings


class CleanupWorker(QtCore.QThread):
    progress = QtCore.Signal(str, float)   # stage label, fraction
    finished_ok = QtCore.Signal(object)    # AudioClip
    failed = QtCore.Signal(str)

    def __init__(self, clip: AudioClip, settings: CleanupSettings) -> None:
        super().__init__()
        self._clip = clip
        self._settings = settings

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            engine = CleanupEngine()
            result = engine.run(
                self._clip,
                self._settings,
                progress=lambda label, frac: self.progress.emit(label, frac),
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # surface to the UI instead of crashing
            self.failed.emit(str(exc))


class BatchWorker(QtCore.QThread):
    progress = QtCore.Signal(str, int, int, str)  # filename, idx, total, status
    finished_all = QtCore.Signal(object)          # list[BatchResult]
    failed = QtCore.Signal(str)

    def __init__(
        self,
        folder: Path,
        out_dir: Path,
        cleanup: CleanupSettings,
        export_settings: ExportSettings,
    ) -> None:
        super().__init__()
        self._folder = folder
        self._out_dir = out_dir
        self._cleanup = cleanup
        self._export = export_settings

    def run(self) -> None:
        try:
            results = process_folder(
                self._folder,
                self._out_dir,
                self._cleanup,
                self._export,
                progress=lambda p, i, t, s: self.progress.emit(p.name, i, t, s),
            )
            self.finished_all.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))
