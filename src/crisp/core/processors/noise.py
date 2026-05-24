"""Background-noise removal via spectral gating (noisereduce)."""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class NoiseReduction(Processor):
    key = "noise"
    label = "Remove background noise"
    description = "Spectral-gating denoise (hum, hiss, fans, AC)."
    default_params = {
        "strength": 0.85,        # prop_decrease: 0..1, how aggressively to cut
        "stationary": False,     # True = constant noise floor; False = adapts
    }
    param_specs = [
        ParamSpec("strength", "Strength", "float", 0.0, 1.0, 0.05),
        ParamSpec("stationary", "Constant noise floor", "bool"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        import noisereduce as nr

        strength = float(self.params["strength"])
        stationary = bool(self.params["stationary"])
        # noisereduce expects (channels, frames) or (frames,); process per channel
        # to keep stereo imaging intact.
        out = np.empty_like(clip.samples)
        for ch in range(clip.channels):
            out[:, ch] = nr.reduce_noise(
                y=clip.samples[:, ch],
                sr=clip.sample_rate,
                prop_decrease=strength,
                stationary=stationary,
            ).astype(np.float32)
        return clip.with_samples(out)
