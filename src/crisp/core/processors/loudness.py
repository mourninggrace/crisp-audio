"""Loudness normalisation to a target LUFS (ITU-R BS.1770 via pyloudnorm).

Measures integrated loudness, applies the gain needed to hit the target, then
guards against clipping with a peak ceiling (true-peak-ish, using sample peak).
"""
from __future__ import annotations

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.processors.base import ParamSpec, Processor


class LoudnessNormalize(Processor):
    key = "loudness"
    label = "Normalize loudness (LUFS)"
    description = "Hits a target integrated loudness with a peak ceiling."
    default_params = {
        "target_lufs": -16.0,
        "peak_ceiling_db": -1.0,   # don't exceed this sample peak after gain
    }
    param_specs = [
        ParamSpec("target_lufs", "Target", "float", -30.0, -9.0, 0.5, "LUFS"),
        ParamSpec("peak_ceiling_db", "Peak ceiling", "float", -3.0, 0.0, 0.5, "dB"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        import pyloudnorm as pyln

        target = float(self.params["target_lufs"])
        meter = pyln.Meter(clip.sample_rate)
        # pyloudnorm wants (frames,) mono or (frames, channels).
        data = clip.samples if clip.channels > 1 else clip.samples[:, 0]
        loudness = meter.integrated_loudness(data)

        if not np.isfinite(loudness):
            # Silence / too short to measure — leave it alone.
            return clip

        gain_db = target - loudness
        gain = 10 ** (gain_db / 20.0)
        out = clip.samples * gain

        ceiling = 10 ** (float(self.params["peak_ceiling_db"]) / 20.0)
        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > ceiling:
            out = out * (ceiling / peak)
        return clip.with_samples(out.astype(np.float32))

    def measure_lufs(self, clip: AudioClip) -> float:
        """Convenience for the UI: report current integrated loudness."""
        import pyloudnorm as pyln

        meter = pyln.Meter(clip.sample_rate)
        data = clip.samples if clip.channels > 1 else clip.samples[:, 0]
        return float(meter.integrated_loudness(data))
