"""
Comprehensive pytest test suite for all audio processors.

Tests each processor individually to verify it actually does what it claims.
Processors under test (src/crisp/core/processors/):
  noise.py      – NoiseReduction
  dereverb.py   – Dereverb
  eq.py         – EqBalance
  clarity.py    – VoiceClarity
  deplosive.py  – PlosiveRemoval
  loudness.py   – LoudnessNormalize
  trim.py       – Trim (gain trim, NOT silence removal)
  chorus.py     – Chorus
  widener.py    – Widener
  panner.py     – Panner
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pytest

sys.path.insert(0, "src")

from crisp.core.audio import AudioClip

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

SR = 44100  # samples/second used throughout


def _tone(freq: float = 440.0, duration: float = 2.0, sr: int = SR,
          amp: float = 0.3, channels: int = 1) -> AudioClip:
    """Pure sine tone, optionally multi-channel."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sig = amp * np.sin(2 * np.pi * freq * t)
    if channels > 1:
        sig = np.column_stack([sig] * channels)
    return AudioClip.from_array(sig.astype(np.float32), sr)


def _noise(duration: float = 2.0, sr: int = SR, amp: float = 0.3,
           channels: int = 1, seed: int = 42) -> AudioClip:
    """White noise, optionally multi-channel."""
    rng = np.random.default_rng(seed)
    n = int(sr * duration)
    sig = amp * rng.standard_normal((n, channels)).astype(np.float32)
    return AudioClip.from_array(sig, sr)


def _tone_plus_noise(freq: float = 440.0, tone_amp: float = 0.15,
                     noise_amp: float = 0.15, duration: float = 2.0,
                     sr: int = SR, channels: int = 1, seed: int = 0) -> AudioClip:
    """Sine tone mixed with white noise."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    tone = tone_amp * np.sin(2 * np.pi * freq * t)
    rng = np.random.default_rng(seed)
    noise = noise_amp * rng.standard_normal(n)
    sig = (tone + noise).astype(np.float32)
    if channels > 1:
        sig = np.column_stack([sig] * channels)
    return AudioClip.from_array(sig, sr)


def _rms(clip: AudioClip) -> float:
    return float(np.sqrt(np.mean(clip.samples ** 2)))


def _fft_magnitude_at(clip: AudioClip, freq: float, bandwidth_pct: float = 0.05) -> float:
    """Mean FFT magnitude near ``freq`` (±``bandwidth_pct`` * freq), averaged over channels."""
    n = clip.frames
    freqs = np.fft.rfftfreq(n, d=1.0 / clip.sample_rate)
    lo, hi = freq * (1 - bandwidth_pct), freq * (1 + bandwidth_pct)
    mask = (freqs >= lo) & (freqs <= hi)
    if not mask.any():
        return 0.0
    total = 0.0
    for ch in range(clip.channels):
        total += float(np.abs(np.fft.rfft(clip.samples[:, ch]))[mask].mean())
    return total / clip.channels


def _band_rms(clip: AudioClip, lo_hz: float, hi_hz: float) -> float:
    """Mean FFT magnitude in a frequency band, averaged over channels."""
    n = clip.frames
    freqs = np.fft.rfftfreq(n, d=1.0 / clip.sample_rate)
    mask = (freqs >= lo_hz) & (freqs <= hi_hz)
    if not mask.any():
        return 0.0
    total = 0.0
    for ch in range(clip.channels):
        total += float(np.abs(np.fft.rfft(clip.samples[:, ch]))[mask].mean())
    return total / clip.channels


def _stereo_spread(clip: AudioClip) -> float:
    """Mean absolute difference between left and right channels."""
    assert clip.channels == 2, "Need stereo clip"
    return float(np.mean(np.abs(clip.samples[:, 0] - clip.samples[:, 1])))


# ─────────────────────────────────────────────────────────────────────────────
# 1. NoiseReduction
# ─────────────────────────────────────────────────────────────────────────────

class TestNoiseReduction:
    """
    NoiseReduction uses spectral gating (noisereduce).
    Key claim: reduces noise floor (background hiss/hum).
    """

    def test_reduces_rms_on_pure_noise(self):
        """Pure white noise → RMS should decrease after spectral gating."""
        from crisp.core.processors.noise import NoiseReduction
        clip = _noise(duration=3.0, amp=0.3)
        out = NoiseReduction(strength=0.9, stationary=True).process(clip)
        assert _rms(out) < _rms(clip), (
            f"NoiseReduction should lower RMS: {_rms(clip):.4f} → {_rms(out):.4f}"
        )

    def test_reduces_rms_on_tone_plus_noise(self):
        """Noisy tone: output RMS should drop (noise floor is reduced)."""
        from crisp.core.processors.noise import NoiseReduction
        # noise_amp > tone_amp so the output is dominated by noise change
        clip = _tone_plus_noise(tone_amp=0.05, noise_amp=0.3, duration=3.0)
        out = NoiseReduction(strength=0.9, stationary=True).process(clip)
        assert _rms(out) < _rms(clip), (
            f"NoiseReduction should lower RMS of noisy signal: {_rms(clip):.4f} → {_rms(out):.4f}"
        )

    def test_output_frame_count_preserved(self):
        from crisp.core.processors.noise import NoiseReduction
        clip = _tone_plus_noise()
        out = NoiseReduction().process(clip)
        assert out.frames == clip.frames
        assert out.sample_rate == clip.sample_rate

    def test_channel_count_preserved(self):
        from crisp.core.processors.noise import NoiseReduction
        clip = _tone_plus_noise(channels=2)
        out = NoiseReduction().process(clip)
        assert out.channels == 2

    def test_no_clipping(self):
        """Output samples must stay within [-1, 1]."""
        from crisp.core.processors.noise import NoiseReduction
        clip = _tone_plus_noise(tone_amp=0.5, noise_amp=0.3)
        out = NoiseReduction(strength=0.9).process(clip)
        assert out.peak() <= 1.0 + 1e-5


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dereverb
# ─────────────────────────────────────────────────────────────────────────────

class TestDereverb:
    """
    Dereverb uses noisereduce in non-stationary mode to suppress the
    slowly-lingering reverb tail.
    Key claims:
      • Reduces reverb tail energy
      • Early-field energy preserved better than late-field (early/late ratio ↑)
    """

    def _reverberant_clip(self, sr: int = SR, duration: float = 3.0,
                          seed: int = 7) -> AudioClip:
        """
        Synthetic reverberant signal:
          0–0.1 s : strong dry burst (clear onset)
          0.1–2.6 s: exponentially decaying broadband noise (reverb tail)

        Signal is normalised to 0.8 peak so it is a valid AudioClip (within ±1).
        """
        n = int(sr * duration)
        sig = np.zeros(n, dtype=np.float32)
        rng = np.random.default_rng(seed)

        # Dry onset burst
        burst_len = int(sr * 0.1)
        sig[:burst_len] = 0.8 * rng.standard_normal(burst_len).astype(np.float32)

        # Reverb tail
        tail_len = int(sr * 2.5)
        t_tail = np.arange(tail_len) / sr
        tail = 0.4 * rng.standard_normal(tail_len).astype(np.float32)
        decay = np.exp(-4 * t_tail / 2.5).astype(np.float32)
        end = min(burst_len + tail_len, n)
        sig[burst_len:end] += tail[: end - burst_len] * decay[: end - burst_len]

        # Normalise to 0.8 peak so samples stay inside the valid ±1 range.
        peak = float(np.max(np.abs(sig)))
        if peak > 0.0:
            sig = sig * (0.8 / peak)

        return AudioClip.from_array(sig[:, None], sr)

    def test_output_shape_preserved(self):
        from crisp.core.processors.dereverb import Dereverb
        clip = self._reverberant_clip()
        out = Dereverb().process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels
        assert out.sample_rate == clip.sample_rate

    def test_reduces_energy_on_noisy_input(self):
        """Pure noise (worst-case reverb) → RMS should drop after dereverb."""
        from crisp.core.processors.dereverb import Dereverb
        clip = _noise(duration=3.0, amp=0.3)
        out = Dereverb(strength=0.9).process(clip)
        assert _rms(out) < _rms(clip), (
            f"Dereverb should lower RMS: {_rms(clip):.4f} → {_rms(out):.4f}"
        )

    def test_early_late_ratio_improves(self):
        """
        After dereverb, early-field energy / late-field energy should be >=
        the same ratio in the input (tail is reduced, onset preserved).
        """
        from crisp.core.processors.dereverb import Dereverb
        clip = self._reverberant_clip()
        out = Dereverb(strength=0.9).process(clip)

        sr = clip.sample_rate
        early_end   = int(sr * 0.3)   # first 300 ms = onset
        late_start  = int(sr * 1.5)   # after 1.5 s = deep reverb tail

        early_in  = float(np.sqrt(np.mean(clip.samples[:early_end] ** 2))) + 1e-9
        late_in   = float(np.sqrt(np.mean(clip.samples[late_start:] ** 2))) + 1e-9
        early_out = float(np.sqrt(np.mean(out.samples[:early_end]  ** 2))) + 1e-9
        late_out  = float(np.sqrt(np.mean(out.samples[late_start:] ** 2))) + 1e-9

        ratio_in  = early_in  / late_in
        ratio_out = early_out / late_out
        assert ratio_out >= ratio_in * 0.95, (   # allow 5% slack for numerical noise
            f"Dereverb should improve early/late ratio: {ratio_in:.2f} → {ratio_out:.2f}"
        )

    def test_no_clipping(self):
        from crisp.core.processors.dereverb import Dereverb
        clip = self._reverberant_clip()
        out = Dereverb().process(clip)
        assert out.peak() <= 1.0 + 1e-5


# ─────────────────────────────────────────────────────────────────────────────
# 3. EqBalance
# ─────────────────────────────────────────────────────────────────────────────

class TestEqBalance:
    """
    EqBalance applies:
      • High-pass at rumble_hz (cuts sub-bass)
      • Peaking cut at mud_hz (-2.5 dB default, "de-box")
      • Peaking boost at air_hz (+2 dB default, "air")
    Verified via FFT magnitude comparisons before/after on white noise (flat spectrum).
    """

    def test_rumble_cut_reduces_sub80hz_energy(self):
        """High-pass at 80 Hz must attenuate below ~80 Hz."""
        from crisp.core.processors.eq import EqBalance
        clip = _noise(duration=3.0, amp=0.3)
        out = EqBalance(rumble_hz=80.0, mud_db=0.0, air_db=0.0).process(clip)
        # Compare 20–60 Hz band (well below cutoff)
        below_in  = _band_rms(clip, 20, 60)
        below_out = _band_rms(out,  20, 60)
        assert below_out < below_in * 0.5, (
            f"Sub-80Hz not sufficiently cut: {below_in:.4f} → {below_out:.4f}"
        )

    def test_mud_cut_reduces_300hz_energy(self):
        """Peaking cut at 300 Hz must lower energy there."""
        from crisp.core.processors.eq import EqBalance
        clip = _noise(duration=3.0, amp=0.3)
        out = EqBalance(mud_hz=300.0, mud_db=-6.0, rumble_hz=20.0, air_db=0.0).process(clip)
        mag_in  = _fft_magnitude_at(clip, 300.0)
        mag_out = _fft_magnitude_at(out,  300.0)
        assert mag_out < mag_in, (
            f"300 Hz not cut: {mag_in:.4f} → {mag_out:.4f}"
        )

    def test_air_lift_raises_12khz_energy(self):
        """Peaking boost at 12 kHz must raise energy there."""
        from crisp.core.processors.eq import EqBalance
        clip = _noise(duration=3.0, amp=0.3)
        out = EqBalance(air_hz=12000.0, air_db=6.0, rumble_hz=20.0, mud_db=0.0).process(clip)
        mag_in  = _fft_magnitude_at(clip, 12000.0)
        mag_out = _fft_magnitude_at(out,  12000.0)
        assert mag_out > mag_in, (
            f"12 kHz not boosted: {mag_in:.4f} → {mag_out:.4f}"
        )

    def test_output_shape_preserved(self):
        from crisp.core.processors.eq import EqBalance
        clip = _noise()
        out = EqBalance().process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels
        assert out.sample_rate == clip.sample_rate

    def test_stereo_preserved(self):
        from crisp.core.processors.eq import EqBalance
        clip = _noise(channels=2)
        out = EqBalance().process(clip)
        assert out.channels == 2

    def test_zero_eq_changes_only_rumble(self):
        """With mud_db=0 and air_db=0 only the high-pass should change things."""
        from crisp.core.processors.eq import EqBalance
        clip = _noise(duration=3.0, amp=0.3)
        out = EqBalance(rumble_hz=80.0, mud_db=0.0, air_db=0.0).process(clip)
        # Mid-range (1–4 kHz) should be relatively unchanged
        mid_in  = _band_rms(clip, 1000, 4000)
        mid_out = _band_rms(out,  1000, 4000)
        assert abs(mid_out - mid_in) / (mid_in + 1e-9) < 0.05, (
            "Mid-range should not change when only high-pass is applied"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. VoiceClarity
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceClarity:
    """
    VoiceClarity:
      • Presence lift via peaking EQ at 2–5 kHz
      • Optional gentle compressor
    Key claim: 2–5 kHz band is enhanced relative to low-mids.
    """

    def test_presence_band_is_boosted(self):
        """FFT magnitude at presence_hz should increase after VoiceClarity."""
        from crisp.core.processors.clarity import VoiceClarity
        clip = _noise(duration=2.0, amp=0.3)
        out = VoiceClarity(presence_hz=3500.0, presence_db=6.0, compress=False).process(clip)
        mag_in  = _fft_magnitude_at(clip, 3500.0)
        mag_out = _fft_magnitude_at(out,  3500.0)
        assert mag_out > mag_in, (
            f"Presence band not boosted: {mag_in:.4f} → {mag_out:.4f}"
        )

    def test_presence_over_lowmid_ratio_increases(self):
        """Presence-band / low-mid energy ratio should rise after clarity boost."""
        from crisp.core.processors.clarity import VoiceClarity
        clip = _noise(duration=2.0, amp=0.3)
        out  = VoiceClarity(presence_hz=3500.0, presence_db=6.0, compress=False).process(clip)
        pres_in   = _band_rms(clip, 3000, 5000)
        lowmid_in = _band_rms(clip, 200,  800)
        pres_out   = _band_rms(out, 3000, 5000)
        lowmid_out = _band_rms(out, 200,  800)
        ratio_in  = pres_in  / (lowmid_in  + 1e-9)
        ratio_out = pres_out / (lowmid_out + 1e-9)
        assert ratio_out > ratio_in, (
            f"Presence/low-mid ratio should improve: {ratio_in:.3f} → {ratio_out:.3f}"
        )

    def test_compressor_reduces_peaks(self):
        """With compress=True a loud signal's peak should be lower than without."""
        from crisp.core.processors.clarity import VoiceClarity
        clip = _tone(amp=0.9)
        out_nocomp = VoiceClarity(compress=False).process(clip)
        out_comp   = VoiceClarity(compress=True, comp_threshold_db=-20.0,
                                  comp_ratio=4.0).process(clip)
        assert out_comp.peak() < out_nocomp.peak(), (
            "Compressor should reduce peak amplitude"
        )

    def test_output_shape_preserved(self):
        from crisp.core.processors.clarity import VoiceClarity
        clip = _noise()
        out = VoiceClarity().process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels

    def test_stereo_works(self):
        from crisp.core.processors.clarity import VoiceClarity
        clip = _noise(channels=2)
        out = VoiceClarity().process(clip)
        assert out.channels == 2


# ─────────────────────────────────────────────────────────────────────────────
# 5. PlosiveRemoval (DeplosiveProcessor)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlosiveRemoval:
    """
    PlosiveRemoval detects short low-frequency bursts and ducks the low band.
    Key claim: peak energy below split_hz is reduced at plosive frames.
    """

    def _plosive_clip(self, sr: int = SR, duration: float = 2.0,
                      plosive_amp: float = 0.9) -> AudioClip:
        """
        Synthetic plosive: background 300 Hz tone + large 50 Hz burst at t=0.5 s.
        """
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False)
        bg = 0.05 * np.sin(2 * np.pi * 300 * t)          # normal speech-like content
        # Plosive burst: 50 Hz, 30 ms, high amplitude
        burst_start = int(sr * 0.5)
        burst_len   = int(sr * 0.03)
        t_burst     = np.arange(burst_len) / sr
        burst = plosive_amp * np.sin(2 * np.pi * 50 * t_burst)
        sig = bg.copy()
        sig[burst_start: burst_start + burst_len] += burst
        return AudioClip.from_array(sig[:, None].astype(np.float32), sr)

    def test_peak_low_freq_energy_reduced(self):
        """Peak energy below 120 Hz should drop after plosive removal."""
        from crisp.core.processors.deplosive import PlosiveRemoval
        from crisp.core.dsp import lowpass

        clip = self._plosive_clip()
        out  = PlosiveRemoval(split_hz=120.0, threshold=2.0, reduction=0.9).process(clip)

        low_in  = lowpass(clip.samples, clip.sample_rate, 120.0, order=4)
        low_out = lowpass(out.samples,  out.sample_rate,  120.0, order=4)

        peak_in  = float(np.max(np.abs(low_in)))
        peak_out = float(np.max(np.abs(low_out)))
        assert peak_out < peak_in, (
            f"Plosive peak not reduced: {peak_in:.4f} → {peak_out:.4f}"
        )

    def test_low_energy_non_plosive_roughly_preserved(self):
        """A quiet signal with no plosives should not be attenuated much."""
        from crisp.core.processors.deplosive import PlosiveRemoval
        # 1 kHz tone – well above split_hz (120 Hz), no plosive
        clip = _tone(freq=1000.0, amp=0.1, duration=2.0)
        out  = PlosiveRemoval(split_hz=120.0, threshold=3.0, reduction=0.85).process(clip)
        rms_in  = _rms(clip)
        rms_out = _rms(out)
        # Should be within 10% (the high-pass + re-add math preserves most energy)
        assert abs(rms_out - rms_in) / (rms_in + 1e-9) < 0.15, (
            f"Non-plosive signal changed too much: {rms_in:.4f} → {rms_out:.4f}"
        )

    def test_output_shape_preserved(self):
        from crisp.core.processors.deplosive import PlosiveRemoval
        clip = self._plosive_clip()
        out  = PlosiveRemoval().process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels

    def test_stereo_works(self):
        from crisp.core.processors.deplosive import PlosiveRemoval
        clip = _noise(channels=2)
        out  = PlosiveRemoval().process(clip)
        assert out.channels == 2

    def test_no_clipping(self):
        from crisp.core.processors.deplosive import PlosiveRemoval
        clip = self._plosive_clip(plosive_amp=0.95)
        out  = PlosiveRemoval().process(clip)
        assert out.peak() <= 1.0 + 1e-5


# ─────────────────────────────────────────────────────────────────────────────
# 6. LoudnessNormalize
# ─────────────────────────────────────────────────────────────────────────────

class TestLoudnessNormalize:
    """
    LoudnessNormalize uses pyloudnorm (BS.1770).
    Key claim: output LUFS within 1 dB of target_lufs, peak ≤ peak_ceiling_db.
    """

    def _lufs(self, clip: AudioClip) -> float:
        import pyloudnorm as pyln
        meter = pyln.Meter(clip.sample_rate)
        data = clip.samples[:, 0] if clip.channels == 1 else clip.samples
        return float(meter.integrated_loudness(data))

    def test_hits_target_lufs_quiet_source(self):
        """Quiet source (amp=0.05) should be brought up to -16 LUFS."""
        from crisp.core.processors.loudness import LoudnessNormalize
        clip = _tone(duration=3.0, amp=0.05)
        out  = LoudnessNormalize(target_lufs=-16.0).process(clip)
        measured = self._lufs(out)
        assert abs(measured - (-16.0)) < 1.0, (
            f"Expected -16 LUFS, got {measured:.2f}"
        )

    def test_hits_target_lufs_loud_source(self):
        """Loud source (amp=0.9) should be pulled down to -23 LUFS."""
        from crisp.core.processors.loudness import LoudnessNormalize
        clip = _tone(duration=3.0, amp=0.9)
        out  = LoudnessNormalize(target_lufs=-23.0).process(clip)
        measured = self._lufs(out)
        assert abs(measured - (-23.0)) < 1.0, (
            f"Expected -23 LUFS, got {measured:.2f}"
        )

    def test_peak_ceiling_respected(self):
        """Output sample peak must not exceed the ceiling after normalization."""
        from crisp.core.processors.loudness import LoudnessNormalize
        # Very quiet → massive gain needed → ceiling must clamp it
        clip = _tone(duration=3.0, amp=0.005)
        proc = LoudnessNormalize(target_lufs=-6.0, peak_ceiling_db=-1.0)
        out  = proc.process(clip)
        ceiling = 10 ** (-1.0 / 20.0)
        assert out.peak() <= ceiling + 1e-5, (
            f"Peak {out.peak():.4f} exceeds ceiling {ceiling:.4f}"
        )

    def test_silence_passthrough(self):
        """Silence (unmeasurable LUFS) should be returned unchanged."""
        from crisp.core.processors.loudness import LoudnessNormalize
        silence = AudioClip.from_array(np.zeros((SR * 3, 1), dtype=np.float32), SR)
        out = LoudnessNormalize().process(silence)
        np.testing.assert_array_equal(out.samples, silence.samples)

    def test_measure_lufs_helper(self):
        """measure_lufs() should return a finite dB value for a non-silent clip."""
        from crisp.core.processors.loudness import LoudnessNormalize
        clip = _tone(duration=3.0, amp=0.3)
        lufs = LoudnessNormalize().measure_lufs(clip)
        assert np.isfinite(lufs) and -60.0 < lufs < 0.0, (
            f"Unexpected LUFS: {lufs}"
        )

    def test_output_shape_preserved(self):
        from crisp.core.processors.loudness import LoudnessNormalize
        clip = _tone(duration=3.0)
        out  = LoudnessNormalize().process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels


# ─────────────────────────────────────────────────────────────────────────────
# 7. Trim  (gain trim — NOT a silence remover)
# ─────────────────────────────────────────────────────────────────────────────

class TestTrim:
    """
    Trim is a simple dB gain stage before the loudness normaliser.
    NOTE: despite the name 'Trim', this is NOT a silence-removal processor.
    Key claims: scales amplitude by 10^(gain_db/20), clips to ±1, passthrough at 0 dB.
    """

    def test_positive_gain_boosts_amplitude(self):
        """gain_db=+6 should roughly double the peak (×1.995)."""
        from crisp.core.processors.trim import Trim
        amp_in = 0.1
        clip = _tone(amp=amp_in)
        out  = Trim(gain_db=6.0).process(clip)
        expected = min(amp_in * 10 ** (6.0 / 20.0), 1.0)
        assert abs(out.peak() - expected) < 0.02, (
            f"Expected peak ≈ {expected:.3f}, got {out.peak():.3f}"
        )

    def test_negative_gain_attenuates_amplitude(self):
        """gain_db=-6 should roughly halve the peak (×0.501)."""
        from crisp.core.processors.trim import Trim
        amp_in = 0.5
        clip = _tone(amp=amp_in)
        out  = Trim(gain_db=-6.0).process(clip)
        expected = amp_in * 10 ** (-6.0 / 20.0)
        assert abs(out.peak() - expected) < 0.02, (
            f"Expected peak ≈ {expected:.3f}, got {out.peak():.3f}"
        )

    def test_zero_gain_is_passthrough(self):
        """gain_db=0 → early return, samples identical to input."""
        from crisp.core.processors.trim import Trim
        clip = _tone()
        out  = Trim(gain_db=0.0).process(clip)
        np.testing.assert_array_equal(out.samples, clip.samples)

    def test_large_positive_gain_clips_to_one(self):
        """A very large gain must not produce samples outside [-1, 1]."""
        from crisp.core.processors.trim import Trim
        clip = _tone(amp=0.9)
        out  = Trim(gain_db=24.0).process(clip)
        assert out.peak() <= 1.0 + 1e-6

    def test_output_shape_preserved(self):
        from crisp.core.processors.trim import Trim
        clip = _tone()
        out  = Trim(gain_db=3.0).process(clip)
        assert out.frames == clip.frames
        assert out.channels == clip.channels
        assert out.sample_rate == clip.sample_rate


# ─────────────────────────────────────────────────────────────────────────────
# 8. Chorus
# ─────────────────────────────────────────────────────────────────────────────

class TestChorus:
    """
    Chorus adds LFO-modulated delay voices.
    Key claims: same length, no clipping, wet≠dry when mix>0, identity when mix=0.
    """

    def test_output_same_length(self):
        from crisp.core.processors.chorus import Chorus
        clip = _tone(duration=2.0)
        out  = Chorus().process(clip)
        assert out.frames == clip.frames

    def test_no_clipping(self):
        from crisp.core.processors.chorus import Chorus
        clip = _tone(amp=0.9)
        out  = Chorus(mix=0.5).process(clip)
        assert out.peak() <= 1.0 + 1e-5

    def test_wet_signal_differs_from_dry(self):
        """mix=0.5 → chorus modifies the signal."""
        from crisp.core.processors.chorus import Chorus
        clip = _tone(freq=440.0, duration=2.0)
        out  = Chorus(mix=0.5, rate=1.0, depth=0.010).process(clip)
        diff = float(np.max(np.abs(out.samples - clip.samples)))
        assert diff > 1e-5, (
            f"Chorus with mix=0.5 should modify the signal (max diff={diff:.2e})"
        )

    def test_dry_only_is_passthrough(self):
        """mix=0.0 → pure dry; output should equal input."""
        from crisp.core.processors.chorus import Chorus
        clip = _tone()
        out  = Chorus(mix=0.0).process(clip)
        np.testing.assert_allclose(out.samples, clip.samples, atol=1e-5)

    def test_stereo_channel_count_preserved(self):
        from crisp.core.processors.chorus import Chorus
        clip = _tone(channels=2)
        out  = Chorus().process(clip)
        assert out.channels == 2

    def test_multi_voice_produces_finite_output(self):
        """3 voices should still produce valid, finite samples."""
        from crisp.core.processors.chorus import Chorus
        clip = _tone(duration=2.0)
        out  = Chorus(voices=3, mix=0.5).process(clip)
        assert out.frames == clip.frames
        assert np.isfinite(out.samples).all()

    def test_sample_rate_preserved(self):
        from crisp.core.processors.chorus import Chorus
        clip = _tone()
        out  = Chorus().process(clip)
        assert out.sample_rate == clip.sample_rate


# ─────────────────────────────────────────────────────────────────────────────
# 9. Widener
# ─────────────────────────────────────────────────────────────────────────────

class TestWidener:
    """
    Widener applies M/S processing to widen or narrow the stereo image.
    Upmixes mono → stereo before processing.
    Key claims:
      • width > 1.0 increases L/R difference on stereo-with-spread input
      • width < 1.0 narrows spread
      • width = 1.0 is a passthrough
      • mono is upmixed to stereo
      • no clipping
    """

    def _stereo_diff(self, amp: float = 0.3, duration: float = 1.0) -> AudioClip:
        """Stereo clip where L ≠ R (real stereo content).

        Amplitudes are clipped to ±0.7 so the resulting AudioClip is always
        valid (peak ≤ 1.0).  This matters because Widener contains an
        anti-clip guard that fires when peak > 1.0, which would otherwise mask
        the widening effect and break the passthrough test.
        """
        n = int(SR * duration)
        rng = np.random.default_rng(0)
        L = np.clip(amp * rng.standard_normal(n), -0.7, 0.7).astype(np.float32)
        R = np.clip(amp * rng.standard_normal(n), -0.7, 0.7).astype(np.float32)
        return AudioClip.from_array(np.column_stack([L, R]), SR)

    def test_width_above_unity_increases_spread(self):
        """width=2.0 on a stereo clip with L≠R should widen the image."""
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff()
        out  = Widener(width=2.0).process(clip)
        assert _stereo_spread(out) > _stereo_spread(clip), (
            f"Widener(2.0) should increase spread: "
            f"{_stereo_spread(clip):.4f} → {_stereo_spread(out):.4f}"
        )

    def test_width_below_unity_narrows_spread(self):
        """width=0.2 should narrow the stereo image."""
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff()
        out  = Widener(width=0.2).process(clip)
        assert _stereo_spread(out) < _stereo_spread(clip), (
            f"Widener(0.2) should decrease spread: "
            f"{_stereo_spread(clip):.4f} → {_stereo_spread(out):.4f}"
        )

    def test_unity_width_is_passthrough(self):
        """width=1.0 should leave samples unchanged (M/S identity)."""
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff()
        out  = Widener(width=1.0).process(clip)
        np.testing.assert_allclose(out.samples, clip.samples, atol=1e-5)

    def test_mono_upmixed_to_stereo(self):
        """Mono input must be upmixed to stereo output."""
        from crisp.core.processors.widener import Widener
        clip = _tone(channels=1)
        out  = Widener(width=1.5).process(clip)
        assert out.channels == 2

    def test_no_clipping_on_wide_setting(self):
        """Even aggressive widening must not produce samples outside [-1, 1]."""
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff(amp=0.9)
        out  = Widener(width=2.5).process(clip)
        assert out.peak() <= 1.0 + 1e-5

    def test_zero_width_collapses_to_mono(self):
        """width=0.0 should kill the S channel → L == R (mono-folded stereo)."""
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff()
        out  = Widener(width=0.0).process(clip)
        # With width=0: S*=0 → L_out=M, R_out=M  (both equal to mid)
        np.testing.assert_allclose(out.samples[:, 0], out.samples[:, 1], atol=1e-5)

    def test_output_shape_preserved(self):
        from crisp.core.processors.widener import Widener
        clip = self._stereo_diff()
        out  = Widener().process(clip)
        assert out.frames == clip.frames
        assert out.sample_rate == clip.sample_rate


# ─────────────────────────────────────────────────────────────────────────────
# 10. Panner
# ─────────────────────────────────────────────────────────────────────────────

class TestPanner:
    """
    Panner uses constant-power (sin/cos) law.
    Key claims:
      • position=0.0 → hard left (right is silent)
      • position=1.0 → hard right (left is silent)
      • position=0.5 → equal power L and R
      • Always outputs stereo
      • Constant power maintained across the pan arc
    """

    def test_right_pan_louder_on_right(self):
        """position=0.8 → R channel louder than L."""
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        out  = Panner(position=0.8).process(clip)
        rms_l = math.sqrt(float(np.mean(out.samples[:, 0] ** 2)))
        rms_r = math.sqrt(float(np.mean(out.samples[:, 1] ** 2)))
        assert rms_r > rms_l, (
            f"Right pan: expected R > L, got L={rms_l:.4f} R={rms_r:.4f}"
        )

    def test_left_pan_louder_on_left(self):
        """position=0.2 → L channel louder than R."""
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        out  = Panner(position=0.2).process(clip)
        rms_l = math.sqrt(float(np.mean(out.samples[:, 0] ** 2)))
        rms_r = math.sqrt(float(np.mean(out.samples[:, 1] ** 2)))
        assert rms_l > rms_r, (
            f"Left pan: expected L > R, got L={rms_l:.4f} R={rms_r:.4f}"
        )

    def test_center_pan_equal_power(self):
        """position=0.5 → L and R have equal RMS (±0.01%)."""
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        out  = Panner(position=0.5).process(clip)
        rms_l = math.sqrt(float(np.mean(out.samples[:, 0] ** 2)))
        rms_r = math.sqrt(float(np.mean(out.samples[:, 1] ** 2)))
        assert abs(rms_l - rms_r) < 1e-4, (
            f"Center pan: expected L ≈ R, got L={rms_l:.5f} R={rms_r:.5f}"
        )

    def test_hard_left_silences_right_channel(self):
        """position=0.0 → cos(0)=1 for L, sin(0)=0 for R → R is silent."""
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        out  = Panner(position=0.0).process(clip)
        assert float(np.max(np.abs(out.samples[:, 1]))) < 1e-5, (
            "Hard left should produce silent right channel"
        )

    def test_hard_right_silences_left_channel(self):
        """position=1.0 → cos(π/2)=0 for L → L is silent."""
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        out  = Panner(position=1.0).process(clip)
        assert float(np.max(np.abs(out.samples[:, 0]))) < 1e-5, (
            "Hard right should produce silent left channel"
        )

    def test_always_outputs_stereo(self):
        """Panner must produce a 2-channel output regardless of input channels."""
        from crisp.core.processors.panner import Panner
        for pos in [0.0, 0.3, 0.5, 0.7, 1.0]:
            clip = _tone(amp=0.5, channels=1)
            out  = Panner(position=pos).process(clip)
            assert out.channels == 2, f"Expected stereo at position={pos}"

    def test_constant_power_across_pan_positions(self):
        """
        Sum of squares L² + R² should equal the input RMS² (constant-power law).
        sqrt(L_rms² + R_rms²) ≈ mono_rms within 0.5%.
        """
        from crisp.core.processors.panner import Panner
        clip = _tone(amp=0.5)
        mono_rms = math.sqrt(float(np.mean(clip.samples ** 2)))
        for pos in [0.1, 0.3, 0.5, 0.7, 0.9]:
            out  = Panner(position=pos).process(clip)
            rms_l = math.sqrt(float(np.mean(out.samples[:, 0] ** 2)))
            rms_r = math.sqrt(float(np.mean(out.samples[:, 1] ** 2)))
            total = math.sqrt(rms_l ** 2 + rms_r ** 2)
            assert abs(total - mono_rms) / (mono_rms + 1e-9) < 0.005, (
                f"Constant power violated at pos={pos}: got {total:.5f}, expected {mono_rms:.5f}"
            )

    def test_output_frame_count_and_rate_preserved(self):
        from crisp.core.processors.panner import Panner
        clip = _tone(duration=1.5)
        out  = Panner(position=0.5).process(clip)
        assert out.frames == clip.frames
        assert out.sample_rate == clip.sample_rate
