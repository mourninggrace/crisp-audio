"""The :class:`AudioClip` value object passed through the whole pipeline.

Internally audio is always stored as float32 in ``[-1.0, 1.0]`` with shape
``(frames, channels)``. Keeping a single canonical representation means every
processor, the waveform view, and the exporter can make the same assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np


@dataclass(frozen=True)
class AudioClip:
    """Immutable block of PCM audio.

    Attributes
    ----------
    samples:
        float32 array, shape ``(frames, channels)``, range ``[-1, 1]``.
    sample_rate:
        Frames per second (Hz).
    """

    samples: np.ndarray
    sample_rate: int

    def __post_init__(self) -> None:
        if self.samples.ndim != 2:
            raise ValueError(f"samples must be 2-D (frames, channels), got {self.samples.shape}")
        if self.samples.dtype != np.float32:
            object.__setattr__(self, "samples", self.samples.astype(np.float32))

    @classmethod
    def from_array(cls, data: np.ndarray, sample_rate: int) -> "AudioClip":
        """Build a clip from any int/float array, mono or interleaved."""
        arr = np.asarray(data)
        if arr.ndim == 1:
            arr = arr[:, np.newaxis]
        arr = _to_float32(arr)
        return cls(arr, int(sample_rate))

    @property
    def channels(self) -> int:
        return self.samples.shape[1]

    @property
    def frames(self) -> int:
        return self.samples.shape[0]

    @property
    def duration(self) -> float:
        return self.frames / self.sample_rate if self.sample_rate else 0.0

    def to_mono(self) -> "AudioClip":
        if self.channels == 1:
            return self
        mono = self.samples.mean(axis=1, keepdims=True).astype(np.float32)
        return replace(self, samples=mono)

    def with_samples(self, samples: np.ndarray) -> "AudioClip":
        """Return a copy carrying new sample data at the same rate."""
        if samples.ndim == 1:
            samples = samples[:, np.newaxis]
        return replace(self, samples=samples.astype(np.float32, copy=False))

    def peak(self) -> float:
        return float(np.max(np.abs(self.samples))) if self.frames else 0.0


def _to_float32(arr: np.ndarray) -> np.ndarray:
    """Convert common PCM dtypes to float32 in [-1, 1]."""
    if np.issubdtype(arr.dtype, np.floating):
        return arr.astype(np.float32, copy=False)
    info = np.iinfo(arr.dtype)
    # Signed PCM: divide by the negative-most magnitude to stay within range.
    denom = float(max(abs(info.min), info.max))
    return (arr.astype(np.float32) / denom).astype(np.float32)
