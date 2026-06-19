"""Stereo panner — constant-power panning.

Positions the signal in the stereo field. 0.0 = hard left, 0.5 = centre,
1.0 = hard right. For mono input, upmixes to stereo first.
Constant-power law (sin/cos) keeps perceived loudness stable across the pan arc.
"""
from __future__ import annotations

import math

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class Panner(Processor):
    key = "panner"
    label = "Panner"
    description = "Stereo panning, constant-power. 0 = hard L, 0.5 = centre, 1 = hard R."
    default_params = {"position": 0.5}
    param_specs = [
        ParamSpec("position", "Pan position", "float", 0.0, 1.0, 0.01),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        pos = float(self.params["position"])

        # Mix down to mono first so the pan law is applied cleanly.
        mono = clip.to_mono().samples[:, 0]

        # Constant-power pan law: L = cos(θ), R = sin(θ), θ ∈ [0, π/2]
        theta = pos * (math.pi / 2.0)
        gain_l = math.cos(theta)
        gain_r = math.sin(theta)

        out = np.stack([mono * gain_l, mono * gain_r], axis=1).astype(np.float32)
        return clip.with_samples(out)
