"""Tonal balancing EQ for spoken voice.

A conservative, broadcast-ish curve: roll off sub-sonic rumble, gently tame the
"boxy" low-mids, and add a touch of air. This is the safe corrective pass;
the brighter presence lift lives in :mod:`clarity`.
"""
from __future__ import annotations

from crisp.core.audio import AudioClip
from crisp.core.dsp import highpass, peaking_eq
from crisp.core.processors.base import ParamSpec, Processor


class EqBalance(Processor):
    key = "eq"
    label = "Balance EQ"
    description = "Corrective voice EQ: rumble cut, de-box, gentle air."
    default_params = {
        "rumble_hz": 80.0,     # high-pass cutoff
        "mud_hz": 300.0,       # boxy/muddy band to trim
        "mud_db": -2.5,
        "air_hz": 12000.0,     # high-shelf-ish air lift
        "air_db": 2.0,
    }
    param_specs = [
        ParamSpec("rumble_hz", "Rumble cut", "float", 40, 150, 5, "Hz"),
        ParamSpec("mud_db", "De-box", "float", -6.0, 0.0, 0.5, "dB"),
        ParamSpec("air_db", "Air", "float", 0.0, 6.0, 0.5, "dB"),
    ]

    def process(self, clip: AudioClip) -> AudioClip:
        sr = clip.sample_rate
        s = highpass(clip.samples, sr, float(self.params["rumble_hz"]), order=2)
        s = peaking_eq(s, sr, float(self.params["mud_hz"]), float(self.params["mud_db"]), q=1.0)
        s = peaking_eq(s, sr, float(self.params["air_hz"]), float(self.params["air_db"]), q=0.7)
        return clip.with_samples(s)
