"""Gain trim — simple dB adjustment before the loudness stage."""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class Trim(Processor):
    key = "trim"
    label = "Trim (gain)"
    description = "Adjust clip gain in dB before loudness normalization."
    default_params = {"gain_db": 0.0}
    param_specs = [
        ParamSpec("gain_db", "Gain", "float", -24.0, 24.0, 0.5, "dB"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        gain_db = float(self.params["gain_db"])
        if gain_db == 0.0:
            return clip
        gain = 10 ** (gain_db / 20.0)
        out = np.clip(clip.samples * gain, -1.0, 1.0).astype(np.float32)
        return clip.with_samples(out)
