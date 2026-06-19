"""Cleanup processors. Each maps to one checkbox in the UI.

Import :data:`ALL_PROCESSORS` for the canonical ordered list — the order is the
order they run in the pipeline, which matters (e.g. denoise before loudness).
"""
from __future__ import annotations

from crisp.core.processors.base import Processor
from crisp.core.processors.noise import NoiseReduction
from crisp.core.processors.dereverb import Dereverb
from crisp.core.processors.deplosive import PlosiveRemoval
from crisp.core.processors.eq import EqBalance
from crisp.core.processors.clarity import VoiceClarity
from crisp.core.processors.trim import Trim
from crisp.core.processors.chorus import Chorus
from crisp.core.processors.widener import Widener
from crisp.core.processors.panner import Panner
from crisp.core.processors.loudness import LoudnessNormalize

# Pipeline order matters:
#  1. Clean noise / room artefacts first
#  2. Fix spectral / tonal problems
#  3. Creative / spatial effects
#  4. Gain trim (before loudness so the target still wins)
#  5. Set final loudness level
ALL_PROCESSORS: list[type[Processor]] = [
    NoiseReduction,
    Dereverb,
    PlosiveRemoval,
    EqBalance,
    VoiceClarity,
    Trim,
    Chorus,
    Widener,
    Panner,
    LoudnessNormalize,
]

__all__ = [
    "Processor",
    "NoiseReduction",
    "Dereverb",
    "PlosiveRemoval",
    "EqBalance",
    "VoiceClarity",
    "Trim",
    "Chorus",
    "Widener",
    "Panner",
    "LoudnessNormalize",
    "ALL_PROCESSORS",
]
