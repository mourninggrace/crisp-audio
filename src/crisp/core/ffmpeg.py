"""Locate an ffmpeg binary, preferring the bundled one.

`pydub` and any MP3/AAC encoding need an ffmpeg executable. Rather than rely on
the user having ffmpeg on PATH (they usually won't), we lean on the
``imageio-ffmpeg`` wheel which ships a static binary on every platform. This
keeps the eventual PyInstaller exe self-contained.
"""
from __future__ import annotations

import functools
import shutil


@functools.lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    """Return a usable ffmpeg path, or ``None`` if nothing is available."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        # Fall back to a system install if the bundled binary is unavailable.
        return shutil.which("ffmpeg")


def configure_pydub() -> None:
    """Point pydub at our ffmpeg binary so format conversion works."""
    path = ffmpeg_path()
    if not path:
        return
    from pydub import AudioSegment

    AudioSegment.converter = path
    AudioSegment.ffmpeg = path
