"""Batch processing: clean every audio file in a folder and export it."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from crisp.core import audio_io
from crisp.core.engine import CleanupEngine, CleanupSettings
from crisp.core.exporter import EXTENSIONS, export
from crisp.core.presets import ExportSettings

# Inputs we'll attempt to load in a batch run.
INPUT_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".aiff", ".aif"}

# (file_path, index, total, status) -> None
BatchProgressCB = Callable[[Path, int, int, str], None]


@dataclass
class BatchResult:
    source: Path
    output: Path | None
    ok: bool
    error: str | None = None


def find_audio_files(folder: str | Path) -> list[Path]:
    folder = Path(folder)
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )


def process_folder(
    folder: str | Path,
    out_dir: str | Path,
    cleanup: CleanupSettings,
    export_settings: ExportSettings,
    progress: BatchProgressCB | None = None,
    files: Iterable[Path] | None = None,
) -> list[BatchResult]:
    """Clean and export every audio file in ``folder`` into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = CleanupEngine()

    file_list = list(files) if files is not None else find_audio_files(folder)
    total = len(file_list)
    results: list[BatchResult] = []

    for i, src in enumerate(file_list):
        if progress:
            progress(src, i, total, "processing")
        try:
            clip = audio_io.load(src)
            cleaned = engine.run(clip, cleanup)
            out_path = out_dir / (src.stem + EXTENSIONS[export_settings.fmt])
            export(cleaned, out_path, export_settings)
            results.append(BatchResult(src, out_path, True))
            if progress:
                progress(src, i, total, "done")
        except Exception as exc:  # keep going; report per-file
            results.append(BatchResult(src, None, False, str(exc)))
            if progress:
                progress(src, i, total, f"error: {exc}")
    return results
