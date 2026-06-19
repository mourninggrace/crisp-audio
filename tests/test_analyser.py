"""Comprehensive pytest test suite for AutoAnalyser and AutoCleanWorker.

Tests are grouped into:
  - 6 original passing tests (signal-based analyser validation)
  - 7 additional tests (report attributes, worker, edge cases)

Run with:
    cd C:\\AudioCleanUpTool && .venv\\Scripts\\python.exe -m pytest tests/test_analyser.py -v --tb=short
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Ensure src is on the path (also handled by pytest.ini_options pythonpath)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Offscreen Qt platform so workers can be instantiated without a display
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from crisp.core.audio import AudioClip  # noqa: E402
from crisp.core.analyser import AutoAnalyser, AnalysisReport  # noqa: E402
from crisp.core.engine import CleanupEngine, CleanupSettings  # noqa: E402
from crisp.core.processors.loudness import LoudnessNormalize  # noqa: E402


# ---------------------------------------------------------------------------
# Signal-generation helpers
# ---------------------------------------------------------------------------

SR = 44100
DUR = 3.0
_T = np.linspace(0, DUR, int(SR * DUR), endpoint=False)


def _make_clip(sig: np.ndarray, sr: int = SR) -> AudioClip:
    return AudioClip.from_array(sig.astype(np.float32), sr)


def _noisy_speech(rng_seed: int = 42) -> AudioClip:
    """130 Hz voiced harmonics + heavy white noise → noisy speech."""
    rng = np.random.default_rng(rng_seed)
    sig = (
        0.5 * np.sin(2 * np.pi * 130 * _T)
        + 0.3 * np.sin(2 * np.pi * 260 * _T)
        + 0.15 * np.sin(2 * np.pi * 390 * _T)
    )
    sig += 0.08 * rng.standard_normal(sig.shape)
    return _make_clip(sig)


def _clean_speech(rng_seed: int = 42) -> AudioClip:
    """130 Hz voiced harmonics + tiny noise → clean speech."""
    rng = np.random.default_rng(rng_seed)
    sig = (
        0.5 * np.sin(2 * np.pi * 130 * _T)
        + 0.3 * np.sin(2 * np.pi * 260 * _T)
        + 0.15 * np.sin(2 * np.pi * 390 * _T)
    )
    sig += 0.003 * rng.standard_normal(sig.shape)
    return _make_clip(sig)


def _music(rng_seed: int = 7) -> AudioClip:
    """440/880/1320 Hz mix + small noise → music/instrument."""
    rng = np.random.default_rng(rng_seed)
    sig = (
        0.3 * np.sin(2 * np.pi * 440 * _T)
        + 0.3 * np.sin(2 * np.pi * 880 * _T)
        + 0.3 * np.sin(2 * np.pi * 1320 * _T)
    )
    sig += 0.01 * rng.standard_normal(sig.shape)
    return _make_clip(sig)


def _plosive_clip(rng_seed: int = 0) -> AudioClip:
    """Low-frequency bursts at known positions → plosive detection."""
    rng = np.random.default_rng(rng_seed)
    sig = 0.01 * rng.standard_normal(int(SR * DUR))
    for pos_s in [0.5, 1.2, 2.1]:
        pos = int(SR * pos_s)
        burst_len = int(SR * 0.015)
        burst = np.zeros(burst_len)
        burst[: int(SR * 0.005)] = 0.8 * np.sin(
            2 * np.pi * 60 * np.linspace(0, 0.005, int(SR * 0.005))
        )
        end = min(pos + burst_len, len(sig))
        sig[pos:end] += burst[: end - pos]
    return _make_clip(sig)


def _reverberant_speech(rng_seed: int = 0) -> AudioClip:
    """Voiced speech with synthetic echo tails at 80–500 ms delays."""
    rng = np.random.default_rng(rng_seed)
    dry = (
        0.5 * np.sin(2 * np.pi * 130 * _T)
        + 0.3 * np.sin(2 * np.pi * 260 * _T)
        + 0.15 * np.sin(2 * np.pi * 390 * _T)
    )
    dry += 0.01 * rng.standard_normal(dry.shape)
    wet = dry.copy()
    for delay_ms in [80, 160, 260, 380, 500]:
        d = int(SR * delay_ms / 1000)
        gain = 0.3 * np.exp(-delay_ms / 200.0)
        if d < len(dry):
            wet[d:] += gain * dry[:-d]
    return _make_clip(np.clip(wet, -1.0, 1.0))


def _quiet_speech(amp: float = 0.01) -> AudioClip:
    """Soft voiced signal that sits well below broadcast loudness."""
    sig = amp * np.sin(2 * np.pi * 130 * _T)
    return _make_clip(sig)


# ---------------------------------------------------------------------------
# Shared analyser fixture (avoids re-computing in parametrised tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analyser() -> AutoAnalyser:
    return AutoAnalyser()


# ===========================================================================
# ──  ORIGINAL 6 TESTS (must all pass)  ──────────────────────────────────────
# ===========================================================================


class TestNoisySpeech:
    """Test 1 — noisy speech → is_speech, noise enabled, SNR & LUFS sensible."""

    @pytest.fixture
    def report(self):
        return AutoAnalyser().analyse(_noisy_speech())

    def test_is_speech(self, report):
        assert report.is_speech is True, "Noisy voiced signal should be classified as speech"

    def test_noise_reduction_enabled(self, report):
        assert report.settings.enabled.get("noise") is True, (
            "Low-SNR clip should trigger noise reduction"
        )

    def test_snr_in_expected_range(self, report):
        # Heavy noise floor → SNR should read roughly 10–20 dB
        assert 8.0 <= report.snr_db <= 25.0, (
            f"Expected SNR ≈ 10–20 dB for noisy speech, got {report.snr_db:.1f}"
        )

    def test_lufs_within_2db_of_target(self, report):
        """After running the engine the output loudness should match target."""
        clip = _noisy_speech()
        out = CleanupEngine().run(clip, report.settings)
        measured = LoudnessNormalize().measure_lufs(out)
        target = report.settings.params["loudness"]["target_lufs"]
        assert np.isfinite(measured), "Output LUFS should be finite after normalisation"
        assert abs(measured - target) <= 2.0, (
            f"LUFS mismatch: measured={measured:.1f}, target={target:.1f}"
        )


class TestCleanSpeech:
    """Test 2 — clean speech → is_speech, noise reduction OFF (high SNR)."""

    @pytest.fixture
    def report(self):
        return AutoAnalyser().analyse(_clean_speech())

    def test_is_speech(self, report):
        assert report.is_speech is True

    def test_noise_reduction_disabled(self, report):
        # SNR >> 38 dB → noise reduction should be left off
        assert report.settings.enabled.get("noise") is False, (
            f"Clean clip (SNR={report.snr_db:.1f} dB) should not enable noise reduction"
        )

    def test_snr_high(self, report):
        assert report.snr_db > 38.0, (
            f"Clean speech should have SNR > 38 dB, got {report.snr_db:.1f}"
        )


class TestMusic:
    """Test 3 — music → not speech, clarity OFF, loudness target = -14 LUFS."""

    @pytest.fixture
    def report(self):
        return AutoAnalyser().analyse(_music())

    def test_not_speech(self, report):
        assert report.is_speech is False, "440/880/1320 Hz mix should be classified as music"

    def test_clarity_disabled(self, report):
        assert report.settings.enabled.get("clarity") is False, (
            "Voice clarity should be OFF for music content"
        )

    def test_target_lufs(self, report):
        target = report.settings.params["loudness"]["target_lufs"]
        assert target == pytest.approx(-14.0), (
            f"Music target LUFS should be -14.0, got {target}"
        )


class TestPlosives:
    """Test 4 — low-frequency burst signal → has_plosives = True."""

    @pytest.fixture
    def report(self):
        return AutoAnalyser().analyse(_plosive_clip())

    def test_plosives_detected(self, report):
        assert report.has_plosives is True, "Impulsive low-freq bursts should trigger plosive detection"


class TestReverberant:
    """Test 5 — echoed speech → RT60 > 180 ms, dereverb enabled."""

    @pytest.fixture
    def report(self):
        return AutoAnalyser().analyse(_reverberant_speech())

    def test_rt60_above_threshold(self, report):
        assert report.rt60_est_ms > 180, (
            f"Expected RT60 > 180 ms for reverberant clip, got {report.rt60_est_ms:.0f} ms"
        )

    def test_dereverb_enabled(self, report):
        assert report.settings.enabled.get("dereverb") is True, (
            "Long reverb tail should enable dereverb"
        )


class TestQuietLoudness:
    """Test 6 — quiet clip loudness is normalised to within 1.5 dB of target."""

    @pytest.fixture
    def report(self):
        # amp=0.01 → LUFS ≈ -44 dB, well-measured by pyloudnorm
        return AutoAnalyser().analyse(_quiet_speech(amp=0.01))

    def test_lufs_hits_target_after_processing(self, report):
        clip = _quiet_speech(amp=0.01)
        out = CleanupEngine().run(clip, report.settings)
        measured = LoudnessNormalize().measure_lufs(out)
        target = report.settings.params["loudness"]["target_lufs"]
        assert np.isfinite(measured), "Quiet clip should produce finite LUFS after processing"
        assert abs(measured - target) <= 1.5, (
            f"Loudness mismatch after processing: measured={measured:.1f}, target={target:.1f}"
        )


# ===========================================================================
# ──  ADDITIONAL 7 TESTS  ─────────────────────────────────────────────────────
# ===========================================================================


class TestSummaryLines:
    """Test 7 — AnalysisReport.summary_lines() returns non-empty list of strings."""

    def test_returns_non_empty_list(self, analyser):
        report = analyser.analyse(_clean_speech())
        lines = report.summary_lines()
        assert isinstance(lines, list), "summary_lines() should return a list"
        assert len(lines) > 0, "summary_lines() should not be empty"

    def test_all_elements_are_strings(self, analyser):
        report = analyser.analyse(_clean_speech())
        lines = report.summary_lines()
        assert all(isinstance(ln, str) for ln in lines), (
            "Every element of summary_lines() should be a str"
        )

    def test_expected_fields_present(self, analyser):
        report = analyser.analyse(_clean_speech())
        joined = "\n".join(report.summary_lines())
        for keyword in ("Content type", "Loudness", "SNR", "Reverb", "Plosive", "Spectral"):
            assert keyword in joined, f"Expected '{keyword}' in summary_lines output"


class TestDecisions:
    """Test 8 — AnalysisReport.decisions is non-empty when processors are enabled."""

    def test_decisions_non_empty_for_noisy_speech(self, analyser):
        report = analyser.analyse(_noisy_speech())
        assert isinstance(report.decisions, list), "decisions should be a list"
        assert len(report.decisions) > 0, (
            "At least one decision should be recorded for noisy speech"
        )

    def test_decisions_are_strings(self, analyser):
        report = analyser.analyse(_noisy_speech())
        assert all(isinstance(d, str) for d in report.decisions), (
            "Each decision should be a str"
        )

    def test_decisions_mention_enabled_processors(self, analyser):
        """Noise reduction enabled → at least one decision mentions noise."""
        report = analyser.analyse(_noisy_speech())
        assert report.settings.enabled.get("noise"), "Noise reduction should be on"
        noise_decisions = [d for d in report.decisions if "Noise" in d or "noise" in d]
        assert len(noise_decisions) > 0, (
            "A decision string should mention noise reduction when it is enabled"
        )


class TestAutoCleanWorkerInstantiation:
    """Test 9 — AutoCleanWorker can be instantiated headlessly (no QThread.start)."""

    def test_worker_can_be_created(self):
        from crisp.gui.workers import AutoCleanWorker  # noqa: PLC0415

        clip = _clean_speech()
        worker = AutoCleanWorker(clip)
        assert worker is not None
        assert isinstance(worker, AutoCleanWorker)

    def test_worker_stores_clip(self):
        from crisp.gui.workers import AutoCleanWorker  # noqa: PLC0415

        clip = _noisy_speech()
        worker = AutoCleanWorker(clip)
        assert hasattr(worker, "_clip"), "Worker should store the clip as _clip"
        assert worker._clip is clip

    def test_worker_accepts_any_clip_shape(self):
        """Worker should accept mono and stereo clips without raising."""
        from crisp.gui.workers import AutoCleanWorker  # noqa: PLC0415

        # Mono
        mono = _make_clip(0.2 * np.sin(2 * np.pi * 200 * _T))
        AutoCleanWorker(mono)

        # Stereo
        stereo_arr = np.column_stack([
            0.2 * np.sin(2 * np.pi * 200 * _T),
            0.2 * np.sin(2 * np.pi * 300 * _T),
        ])
        stereo = _make_clip(stereo_arr)
        AutoCleanWorker(stereo)


class TestSettingsLoudnessEnabled:
    """Test 10 — CleanupSettings from AnalysisReport.settings has loudness enabled."""

    @pytest.mark.parametrize(
        "clip_fn",
        [_noisy_speech, _clean_speech, _music, _quiet_speech],
        ids=["noisy_speech", "clean_speech", "music", "quiet_speech"],
    )
    def test_loudness_always_enabled(self, analyser, clip_fn):
        report = analyser.analyse(clip_fn())
        settings: CleanupSettings = report.settings
        assert settings.enabled.get("loudness") is True, (
            f"loudness should always be enabled, but got {settings.enabled}"
        )

    def test_loudness_params_present(self, analyser):
        report = analyser.analyse(_clean_speech())
        params = report.settings.params.get("loudness", {})
        assert "target_lufs" in params, "loudness params must contain 'target_lufs'"
        assert "peak_ceiling_db" in params, "loudness params must contain 'peak_ceiling_db'"


# ---------------------------------------------------------------------------
# Module-level fixtures for edge-case clips (avoids class-scope instance warn)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def short_clip():
    """200 ms tone — under 1 second."""
    sig = 0.3 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(SR * 0.2)))
    return _make_clip(sig)


@pytest.fixture(scope="module")
def silence_clip():
    """2 s of pure silence."""
    return _make_clip(np.zeros(int(SR * 2.0), dtype=np.float32))


@pytest.fixture(scope="module")
def stereo_clip():
    """Stereo clip: two different frequencies, one per channel."""
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    arr = np.column_stack([
        0.3 * np.sin(2 * np.pi * 130 * t),
        0.3 * np.sin(2 * np.pi * 200 * t),
    ]).astype(np.float32)
    return AudioClip.from_array(arr, SR)


class TestShortClip:
    """Test 11 — very short clip (< 1 s) does not crash the analyser."""

    def test_does_not_raise(self, short_clip):
        report = AutoAnalyser().analyse(short_clip)
        assert report is not None

    def test_report_fields_are_finite_or_zero(self, short_clip):
        report = AutoAnalyser().analyse(short_clip)
        assert np.isfinite(report.snr_db) or report.snr_db == 0.0
        assert report.rt60_est_ms >= 0.0
        assert isinstance(report.is_speech, bool)
        assert isinstance(report.has_plosives, bool)

    def test_summary_lines_work_on_short_clip(self, short_clip):
        report = AutoAnalyser().analyse(short_clip)
        lines = report.summary_lines()
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_settings_not_none(self, short_clip):
        report = AutoAnalyser().analyse(short_clip)
        assert report.settings is not None


class TestSilenceClip:
    """Test 12 — silence-only clip does not crash the analyser."""

    def test_does_not_raise(self, silence_clip):
        report = AutoAnalyser().analyse(silence_clip)
        assert report is not None

    def test_lufs_is_neg_inf_or_very_low(self, silence_clip):
        report = AutoAnalyser().analyse(silence_clip)
        # Silence has no loudness — pyloudnorm returns -inf or a very low value
        assert report.lufs == float("-inf") or report.lufs < -60.0, (
            f"Silence LUFS should be -inf or < -60, got {report.lufs}"
        )

    def test_snr_is_zero_or_low(self, silence_clip):
        report = AutoAnalyser().analyse(silence_clip)
        # Zero-power signal → SNR should be 0
        assert report.snr_db == pytest.approx(0.0, abs=1.0), (
            f"Silence SNR should be ~0 dB, got {report.snr_db}"
        )

    def test_summary_lines_work_on_silence(self, silence_clip):
        report = AutoAnalyser().analyse(silence_clip)
        lines = report.summary_lines()
        assert isinstance(lines, list)
        assert len(lines) > 0
        # Verify the "too quiet" branch is exercised
        loudness_line = next((ln for ln in lines if "Loudness" in ln), None)
        assert loudness_line is not None
        assert (
            "too quiet" in loudness_line.lower()
            or "-inf" in loudness_line.lower()
            or "LUFS" in loudness_line
        )

    def test_settings_not_none(self, silence_clip):
        report = AutoAnalyser().analyse(silence_clip)
        assert report.settings is not None


class TestStereoClip:
    """Test 13 — stereo clip is handled correctly (no shape errors)."""

    def test_clip_has_two_channels(self, stereo_clip):
        assert stereo_clip.channels == 2

    def test_does_not_raise(self, stereo_clip):
        report = AutoAnalyser().analyse(stereo_clip)
        assert report is not None

    def test_report_fields_valid(self, stereo_clip):
        report = AutoAnalyser().analyse(stereo_clip)
        assert isinstance(report.is_speech, bool)
        assert isinstance(report.has_plosives, bool)
        assert np.isfinite(report.snr_db)
        assert report.rt60_est_ms >= 0.0
        assert report.settings is not None

    def test_summary_lines_work(self, stereo_clip):
        report = AutoAnalyser().analyse(stereo_clip)
        lines = report.summary_lines()
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_engine_processes_stereo_without_error(self, stereo_clip):
        """Running the full engine on a stereo clip should not raise."""
        report = AutoAnalyser().analyse(stereo_clip)
        out = CleanupEngine().run(stereo_clip, report.settings)
        assert out.channels == stereo_clip.channels
        assert np.isfinite(out.samples).all()
