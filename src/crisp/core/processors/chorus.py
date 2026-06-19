"""Chorus effect — multiple LFO-modulated delay voices layered over the dry signal."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor

_CENTER_DELAY_S = 0.020  # 20 ms fixed center delay per voice


class Chorus(Processor):
    key = "chorus"
    label = "Chorus"
    description = "Thickens audio with LFO-modulated delay voices (rate, depth, mix)."
    default_params = {
        "rate": 0.8,      # LFO Hz
        "depth": 0.010,   # seconds of LFO delay swing
        "mix": 0.40,      # wet/dry
        "voices": 2,      # number of chorus voices (int 1-3)
    }
    param_specs = [
        ParamSpec("rate",   "Rate",   "float", 0.1, 5.0,  0.1,  "Hz"),
        ParamSpec("depth",  "Depth",  "float", 0.001, 0.030, 0.001, "s"),
        ParamSpec("mix",    "Mix",    "float", 0.0, 1.0,  0.05),
        ParamSpec("voices", "Voices", "float", 1.0, 3.0,  1.0),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        sr = clip.sample_rate
        samples = clip.samples
        n_frames, n_ch = samples.shape

        rate   = float(self.params["rate"])
        depth  = float(self.params["depth"])
        mix    = float(self.params["mix"])
        voices = max(1, int(round(float(self.params["voices"]))))

        t = np.arange(n_frames, dtype=np.float64) / sr
        wet = np.zeros_like(samples)

        for v in range(voices):
            phase = 2 * np.pi * v / voices
            lfo = np.sin(2 * np.pi * rate * t + phase)
            delay_samples = (_CENTER_DELAY_S + lfo * depth) * sr
            read_idx = np.clip(np.arange(n_frames) - delay_samples, 0, n_frames - 1)

            for ch in range(n_ch):
                # order=1 → linear interpolation; mode='nearest' clamps at edges
                wet[:, ch] += map_coordinates(
                    samples[:, ch], [read_idx], order=1, mode="nearest"
                )

        wet /= voices
        out = (samples * (1.0 - mix) + wet * mix).astype(np.float32)
        return clip.with_samples(out)
