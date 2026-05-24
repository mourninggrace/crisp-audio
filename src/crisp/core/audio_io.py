"""Load and save :class:`AudioClip` objects.

WAV/FLAC/OGG go through libsndfile (``soundfile``) directly. Formats that
need an encoder libsndfile lacks (MP3, AAC/M4A) are routed through ffmpeg via
``pydub``. Loading of compressed inputs also goes through pydub.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import soundfile as sf

from crisp.core.audio import AudioClip
from crisp.core.ffmpeg import configure_pydub

# Extensions libsndfile handles natively for *reading*.
_NATIVE_READ = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".w64"}


def load(path: str | Path) -> AudioClip:
    """Read any supported audio file into an :class:`AudioClip`."""
    path = Path(path)
    if path.suffix.lower() in _NATIVE_READ:
        data, sr = sf.read(str(path), always_2d=True, dtype="float32")
        return AudioClip(data, sr)
    return _load_via_pydub(path)


def _load_via_pydub(path: Path) -> AudioClip:
    configure_pydub()
    from pydub import AudioSegment

    seg = AudioSegment.from_file(str(path))
    samples = np.array(seg.get_array_of_samples())
    samples = samples.reshape((-1, seg.channels)) if seg.channels > 1 else samples[:, None]
    # pydub samples are signed int of width sample_width; normalise by bit depth.
    max_val = float(1 << (8 * seg.sample_width - 1))
    floats = (samples.astype(np.float32) / max_val)
    return AudioClip(floats, seg.frame_rate)


def save_wav(clip: AudioClip, path: str | Path, subtype: str = "PCM_16") -> None:
    """Write a WAV. ``subtype`` is a libsndfile subtype like ``PCM_24``."""
    sf.write(str(path), clip.samples, clip.sample_rate, subtype=subtype)


def save_flac(clip: AudioClip, path: str | Path, subtype: str = "PCM_16") -> None:
    sf.write(str(path), clip.samples, clip.sample_rate, subtype=subtype, format="FLAC")


def save_ogg(clip: AudioClip, path: str | Path) -> None:
    sf.write(str(path), clip.samples, clip.sample_rate, format="OGG", subtype="VORBIS")


def clip_to_segment(clip: AudioClip):
    """Convert a clip to a pydub ``AudioSegment`` (int16) for ffmpeg encoding."""
    from pydub import AudioSegment

    pcm = np.clip(clip.samples, -1.0, 1.0)
    int16 = (pcm * 32767.0).astype("<i2")
    return AudioSegment(
        int16.tobytes(),
        frame_rate=clip.sample_rate,
        sample_width=2,
        channels=clip.channels,
    )
