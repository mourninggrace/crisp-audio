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
from crisp.core.processors.loudness import LoudnessNormalize

# Pipeline order: clean noise/room first, fix spectral problems, then set level.
ALL_PROCESSORS: list[type[Processor]] = [
    NoiseReduction,
    Dereverb,
    PlosiveRemoval,
    EqBalance,
    VoiceClarity,
    LoudnessNormalize,
]

__all__ = [
    "Processor",
    "NoiseReduction",
    "Dereverb",
    "PlosiveRemoval",
    "EqBalance",
    "VoiceClarity",
    "LoudnessNormalize",
    "ALL_PROCESSORS",
]
