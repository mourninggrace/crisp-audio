"""Voice clarity / presence enhancement.

Lifts the 2–5 kHz presence range where speech intelligibility lives, then runs
a gentle compressor so quiet consonants come forward without the louder vowels
clipping. Run late in the chain, after noise/reverb are gone, so we're not
amplifying artefacts.
"""
from __future__ import annotations

from crisp.core.audio import AudioClip
from crisp.core.dsp import peaking_eq, soft_compress
from crisp.core.processors.base import ParamSpec, Processor


class VoiceClarity(Processor):
    key = "clarity"
    label = "Enhance voice clarity"
    description = "Presence lift (2–5 kHz) plus gentle leveling."
    default_params = {
        "presence_hz": 3500.0,
        "presence_db": 3.0,
        "compress": True,
        "comp_threshold_db": -20.0,
        "comp_ratio": 2.5,
    }
    param_specs = [
        ParamSpec("presence_hz", "Presence freq", "float", 2000, 6000, 100, "Hz"),
        ParamSpec("presence_db", "Presence lift", "float", 0.0, 6.0, 0.5, "dB"),
        ParamSpec("compress", "Gentle leveling", "bool"),
        ParamSpec("comp_ratio", "Leveling ratio", "float", 1.5, 4.0, 0.1, ":1"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        sr = clip.sample_rate
        s = peaking_eq(
            clip.samples, sr,
            float(self.params["presence_hz"]),
            float(self.params["presence_db"]),
            q=0.9,
        )
        if self.params.get("compress", True):
            s = soft_compress(
                s,
                threshold_db=float(self.params["comp_threshold_db"]),
                ratio=float(self.params["comp_ratio"]),
            )
        return clip.with_samples(s)
