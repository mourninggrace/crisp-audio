"""Automatic audio analysis and intelligent settings recommendation.

Analyses a clip across several dimensions — noise floor, reverb tail, content
type, plosives, spectral tilt, and loudness — and builds a CleanupSettings
tailored to that specific recording.  No user input required.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from crisp.core.audio import AudioClip
from crisp.core.engine import CleanupSettings


@dataclass
class AnalysisReport:
    """Measurement results and the decisions made from them."""

    # --- Raw measurements ---
    lufs: float = float("-inf")
    snr_db: float = 0.0
    rt60_est_ms: float = 0.0
    is_speech: bool = True
    has_plosives: bool = False
    spectral_tilt_db: float = 0.0   # + = bright, - = dull/muffled

    # --- Human-readable decisions ---
    decisions: list[str] = field(default_factory=list)

    # --- Ready-to-run settings ---
    settings: CleanupSettings | None = None

    def summary_lines(self) -> list[str]:
        """Concise measurement summary for the UI report."""
        lufs_str = f"{self.lufs:.1f} LUFS" if self.lufs > -70 else "too quiet to measure"
        content = "speech/voice" if self.is_speech else "music/instrument"
        lines = [
            f"Content type  : {content}",
            f"Loudness      : {lufs_str}",
            f"Estimated SNR : {self.snr_db:.0f} dB",
            f"Reverb tail   : {self.rt60_est_ms:.0f} ms (RT60 est.)",
            f"Plosives      : {'detected' if self.has_plosives else 'none detected'}",
            f"Spectral tilt : {self.spectral_tilt_db:+.1f} dB (high vs low-mid)",
        ]
        return lines


# ---------------------------------------------------------------------------


class AutoAnalyser:
    """Analyses an :class:`AudioClip` and returns an :class:`AnalysisReport`."""

    def analyse(self, clip: AudioClip) -> AnalysisReport:
        report = AnalysisReport()
        mono = clip.to_mono().samples[:, 0].astype(np.float32)
        sr = clip.sample_rate

        report.lufs = self._measure_lufs(clip)
        report.snr_db = self._estimate_snr(mono)
        report.rt60_est_ms = self._estimate_rt60(mono, sr)
        report.is_speech = self._classify_content(mono, sr)
        report.has_plosives = self._detect_plosives(mono, sr)
        report.spectral_tilt_db = self._spectral_tilt(mono, sr)

        report.settings, report.decisions = self._build_settings(report)
        return report

    # ------------------------------------------------------------------
    # Measurement helpers
    # ------------------------------------------------------------------

    def _measure_lufs(self, clip: AudioClip) -> float:
        try:
            import pyloudnorm as pyln
            meter = pyln.Meter(clip.sample_rate)
            data = clip.samples if clip.channels > 1 else clip.samples[:, 0]
            lufs = float(meter.integrated_loudness(data))
            return lufs if np.isfinite(lufs) else float("-inf")
        except Exception:
            return float("-inf")

    def _estimate_snr(self, mono: np.ndarray) -> float:
        """Spectral SNR using Welch's averaged PSD + minimum noise floor.

        Welch averages overlapping frames → stable per-bin power estimate even
        for white noise (no wild single-bin dips).  A minimum filter then
        tracks the noise floor between harmonic peaks.  Global SNR = ratio of
        total power above the noise floor vs. the floor itself.
        """
        from scipy.signal import welch
        from scipy.ndimage import minimum_filter1d

        n = min(len(mono), 4 * 44100)
        nperseg = 2048
        _, psd = welch(
            mono[:n].astype(np.float64),
            fs=44100,
            nperseg=nperseg,
            noverlap=nperseg // 2,
        )

        if psd.max() < 1e-15:
            return 0.0

        # Noise floor: minimum of smoothed PSD over a window covering ~300 Hz.
        # At 44100 Hz with nperseg=2048, frequency resolution ≈ 21.5 Hz/bin.
        # 300 Hz / 21.5 Hz ≈ 14 bins.
        win = max(5, len(psd) // 40)
        noise_floor = minimum_filter1d(psd, size=win)
        noise_floor = np.maximum(noise_floor, 1e-20)

        total_power = float(np.sum(psd))
        noise_power = float(np.sum(noise_floor))
        signal_power = max(0.0, total_power - noise_power)

        if noise_power < 1e-20:
            return 60.0

        snr = 10 * np.log10((signal_power + 1e-20) / noise_power)
        return float(np.clip(snr, 0.0, 60.0))

    def _estimate_rt60(self, mono: np.ndarray, sr: int) -> float:
        """Estimate reverb decay from energy envelope after the loudest
        transient.  Returns approximate RT60 in milliseconds."""
        win = max(1, int(sr * 0.02))   # 20 ms
        hop = win // 2
        frames = range(0, len(mono) - win, hop)
        if not frames:
            return 0.0

        energy = np.array([float(np.mean(mono[i : i + win] ** 2)) for i in frames])
        if energy.max() < 1e-12:
            return 0.0

        peak_idx = int(np.argmax(energy))
        tail = energy[peak_idx:]
        if len(tail) < 5:
            return 0.0

        peak_db = 10 * np.log10(float(tail[0]) + 1e-12)
        target_db = peak_db - 30.0   # T30

        for i, e in enumerate(tail):
            if 10 * np.log10(float(e) + 1e-12) <= target_db:
                t30_ms = i * hop / sr * 1000
                return float(t30_ms * 2)   # extrapolate T30 → RT60

        # Energy never dropped 30 dB — return conservative upper bound
        return float(min(len(tail) * hop / sr * 1000, 2000))

    def _classify_content(self, mono: np.ndarray, sr: int) -> bool:
        """Return True if the clip sounds like speech/voice.

        Two-pronged test:
        1. Autocorrelation periodicity in the voiced F0 range (80–400 Hz).
           Real voiced speech (and voice-like synth) has a clear lag peak there.
        2. Spectral centroid stays below 4 kHz — music often has high-
           frequency energy that pushes the centroid up.

        ZCR is deliberately avoided — it's unreliable for low-pitched voices
        (male fundamentals at 80–150 Hz produce ZCR ≈ 0.003, well below any
        useful threshold).
        """
        from scipy.signal import stft as _stft

        # --- periodicity test (autocorrelation) ---
        lag_min = int(sr / 400)   # corresponds to 400 Hz
        lag_max = int(sr / 80)    # corresponds to  80 Hz
        frame_len = 2048          # ~46 ms at 44.1 kHz
        hop = sr // 4             # check every 250 ms

        voiced_frames = 0
        total_frames = 0
        for start in range(0, len(mono) - frame_len, hop):
            frame = mono[start : start + frame_len].astype(np.float64)
            # Normalize
            rms = np.sqrt(np.mean(frame ** 2))
            if rms < 1e-6:
                continue  # skip silence
            frame = frame / (rms + 1e-9)
            ac = np.correlate(frame, frame, mode="full")
            ac = ac[len(ac) // 2 :]   # one-sided
            ac = ac / (ac[0] + 1e-9)  # normalize to 1 at lag 0
            if lag_max >= len(ac):
                continue
            peak = float(np.max(ac[lag_min : lag_max + 1]))
            if peak > 0.25:
                voiced_frames += 1
            total_frames += 1

        voiced_frac = voiced_frames / max(1, total_frames)

        # Subharmonic check: if the dominant lag corresponds to a subharmonic
        # of a higher-freq musical note (e.g. 440 Hz -> peak at lag 200 = 220 Hz),
        # verify the implied F0 isn't above 400 Hz at half the lag.
        # If half-lag also has a strong peak above 400 Hz, it's likely music.
        subharmonic_frac = 0.0
        for start in range(0, len(mono) - frame_len, hop):
            frame = mono[start : start + frame_len].astype(np.float64)
            rms = np.sqrt(np.mean(frame ** 2))
            if rms < 1e-6:
                continue
            frame = frame / (rms + 1e-9)
            ac = np.correlate(frame, frame, mode="full")
            ac = ac[len(ac) // 2 :]
            ac = ac / (ac[0] + 1e-9)
            if lag_max >= len(ac):
                continue
            best_lag = lag_min + int(np.argmax(ac[lag_min : lag_max + 1]))
            half_lag = best_lag // 2
            # If half_lag is below lag_min (F0 at half_lag > 400 Hz = music range)
            # and has a meaningful AC peak, it's a subharmonic alias of music.
            if half_lag >= 4 and half_lag < lag_min:
                if float(ac[half_lag]) > 0.25:
                    subharmonic_frac += 1.0 / max(1, total_frames)

        # If most frames look like music subharmonics, override voiced_frac
        if subharmonic_frac > 0.5:
            voiced_frac = 0.0   # force "not speech"

        # Strong periodicity → voice, regardless of spectral centroid
        # (broadband noise swamps centroid even on clearly voiced signals).
        if voiced_frac > 0.55:
            return True

        # Ambiguous periodicity — use spectral centroid as a tiebreaker.
        # Music tends to have energy spread wide; voice+mid-freq content <4.5 kHz.
        try:
            f, _t, Zxx = _stft(mono, fs=sr, nperseg=1024)
            mag = np.abs(Zxx)
            col_sum = np.sum(mag, axis=0) + 1e-9
            centroids = np.sum(f[:, None] * mag, axis=0) / col_sum
            valid = centroids[centroids > 50]
            centroid = float(np.median(valid)) if len(valid) else 4000.0
        except Exception:
            centroid = 2000.0

        return voiced_frac > 0.25 and centroid < 4500

    def _detect_plosives(self, mono: np.ndarray, sr: int) -> bool:
        """Return True if sub-120 Hz energy has impulsive spikes
        consistent with breath pops / plosives."""
        from scipy.signal import butter, sosfilt

        sos = butter(4, 120.0 / (sr / 2), btype="lowpass", output="sos")
        low = sosfilt(sos, mono)

        win = max(1, int(sr * 0.01))   # 10 ms
        energy = np.convolve(np.abs(low), np.ones(win) / win, mode="same")
        median = float(np.median(energy)) + 1e-9
        return bool(np.any(energy > median * 4.5))

    def _spectral_tilt(self, mono: np.ndarray, sr: int) -> float:
        """Compare energy in the low-mids (200–2 kHz) vs highs (5–15 kHz).
        Returns dB difference; positive = brighter than average."""
        from scipy.signal import butter, sosfilt

        def _band_rms(lo: float, hi: float) -> float:
            nyq = sr / 2
            lo_n = max(lo / nyq, 0.001)
            hi_n = min(hi / nyq, 0.999)
            if lo_n >= hi_n:
                return 1e-12
            sos = butter(4, [lo_n, hi_n], btype="bandpass", output="sos")
            y = sosfilt(sos, mono)
            rms = float(np.sqrt(np.mean(y ** 2)))
            return rms if rms > 1e-12 else 1e-12

        low_mid = _band_rms(200, 2000)
        high = _band_rms(5000, min(15000, sr // 2 - 100))
        return float(20 * np.log10(high / low_mid))

    # ------------------------------------------------------------------
    # Settings builder
    # ------------------------------------------------------------------

    def _build_settings(
        self, report: AnalysisReport
    ) -> tuple[CleanupSettings, list[str]]:
        decisions: list[str] = []

        # Start with everything disabled; we'll selectively enable.
        all_keys = ["noise", "dereverb", "plosives", "eq", "clarity",
                    "trim", "chorus", "widener", "panner", "loudness"]
        enabled: dict[str, bool] = {k: False for k in all_keys}
        params: dict[str, dict] = {}

        # ── Noise reduction ──────────────────────────────────────────────
        if report.snr_db < 38:
            strength = self._remap(report.snr_db, 8, 38, 0.95, 0.45)
            stationary = report.snr_db < 18
            enabled["noise"] = True
            params["noise"] = {
                "strength": round(strength, 2),
                "stationary": stationary,
            }
            mode = "stationary" if stationary else "adaptive"
            decisions.append(
                f"Noise reduction {strength:.0%} [{mode}]  (SNR ≈ {report.snr_db:.0f} dB)"
            )

        # ── Dereverb ─────────────────────────────────────────────────────
        if report.rt60_est_ms > 180:
            strength = self._remap(report.rt60_est_ms, 180, 900, 0.35, 0.82)
            strength = round(min(strength, 0.82), 2)
            enabled["dereverb"] = True
            params["dereverb"] = {"strength": strength}
            decisions.append(
                f"Dereverb {strength:.0%}  (RT60 ≈ {report.rt60_est_ms:.0f} ms)"
            )

        # ── Plosive removal ──────────────────────────────────────────────
        if report.has_plosives and report.is_speech:
            enabled["plosives"] = True
            decisions.append("Plosive removal  (breath pops detected)")

        # ── EQ ───────────────────────────────────────────────────────────
        enabled["eq"] = True
        if report.is_speech:
            air_db = 2.0
            mud_db = -2.5
            rumble_hz = 80.0
        else:
            air_db = 1.0
            mud_db = -1.5
            rumble_hz = 40.0

        # Compensate for spectral imbalance
        if report.spectral_tilt_db < -15:
            air_db = min(air_db + 2.0, 4.5)
        elif report.spectral_tilt_db > 8:
            air_db = max(air_db - 1.0, 0.0)

        params["eq"] = {
            "rumble_hz": rumble_hz,
            "mud_db": mud_db,
            "air_db": round(air_db, 1),
        }
        curve = "voice" if report.is_speech else "music"
        decisions.append(
            f"EQ [{curve} curve]  rumble cut {rumble_hz:.0f} Hz, "
            f"de-box {mud_db:+.1f} dB, air {air_db:+.1f} dB"
        )

        # ── Voice clarity ────────────────────────────────────────────────
        if report.is_speech:
            enabled["clarity"] = True
            params["clarity"] = {
                "presence_db": 3.0,
                "compress": True,
                "comp_ratio": 2.5,
            }
            decisions.append("Voice clarity  (presence lift + gentle leveling)")

        # ── Trim silence ─────────────────────────────────────────────────
        enabled["trim"] = True
        decisions.append("Silence trimmed from start and end")

        # ── Creative effects: off in auto mode ───────────────────────────
        enabled["chorus"] = False
        enabled["widener"] = False
        enabled["panner"] = False

        # ── Loudness normalisation ────────────────────────────────────────
        enabled["loudness"] = True
        target_lufs = -16.0 if report.is_speech else -14.0
        params["loudness"] = {
            "target_lufs": target_lufs,
            "peak_ceiling_db": -1.0,
        }
        standard = "podcast/voice" if report.is_speech else "streaming/music"
        decisions.append(
            f"Loudness → {target_lufs:.0f} LUFS  ({standard} standard)"
        )

        return CleanupSettings(enabled=enabled, params=params), decisions

    @staticmethod
    def _remap(
        val: float, in_min: float, in_max: float,
        out_min: float, out_max: float,
    ) -> float:
        t = (val - in_min) / (in_max - in_min)
        t = max(0.0, min(1.0, t))
        return out_min + t * (out_max - out_min)
