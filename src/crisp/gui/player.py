"""Simple non-blocking playback with an A/B switch.

Holds the original and cleaned clips. Playback runs on sounddevice's own
callback thread; switching A/B swaps the source at the current play position so
the comparison feels instant.
"""
from __future__ import annotations

import threading

import numpy as np

from crisp.core.audio import AudioClip


class ABPlayer:
    def __init__(self) -> None:
        self._clips: dict[str, AudioClip | None] = {"A": None, "B": None}
        self._source = "A"
        self._pos = 0
        self._stream = None
        self._lock = threading.Lock()

    def set_clip(self, slot: str, clip: AudioClip | None) -> None:
        assert slot in ("A", "B")
        with self._lock:
            self._clips[slot] = clip

    @property
    def source(self) -> str:
        return self._source

    def toggle(self) -> str:
        """Swap A<->B without interrupting playback. Returns new source."""
        with self._lock:
            self._source = "B" if self._source == "A" else "A"
        return self._source

    def select(self, slot: str) -> None:
        with self._lock:
            self._source = slot

    def _current(self) -> AudioClip | None:
        clip = self._clips[self._source]
        # Fall back to whichever slot has audio (e.g. before cleanup exists).
        if clip is None:
            other = "B" if self._source == "A" else "A"
            clip = self._clips[other]
        return clip

    def play(self) -> None:
        import sounddevice as sd

        self.stop()
        clip = self._current()
        if clip is None or clip.frames == 0:
            return
        self._pos = 0

        def _callback(outdata, frames, time_info, status):  # noqa: ANN001
            with self._lock:
                clip = self._current()
                if clip is None:
                    outdata.fill(0)
                    raise sd.CallbackStop
                chunk = clip.samples[self._pos:self._pos + frames]
                n = len(chunk)
                ch = outdata.shape[1]
                # Match channel count of the output stream.
                if chunk.shape[1] == 1 and ch > 1:
                    chunk = np.repeat(chunk, ch, axis=1)
                elif chunk.shape[1] > ch:
                    chunk = chunk[:, :ch]
                outdata[:n] = chunk
                if n < frames:
                    outdata[n:] = 0
                    self._pos += n
                    raise sd.CallbackStop
                self._pos += frames

        clip = self._current()
        self._stream = sd.OutputStream(
            samplerate=clip.sample_rate,
            channels=max(c.channels for c in self._clips.values() if c is not None),
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @property
    def is_playing(self) -> bool:
        return self._stream is not None and self._stream.active

    def position_seconds(self) -> float:
        """Current playback position in seconds (0 if nothing is loaded)."""
        with self._lock:
            clip = self._current()
            if clip is None or clip.sample_rate == 0:
                return 0.0
            return self._pos / clip.sample_rate
