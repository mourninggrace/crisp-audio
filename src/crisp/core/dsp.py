"""Reusable DSP primitives (biquad filters, simple dynamics).

These are deliberately dependency-light — just numpy + scipy — so processors can
share them without each reinventing filter design.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import sosfilt, butter


def _apply_sos(samples: np.ndarray, sos: np.ndarray) -> np.ndarray:
    """Filter every channel of an (frames, channels) array with an SOS."""
    out = np.empty_like(samples)
    for ch in range(samples.shape[1]):
        out[:, ch] = sosfilt(sos, samples[:, ch]).astype(np.float32)
    return out


def highpass(samples: np.ndarray, sr: int, cutoff: float, order: int = 4) -> np.ndarray:
    sos = butter(order, cutoff / (sr / 2), btype="highpass", output="sos")
    return _apply_sos(samples, sos)


def lowpass(samples: np.ndarray, sr: int, cutoff: float, order: int = 4) -> np.ndarray:
    sos = butter(order, min(cutoff / (sr / 2), 0.999), btype="lowpass", output="sos")
    return _apply_sos(samples, sos)


def peaking_eq(samples: np.ndarray, sr: int, freq: float, gain_db: float, q: float = 1.0) -> np.ndarray:
    """Apply an RBJ peaking (bell) EQ filter to every channel."""
    b, a = _peaking_coeffs(sr, freq, gain_db, q)
    sos = np.hstack([b, a]).reshape(1, 6)
    return _apply_sos(samples, sos)


def _peaking_coeffs(sr: int, freq: float, gain_db: float, q: float):
    """RBJ cookbook peaking-EQ coefficients, normalised so a0 = 1."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2 * q)
    cos_w0 = np.cos(w0)

    b0 = 1 + alpha * A
    b1 = -2 * cos_w0
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cos_w0
    a2 = 1 - alpha / A
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def soft_compress(samples: np.ndarray, threshold_db: float = -18.0, ratio: float = 2.5) -> np.ndarray:
    """A gentle feed-forward compressor on the signal envelope.

    Simplified (no separate attack/release smoothing): good enough to even out
    a voice without obvious pumping. Operates on the linked stereo envelope.
    """
    eps = 1e-9
    env = np.sqrt(np.mean(samples ** 2, axis=1, keepdims=True)) + eps
    env_db = 20 * np.log10(env)
    over = np.maximum(env_db - threshold_db, 0.0)
    gain_db = -over * (1 - 1 / ratio)
    gain = 10 ** (gain_db / 20.0)
    return (samples * gain).astype(np.float32)
