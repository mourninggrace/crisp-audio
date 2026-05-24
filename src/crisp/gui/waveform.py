"""Waveform display widget (before/after) built on pyqtgraph.

Renders a min/max envelope rather than every sample so multi-minute clips draw
instantly. Two stacked plots share an x-axis: top = original, bottom = cleaned.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtWidgets

from crisp.core.audio import AudioClip

pg.setConfigOptions(antialias=True, background="#1e1e22", foreground="#b0b0b8")

_MAX_POINTS = 4000  # envelope resolution; plenty for any screen width


def _envelope(clip: AudioClip, buckets: int = _MAX_POINTS):
    """Downsample to (x, min, max) envelope arrays for fast plotting."""
    mono = clip.to_mono().samples[:, 0]
    n = len(mono)
    if n == 0:
        return np.array([0.0]), np.array([0.0]), np.array([0.0])
    buckets = min(buckets, n)
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    mins = np.empty(buckets, dtype=np.float32)
    maxs = np.empty(buckets, dtype=np.float32)
    for i in range(buckets):
        seg = mono[edges[i]:edges[i + 1]]
        if seg.size:
            mins[i] = seg.min()
            maxs[i] = seg.max()
        else:
            mins[i] = maxs[i] = 0.0
    times = (edges[:-1] / clip.sample_rate)
    return times, mins, maxs


class WaveformPair(QtWidgets.QWidget):
    """Two stacked, x-linked waveform plots."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._before = pg.PlotWidget(title="Original")
        self._after = pg.PlotWidget(title="Cleaned")
        for p in (self._before, self._after):
            p.setYRange(-1, 1)
            p.setMouseEnabled(y=False)
            p.showGrid(x=True, y=False, alpha=0.15)
            p.getAxis("left").setWidth(40)
        self._after.setXLink(self._before)

        # Playback cursor on both plots (x-linked, so one position drives both).
        pen = pg.mkPen("#ffcc44", width=1)
        self._playheads = [
            pg.InfiniteLine(pos=0, angle=90, pen=pen, movable=False)
            for _ in range(2)
        ]
        for plot, line in zip((self._before, self._after), self._playheads):
            line.setVisible(False)
            plot.addItem(line)

        layout.addWidget(self._before)
        layout.addWidget(self._after)

    def set_playhead(self, seconds: float | None) -> None:
        """Move the cursor to ``seconds``; pass ``None`` to hide it."""
        for line in self._playheads:
            if seconds is None:
                line.setVisible(False)
            else:
                line.setVisible(True)
                line.setPos(seconds)

    def _draw(self, plot: pg.PlotWidget, line, clip: AudioClip | None, color: str) -> None:
        # clear() drops every item including the playhead, so re-add it after.
        plot.clear()
        plot.addItem(line)
        if clip is None:
            return
        times, mins, maxs = _envelope(clip)
        brush = pg.mkBrush(color)
        # Fill between min and max for a classic filled-waveform look.
        curve = pg.FillBetweenItem(
            pg.PlotDataItem(times, maxs),
            pg.PlotDataItem(times, mins),
            brush=brush,
        )
        plot.addItem(curve)
        plot.setXRange(0, max(times[-1], 0.01), padding=0)

    def set_before(self, clip: AudioClip | None) -> None:
        self._draw(self._before, self._playheads[0], clip, "#4a9eff")

    def set_after(self, clip: AudioClip | None) -> None:
        self._draw(self._after, self._playheads[1], clip, "#43d17a")
