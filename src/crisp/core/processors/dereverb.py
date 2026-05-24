"""Reverb / room-tail reduction via spectral over-subtraction.

True dereverberation is hard. This is a pragmatic approach that works well on
spoken voice: estimate a slowly-varying noise/reverb floor per frequency bin
(the reverb tail is the part of the spectrum that lingers) and subtract a
fraction of it. It leans on noisereduce's stationary mode tuned for the diffuse
tail rather than broadband hiss.
"""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class Dereverb(Processor):
    key = "dereverb"
    label = "Reduce reverb / room sound"
    description = "Suppresses the diffuse room tail to dry up the voice."
    default_params = {
        "strength": 0.6,      # 0..1 amount of tail to remove
        "time_mask_ms": 60,   # smoothing window for the tail estimate
    }
    param_specs = [
        ParamSpec("strength", "Strength", "float", 0.0, 1.0, 0.05),
        ParamSpec("time_mask_ms", "Tail smoothing", "float", 20, 200, 10, "ms"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        import noisereduce as nr

        strength = float(self.params["strength"])
        time_mask = float(self.params["time_mask_ms"])
        out = np.empty_like(clip.samples)
        for ch in range(clip.channels):
            out[:, ch] = nr.reduce_noise(
                y=clip.samples[:, ch],
                sr=clip.sample_rate,
                stationary=False,
                prop_decrease=strength,
                time_mask_smooth_ms=time_mask,
                freq_mask_smooth_hz=500,
            ).astype(np.float32)
        return clip.with_samples(out)
