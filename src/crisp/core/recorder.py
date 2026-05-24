"""Input-device enumeration and live recording via sounddevice."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from crisp.core.audio import AudioClip


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: int


def list_input_devices() -> list[InputDevice]:
    """Return every device exposing at least one input channel."""
    import sounddevice as sd

    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            devices.append(
                InputDevice(
                    index=idx,
                    name=dev["name"],
                    max_input_channels=dev["max_input_channels"],
                    default_samplerate=int(dev.get("default_samplerate") or 44100),
                )
            )
    return devices


def default_input_device() -> InputDevice | None:
    devices = list_input_devices()
    if not devices:
        return None
    import sounddevice as sd

    try:
        default_idx = sd.default.device[0]
    except Exception:
        default_idx = devices[0].index
    for d in devices:
        if d.index == default_idx:
            return d
    return devices[0]


class Recorder:
    """Streams audio from an input device into an in-memory buffer.

    Usage::

        rec = Recorder(device_index=1, sample_rate=48000, channels=1)
        rec.start()
        ...                       # GUI keeps running
        clip = rec.stop()         # -> AudioClip

    A ``level_callback`` (if given) is invoked from the audio thread with the
    current block's peak level (0..1), suitable for a VU meter.
    """

    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = 48000,
        channels: int = 1,
        level_callback=None,
    ) -> None:
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.level_callback = level_callback
        self._blocks: list[np.ndarray] = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._blocks = []

        def _callback(indata, frames, time_info, status):  # noqa: ANN001
            self._blocks.append(indata.copy())
            if self.level_callback is not None:
                self.level_callback(float(np.max(np.abs(indata))) if frames else 0.0)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device_index,
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def stop(self) -> AudioClip:
        if self._stream is None:
            raise RuntimeError("Recorder is not running")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._blocks:
            empty = np.zeros((0, self.channels), dtype=np.float32)
            return AudioClip(empty, self.sample_rate)
        data = np.concatenate(self._blocks, axis=0)
        return AudioClip(data, self.sample_rate)
