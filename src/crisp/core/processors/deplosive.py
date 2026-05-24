"""Plosive (p-pop / b-pop) removal.

Plosives are short bursts of low-frequency energy from breath hitting the mic.
We detect frames where sub-120 Hz energy spikes well above the rolling average
and duck the low end there, leaving normal speech untouched.
"""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.dsp import highpass, lowpass
from crisp.core.processors.base import ParamSpec, Processor


class PlosiveRemoval(Processor):
    key = "plosives"
    label = "Remove plosives"
    description = "Detects low-frequency breath pops and ducks them."
    default_params = {
        "split_hz": 120.0,    # crossover between "rumble" and the rest
        "threshold": 3.0,     # how many x the median low-band energy counts as a pop
        "reduction": 0.85,    # how much of the low band to remove at a pop (0..1)
    }
    param_specs = [
        ParamSpec("split_hz", "Crossover", "float", 60, 200, 5, "Hz"),
        ParamSpec("threshold", "Sensitivity", "float", 1.5, 6.0, 0.1, "×"),
        ParamSpec("reduction", "Reduction", "float", 0.0, 1.0, 0.05),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        sr = clip.sample_rate
        split = float(self.params["split_hz"])
        low = lowpass(clip.samples, sr, split, order=4)
        high = highpass(clip.samples, sr, split, order=4)

        # Short-window energy of the low band, summed across channels.
        win = max(1, int(sr * 0.01))  # 10 ms
        low_mono = np.mean(np.abs(low), axis=1)
        kernel = np.ones(win) / win
        energy = np.convolve(low_mono, kernel, mode="same")

        median = np.median(energy) + 1e-9
        thresh = median * float(self.params["threshold"])
        reduction = float(self.params["reduction"])

        # Smooth gain envelope: full low band normally, ducked at pops.
        duck = np.where(energy > thresh, 1.0 - reduction, 1.0)
        duck = np.convolve(duck, kernel, mode="same")[:, None]

        out = high + low * duck.astype(np.float32)
        return clip.with_samples(out.astype(np.float32))
