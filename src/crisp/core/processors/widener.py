"""Stereo widener — mid-side manipulation.

Upmixes mono to stereo if needed, then applies M/S widening.
A width of 1.0 is unity (no change). Values > 1.0 push sides out further;
< 1.0 narrows toward mono.
"""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class Widener(Processor):
    key = "widener"
    label = "Stereo Widener"
    description = "Widens or narrows the stereo image via M/S processing. Upmixes mono."
    default_params = {"width": 1.4}
    param_specs = [
        ParamSpec("width", "Width", "float", 0.0, 2.5, 0.05),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        width = float(self.params["width"])
        samples = clip.samples

        # Upmix mono → stereo by duplicating the channel.
        if clip.channels == 1:
            samples = np.repeat(samples, 2, axis=1)

        if clip.channels > 2:
            # Just work on the first two channels; pass the rest through.
            stereo = samples[:, :2]
            rest   = samples[:, 2:]
            stereo = self._ms_widen(stereo, width)
            out    = np.concatenate([stereo, rest], axis=1)
            return clip.with_samples(out.astype(np.float32))

        return clip.with_samples(self._ms_widen(samples, width).astype(np.float32))

    @staticmethod
    def _ms_widen(stereo: np.ndarray, width: float) -> np.ndarray:
        L, R = stereo[:, 0], stereo[:, 1]
        M = (L + R) * 0.5
        S = (L - R) * 0.5
        S *= width
        out = np.stack([M + S, M - S], axis=1)
        # Guard against clipping after widening.
        peak = np.max(np.abs(out))
        if peak > 1.0:
            out /= peak
        return out
