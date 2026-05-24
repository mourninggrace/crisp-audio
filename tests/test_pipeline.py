"""Headless tests for the core engine — no GUI, no audio device required."""
from __future__ import annotations

import numpy as np
import pytest

from crisp.core.audio import AudioClip
from crisp.core.engine import CleanupEngine, CleanupSettings
from crisp.core.processors.loudness import LoudnessNormalize


def _tone(seconds=1.0, sr=48000, freq=220.0, amp=0.3):
    """A noisy sine tone to exercise the processors."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = amp * np.sin(2 * np.pi * freq * t)
    sig += 0.02 * np.random.default_rng(0).standard_normal(sig.shape)  # hiss
    return AudioClip.from_array(sig.astype(np.float32), sr)


def test_clip_is_canonicalised():
    clip = AudioClip.from_array(np.zeros(100, dtype=np.float32), 48000)
    assert clip.samples.ndim == 2
    assert clip.channels == 1
    assert clip.samples.dtype == np.float32


def test_int16_is_normalised():
    pcm = np.array([0, 32767, -32768], dtype=np.int16)
    clip = AudioClip.from_array(pcm, 48000)
    assert clip.peak() <= 1.0 + 1e-6


def test_loudness_hits_target():
    clip = _tone()
    out = LoudnessNormalize(target_lufs=-16.0).process(clip)
    measured = LoudnessNormalize().measure_lufs(out)
    assert measured == pytest.approx(-16.0, abs=1.0)


def test_engine_runs_full_chain_and_preserves_shape():
    clip = _tone()
    settings = CleanupSettings.defaults()
    settings.enabled["dereverb"] = True  # exercise every stage
    out = CleanupEngine().run(clip, settings)
    assert out.sample_rate == clip.sample_rate
    assert out.channels == clip.channels
    assert np.isfinite(out.samples).all()
    assert out.peak() <= 1.0 + 1e-3


def test_empty_settings_is_passthrough():
    clip = _tone()
    settings = CleanupSettings(enabled={})
    out = CleanupEngine().run(clip, settings)
    assert np.array_equal(out.samples, clip.samples)
