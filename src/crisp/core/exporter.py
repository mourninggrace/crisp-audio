"""Write an :class:`AudioClip` to disk in the requested format.

WAV/FLAC/OGG/AIFF use libsndfile directly.  MP3/AAC/OPUS are encoded through
ffmpeg via pydub.  If an :class:`ExportSettings.target_lufs` is set, loudness
is applied just before encoding so presets land on their delivery spec.
"""
from __future__ import annotations

from pathlib import Path

from crisp.core import audio_io
from crisp.core.audio import AudioClip
from crisp.core.ffmpeg import configure_pydub, ffmpeg_path
from crisp.core.presets import ExportSettings, Format
from crisp.core.processors.loudness import LoudnessNormalize

# Default extension per format (AAC lives in an .m4a container).
EXTENSIONS = {
    Format.WAV:  ".wav",
    Format.FLAC: ".flac",
    Format.MP3:  ".mp3",
    Format.AAC:  ".m4a",
    Format.OGG:  ".ogg",
    Format.OPUS: ".opus",
    Format.AIFF: ".aiff",
}

# Formats that go through ffmpeg rather than libsndfile.
_FFMPEG_FORMATS = {Format.MP3, Format.AAC, Format.OPUS}


def export(clip: AudioClip, path: str | Path, settings: ExportSettings) -> Path:
    """Encode ``clip`` to ``path`` (extension forced to match the format)."""
    path = Path(path).with_suffix(EXTENSIONS[settings.fmt])

    if settings.target_lufs is not None:
        clip = LoudnessNormalize(target_lufs=settings.target_lufs).process(clip)

    if settings.fmt == Format.WAV:
        audio_io.save_wav(clip, path, subtype=settings.wav_subtype)
    elif settings.fmt == Format.FLAC:
        audio_io.save_flac(clip, path, subtype=settings.wav_subtype)
    elif settings.fmt == Format.OGG:
        audio_io.save_ogg(clip, path)
    elif settings.fmt == Format.AIFF:
        audio_io.save_aiff(clip, path, subtype=settings.wav_subtype)
    elif settings.fmt in _FFMPEG_FORMATS:
        _export_ffmpeg(clip, path, settings)
    else:  # pragma: no cover - exhaustive
        raise ValueError(f"Unsupported format: {settings.fmt}")
    return path


def _export_ffmpeg(clip: AudioClip, path: Path, settings: ExportSettings) -> None:
    if not ffmpeg_path():
        raise RuntimeError(
            "ffmpeg is required for MP3/AAC/OPUS export but was not found. "
            "Install the 'imageio-ffmpeg' package."
        )
    configure_pydub()
    seg = audio_io.clip_to_segment(clip)

    if settings.fmt == Format.AAC:
        seg.export(str(path), format="ipod", codec="aac", bitrate=settings.mp3_bitrate)
    elif settings.fmt == Format.OPUS:
        # pydub wraps ffmpeg; 'opus' format requires libopus which ffmpeg bundles.
        seg.export(str(path), format="opus", codec="libopus", bitrate=settings.mp3_bitrate)
    else:  # MP3
        seg.export(str(path), format="mp3", bitrate=settings.mp3_bitrate)
