"""GUI smoke tests — no visual output required, just instantiation."""
from __future__ import annotations

import pytest

pytest_plugins = ("pytester",)


def test_float_slider_instantiates(qapp):
    """FloatSlider can be constructed without crashing."""
    from PySide6.QtCore import Qt
    from crisp.gui.widgets import FloatSlider
    from crisp.core.processors.base import ParamSpec

    spec = ParamSpec(key="threshold", label="Threshold", minimum=-60, maximum=0, step=1, unit="dB")
    slider = FloatSlider(spec, value=-24.0)
    # Force layoutcalc so widgets are properly created
    slider.resize(300, 50)


def test_processor_panel_instantiates(qapp):
    """ProcessorPanel can be constructed without crashing."""
    from crisp.gui.widgets import ProcessorPanel
    from crisp.core.processors.noise import NoiseReduction

    panel = ProcessorPanel(
        proc_cls=NoiseReduction,
        enabled=True,
        params={},
        on_enabled=lambda k, v: None,
        on_param=lambda k, p, v: None,
    )
    assert panel.isChecked()


def test_waveform_pair_instantiates(qapp):
    """WaveformPair can be constructed."""
    from crisp.gui.waveform import WaveformPair
    from crisp.core.audio import AudioClip

    w = WaveformPair()
    w.resize(800, 300)


def test_cleanup_worker_instantiates():
    """CleanupWorker can be constructed (but won't run without a thread)."""
    from crisp.gui.workers import CleanupWorker
    from crisp.core.audio import AudioClip
    from crisp.core.engine import CleanupSettings

    clip = AudioClip.from_array([0.1] * 48000, sample_rate=48000)
    settings = CleanupSettings.defaults()
    worker = CleanupWorker(clip, settings)
    assert worker.clip is clip


def test_ab_player_instantiates(qapp):
    """ABPlayer can be constructed (uses sounddevice silently)."""
    from crisp.gui.player import ABPlayer

    player = ABPlayer()
    # Ensure it shuts down cleanly
    player.stop()
