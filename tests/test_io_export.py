"""Comprehensive tests for audio I/O, export formats, batch processing, and
the exporter in the AudioCleanUpTool (crisp) package.

Run with:
    cd C:\\AudioCleanUpTool
    .venv\\Scripts\\python.exe -m pytest tests/test_io_export.py -v --tb=short
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

import numpy as np
import pytest

# Ensure src/ is on sys.path (mirrors the project convention).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crisp.core.audio import AudioClip
from crisp.core import audio_io
from crisp.core.exporter import export, EXTENSIONS
from crisp.core.presets import ExportSettings, Format, PRESETS
from crisp.core.ffmpeg import ffmpeg_path
from crisp.core.engine import CleanupEngine, CleanupSettings
from crisp.core import batch as batch_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FFMPEG_AVAILABLE = ffmpeg_path() is not None

skip_no_ffmpeg = pytest.mark.skipif(
    not FFMPEG_AVAILABLE,
    reason="ffmpeg not found — skipping lossy-format test",
)


def _make_clip(
    duration: float = 0.5,
    sr: int = 44100,
    channels: int = 1,
    freq: float = 440.0,
    amp: float = 0.5,
) -> AudioClip:
    """Generate a sine-wave AudioClip (mono or stereo)."""
    frames = int(sr * duration)
    t = np.linspace(0, duration, frames, endpoint=False)
    sig = amp * np.sin(2 * np.pi * freq * t).astype(np.float32)
    if channels == 1:
        return AudioClip.from_array(sig, sr)
    # stereo: left = 440 Hz, right = 880 Hz
    t2 = amp * np.sin(2 * np.pi * 880.0 * t).astype(np.float32)
    stereo = np.stack([sig, t2], axis=1)
    return AudioClip.from_array(stereo, sr)


def _empty_cleanup() -> CleanupSettings:
    """CleanupSettings with every processor disabled (fastest for tests)."""
    return CleanupSettings(enabled={}, params={})


# ===========================================================================
# 1. AudioClip construction & properties
# ===========================================================================

class TestAudioClip:
    def test_from_array_mono_shape(self):
        clip = _make_clip(channels=1)
        assert clip.samples.ndim == 2
        assert clip.channels == 1

    def test_from_array_stereo_shape(self):
        clip = _make_clip(channels=2)
        assert clip.samples.ndim == 2
        assert clip.channels == 2

    def test_dtype_is_float32(self):
        clip = _make_clip()
        assert clip.samples.dtype == np.float32

    def test_int16_input_normalised(self):
        pcm = np.array([0, 32767, -32768], dtype=np.int16)
        clip = AudioClip.from_array(pcm, 48000)
        assert clip.peak() <= 1.0 + 1e-6

    def test_frames_and_duration(self):
        sr = 22050
        clip = _make_clip(duration=1.0, sr=sr)
        assert clip.frames == sr
        assert abs(clip.duration - 1.0) < 1e-3

    def test_to_mono_from_stereo(self):
        clip = _make_clip(channels=2)
        mono = clip.to_mono()
        assert mono.channels == 1
        assert mono.frames == clip.frames

    def test_to_mono_idempotent(self):
        clip = _make_clip(channels=1)
        assert clip.to_mono() is clip  # same object

    def test_with_samples(self):
        clip = _make_clip()
        new_data = np.zeros((100, 1), dtype=np.float32)
        new_clip = clip.with_samples(new_data)
        assert new_clip.frames == 100
        assert new_clip.sample_rate == clip.sample_rate

    def test_invalid_1d_raw_samples_raises(self):
        """Constructing with a 1-D array directly (not via from_array) must raise."""
        with pytest.raises(ValueError):
            AudioClip(np.zeros(100, dtype=np.float32), 44100)

    def test_peak(self):
        clip = _make_clip(amp=0.5)
        assert 0.4 < clip.peak() <= 0.5 + 1e-6


# ===========================================================================
# 2. Load from disk
# ===========================================================================

class TestLoad:
    def test_load_wav(self, tmp_path):
        """Write a WAV with scipy, then load it via audio_io.load()."""
        wav_path = tmp_path / "test.wav"
        clip = _make_clip(duration=0.2, sr=44100, channels=1)
        audio_io.save_wav(clip, wav_path)

        loaded = audio_io.load(wav_path)
        assert loaded.sample_rate == 44100
        assert loaded.channels == 1
        assert loaded.frames > 0
        assert loaded.samples.dtype == np.float32
        assert loaded.samples.ndim == 2

    def test_load_stereo_wav(self, tmp_path):
        wav_path = tmp_path / "stereo.wav"
        clip = _make_clip(duration=0.2, sr=48000, channels=2)
        audio_io.save_wav(clip, wav_path)

        loaded = audio_io.load(wav_path)
        assert loaded.channels == 2
        assert loaded.sample_rate == 48000

    def test_load_flac(self, tmp_path):
        flac_path = tmp_path / "test.flac"
        clip = _make_clip(duration=0.2, sr=44100, channels=1)
        audio_io.save_flac(clip, flac_path)

        loaded = audio_io.load(flac_path)
        assert loaded.sample_rate == 44100
        assert loaded.channels == 1
        assert loaded.samples.dtype == np.float32

    def test_load_ogg(self, tmp_path):
        ogg_path = tmp_path / "test.ogg"
        clip = _make_clip(duration=0.2, sr=44100, channels=1)
        audio_io.save_ogg(clip, ogg_path)

        loaded = audio_io.load(ogg_path)
        assert loaded.sample_rate == 44100
        assert loaded.channels == 1


# ===========================================================================
# 3. Save round-trip fidelity
# ===========================================================================

class TestSaveRoundTrip:
    def test_wav_roundtrip(self, tmp_path):
        """WAV PCM_16 round-trip should preserve shape and be close in value."""
        original = _make_clip(duration=0.3, sr=44100, channels=1, amp=0.8)
        path = tmp_path / "rt.wav"
        audio_io.save_wav(original, path, subtype="PCM_16")
        reloaded = audio_io.load(path)

        assert reloaded.frames == original.frames
        assert reloaded.channels == original.channels
        assert reloaded.sample_rate == original.sample_rate
        # PCM_16 quantisation: within ~0.1% of full scale.
        np.testing.assert_allclose(
            reloaded.samples, original.samples, atol=1e-3
        )

    def test_wav_float32_roundtrip(self, tmp_path):
        """Float32 WAV should be bit-exact."""
        original = _make_clip(duration=0.2, sr=48000, channels=2)
        path = tmp_path / "rt_f32.wav"
        audio_io.save_wav(original, path, subtype="FLOAT")
        reloaded = audio_io.load(path)

        np.testing.assert_array_equal(reloaded.samples, original.samples)

    def test_flac_roundtrip(self, tmp_path):
        """FLAC PCM_16 should round-trip losslessly at 16-bit precision."""
        original = _make_clip(duration=0.2, sr=44100, channels=1, amp=0.7)
        path = tmp_path / "rt.flac"
        audio_io.save_flac(original, path, subtype="PCM_16")
        reloaded = audio_io.load(path)

        assert reloaded.frames == original.frames
        assert reloaded.sample_rate == original.sample_rate
        np.testing.assert_allclose(
            reloaded.samples, original.samples, atol=1e-3
        )

    def test_aiff_roundtrip(self, tmp_path):
        original = _make_clip(duration=0.2, sr=22050, channels=1)
        path = tmp_path / "rt.aiff"
        audio_io.save_aiff(original, path, subtype="PCM_16")
        reloaded = audio_io.load(path)

        assert reloaded.sample_rate == 22050
        assert reloaded.channels == 1
        np.testing.assert_allclose(
            reloaded.samples, original.samples, atol=1e-3
        )

    def test_stereo_wav_roundtrip(self, tmp_path):
        original = _make_clip(duration=0.25, sr=48000, channels=2)
        path = tmp_path / "stereo_rt.wav"
        audio_io.save_wav(original, path)
        reloaded = audio_io.load(path)

        assert reloaded.channels == 2
        np.testing.assert_allclose(
            reloaded.samples, original.samples, atol=1e-3
        )


# ===========================================================================
# 4. Export via exporter.export()
# ===========================================================================

class TestExporter:
    def test_export_wav(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.WAV)
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".wav"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_wav_24bit(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.WAV, wav_subtype="PCM_24")
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".wav"
        assert out.exists()
        # 24-bit files are larger than 16-bit for same content
        assert out.stat().st_size > 0

    def test_export_flac(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.FLAC, wav_subtype="PCM_16")
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".flac"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_flac_24bit(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.FLAC, wav_subtype="PCM_24")
        out = export(clip, tmp_path / "out24", settings)
        assert out.suffix == ".flac"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_ogg(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.OGG)
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".ogg"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_aiff(self, tmp_path):
        clip = _make_clip(duration=0.2, sr=44100)
        settings = ExportSettings(fmt=Format.AIFF)
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".aiff"
        assert out.exists()
        assert out.stat().st_size > 0

    @skip_no_ffmpeg
    def test_export_mp3(self, tmp_path):
        clip = _make_clip(duration=0.5, sr=44100)
        settings = ExportSettings(fmt=Format.MP3, mp3_bitrate="128k")
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".mp3"
        assert out.exists()
        assert out.stat().st_size > 0

    @skip_no_ffmpeg
    def test_export_aac(self, tmp_path):
        clip = _make_clip(duration=0.5, sr=44100)
        settings = ExportSettings(fmt=Format.AAC, mp3_bitrate="128k")
        out = export(clip, tmp_path / "out", settings)
        assert out.suffix == ".m4a"
        assert out.exists()
        assert out.stat().st_size > 0

    @skip_no_ffmpeg
    def test_export_mp3_stereo(self, tmp_path):
        clip = _make_clip(duration=0.5, sr=44100, channels=2)
        settings = ExportSettings(fmt=Format.MP3, mp3_bitrate="192k")
        out = export(clip, tmp_path / "stereo", settings)
        assert out.suffix == ".mp3"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_returns_path_with_correct_suffix(self, tmp_path):
        """export() forces the suffix to match the format regardless of stem."""
        clip = _make_clip(duration=0.1, sr=44100)
        # Pass a path with wrong extension
        settings = ExportSettings(fmt=Format.FLAC)
        out = export(clip, tmp_path / "wrong_ext.wav", settings)
        assert out.suffix == ".flac"

    def test_export_to_existing_directory(self, tmp_path):
        """Exporting to a file inside an existing directory must not raise."""
        sub = tmp_path / "output"
        sub.mkdir()
        clip = _make_clip(duration=0.1, sr=44100)
        out = export(clip, sub / "result", ExportSettings(fmt=Format.WAV))
        assert out.exists()

    def test_export_applies_loudness(self, tmp_path):
        """When target_lufs is set, the exported file must exist (loudness
        normalization is exercised without crashing)."""
        clip = _make_clip(duration=0.5, sr=44100)
        settings = ExportSettings(fmt=Format.WAV, target_lufs=-23.0)
        out = export(clip, tmp_path / "loud", settings)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_extensions_dict_covers_all_formats(self):
        for fmt in Format:
            assert fmt in EXTENSIONS, f"EXTENSIONS missing entry for {fmt}"


# ===========================================================================
# 5. Presets
# ===========================================================================

class TestPresets:
    def test_all_standard_presets_exist(self):
        for key in ("youtube", "spotify", "podcast", "apple_podcasts",
                    "broadcast", "archival"):
            assert key in PRESETS, f"Missing preset: {key}"

    def test_podcast_preset_settings(self):
        p = PRESETS["podcast"]
        assert p.export.fmt == Format.MP3
        assert p.export.mp3_bitrate == "128k"
        assert p.export.target_lufs == -16.0

    def test_youtube_preset_settings(self):
        p = PRESETS["youtube"]
        assert p.export.fmt == Format.MP3
        assert p.export.mp3_bitrate == "192k"
        assert p.export.target_lufs == -14.0

    def test_spotify_preset_settings(self):
        p = PRESETS["spotify"]
        assert p.export.mp3_bitrate == "320k"
        assert p.export.target_lufs == -14.0

    def test_archival_preset_is_flac_no_lufs(self):
        p = PRESETS["archival"]
        assert p.export.fmt == Format.FLAC
        assert p.export.wav_subtype == "PCM_24"
        assert p.export.target_lufs is None

    def test_broadcast_preset(self):
        p = PRESETS["broadcast"]
        assert p.export.fmt == Format.WAV
        assert p.export.wav_subtype == "PCM_24"
        assert p.export.target_lufs == -23.0

    @skip_no_ffmpeg
    def test_export_with_podcast_preset(self, tmp_path):
        """Full round-trip using the podcast preset (requires ffmpeg for MP3)."""
        clip = _make_clip(duration=0.5, sr=44100)
        settings = PRESETS["podcast"].export
        out = export(clip, tmp_path / "pod", settings)
        assert out.suffix == ".mp3"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_with_archival_preset(self, tmp_path):
        """Archival preset uses FLAC — no ffmpeg required."""
        clip = _make_clip(duration=0.3, sr=44100)
        settings = PRESETS["archival"].export
        out = export(clip, tmp_path / "arch", settings)
        assert out.suffix == ".flac"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_with_broadcast_preset(self, tmp_path):
        # pyloudnorm needs > 400 ms of audio to measure integrated loudness;
        # use 0.6 s to stay safely above the block-size floor.
        clip = _make_clip(duration=0.6, sr=48000)
        settings = PRESETS["broadcast"].export
        out = export(clip, tmp_path / "bc", settings)
        assert out.suffix == ".wav"
        assert out.exists()
        reloaded = audio_io.load(out)
        assert reloaded.sample_rate == 48000


# ===========================================================================
# 6. Batch processing
# ===========================================================================

class TestBatch:
    def _write_wav(self, folder: Path, name: str, **kw) -> Path:
        p = folder / name
        clip = _make_clip(**kw)
        audio_io.save_wav(clip, p)
        return p

    def test_find_audio_files_wav(self, tmp_path):
        self._write_wav(tmp_path, "a.wav")
        self._write_wav(tmp_path, "b.wav")
        (tmp_path / "readme.txt").write_text("ignore me")
        found = batch_mod.find_audio_files(tmp_path)
        names = [f.name for f in found]
        assert "a.wav" in names
        assert "b.wav" in names
        assert "readme.txt" not in names

    def test_find_audio_files_empty_folder(self, tmp_path):
        assert batch_mod.find_audio_files(tmp_path) == []

    def test_find_audio_files_sorts(self, tmp_path):
        for name in ("z.wav", "a.wav", "m.wav"):
            self._write_wav(tmp_path, name)
        found = batch_mod.find_audio_files(tmp_path)
        names = [f.name for f in found]
        assert names == sorted(names)

    def test_process_folder_two_clips(self, tmp_path):
        """Batch-process 2 WAV clips → 2 WAV outputs in out_dir."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()

        clip_a = self._write_wav(in_dir, "a.wav", duration=0.2, sr=44100)
        clip_b = self._write_wav(in_dir, "b.wav", duration=0.2, sr=44100)

        cleanup = _empty_cleanup()
        export_settings = ExportSettings(fmt=Format.WAV)
        results = batch_mod.process_folder(
            in_dir, out_dir, cleanup, export_settings
        )

        assert len(results) == 2
        assert all(r.ok for r in results), [r.error for r in results]
        for r in results:
            assert r.output is not None
            assert r.output.exists()
            assert r.output.stat().st_size > 0

    def test_process_folder_explicit_file_list(self, tmp_path):
        """Passing an explicit `files` list overrides folder scanning."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()

        clip_a = self._write_wav(in_dir, "keep.wav", duration=0.2)
        self._write_wav(in_dir, "skip.wav", duration=0.2)

        cleanup = _empty_cleanup()
        results = batch_mod.process_folder(
            in_dir, out_dir, cleanup,
            ExportSettings(fmt=Format.WAV),
            files=[clip_a],
        )
        assert len(results) == 1
        assert results[0].source.name == "keep.wav"

    def test_process_folder_creates_out_dir(self, tmp_path):
        """out_dir must be created automatically if it doesn't exist."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "new" / "deep" / "out"
        in_dir.mkdir()
        self._write_wav(in_dir, "x.wav")

        cleanup = _empty_cleanup()
        batch_mod.process_folder(
            in_dir, out_dir, cleanup, ExportSettings(fmt=Format.WAV)
        )
        assert out_dir.exists()

    def test_process_folder_output_shape(self, tmp_path):
        """Verify that each output clip has the same shape as the source."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()
        sr = 22050
        frames = int(sr * 0.2)

        for name in ("clip1.wav", "clip2.wav"):
            self._write_wav(in_dir, name, duration=0.2, sr=sr)

        cleanup = _empty_cleanup()
        results = batch_mod.process_folder(
            in_dir, out_dir, cleanup, ExportSettings(fmt=Format.WAV)
        )
        assert all(r.ok for r in results)
        for r in results:
            loaded = audio_io.load(r.output)
            assert loaded.frames == frames
            assert loaded.sample_rate == sr

    def test_batch_progress_callback(self, tmp_path):
        """Progress callback is called for every file."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()
        self._write_wav(in_dir, "p1.wav")
        self._write_wav(in_dir, "p2.wav")

        calls: list[tuple] = []

        def cb(path, idx, total, status):
            calls.append((path.name, idx, total, status))

        batch_mod.process_folder(
            in_dir, out_dir, _empty_cleanup(),
            ExportSettings(fmt=Format.WAV),
            progress=cb,
        )
        # 2 files × 2 calls each (processing + done)
        assert len(calls) >= 2
        statuses = [c[3] for c in calls]
        assert "done" in statuses

    def test_batch_bad_file_error_handled(self, tmp_path):
        """A corrupted file in batch returns BatchResult(ok=False) and continues."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()

        # Write a valid clip and an unreadable garbage WAV
        good = self._write_wav(in_dir, "good.wav")
        bad = in_dir / "bad.wav"
        bad.write_bytes(b"NOT A WAV FILE AT ALL")

        cleanup = _empty_cleanup()
        results = batch_mod.process_folder(
            in_dir, out_dir, cleanup,
            ExportSettings(fmt=Format.WAV),
            files=[good, bad],   # control the order
        )
        assert len(results) == 2
        ok_results = [r for r in results if r.ok]
        fail_results = [r for r in results if not r.ok]
        assert len(ok_results) == 1
        assert len(fail_results) == 1
        assert fail_results[0].error is not None

    @skip_no_ffmpeg
    def test_batch_process_to_flac(self, tmp_path):
        """Batch export to FLAC."""
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()
        self._write_wav(in_dir, "a.wav", duration=0.2)
        self._write_wav(in_dir, "b.wav", duration=0.2)

        cleanup = _empty_cleanup()
        results = batch_mod.process_folder(
            in_dir, out_dir, cleanup,
            ExportSettings(fmt=Format.FLAC),
        )
        assert all(r.ok for r in results)
        for r in results:
            assert r.output.suffix == ".flac"
            assert r.output.exists()


# ===========================================================================
# 7. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_mono_clip_exported_to_wav(self, tmp_path):
        """A mono clip must round-trip through WAV without error."""
        mono = _make_clip(channels=1, duration=0.2, sr=44100)
        path = tmp_path / "mono.wav"
        audio_io.save_wav(mono, path)
        loaded = audio_io.load(path)
        assert loaded.channels == 1

    def test_mono_clip_exported_to_flac(self, tmp_path):
        mono = _make_clip(channels=1, duration=0.2, sr=44100)
        path = tmp_path / "mono.flac"
        audio_io.save_flac(mono, path)
        loaded = audio_io.load(path)
        assert loaded.channels == 1
        assert loaded.sample_rate == 44100

    def test_stereo_clip_exported_to_flac(self, tmp_path):
        stereo = _make_clip(channels=2, duration=0.2, sr=44100)
        path = tmp_path / "stereo.flac"
        audio_io.save_flac(stereo, path)
        loaded = audio_io.load(path)
        assert loaded.channels == 2

    def test_export_wav_subtype_pcm24(self, tmp_path):
        """PCM_24 WAV should have a larger file size than PCM_16 for same clip."""
        clip = _make_clip(duration=0.5, sr=44100, channels=1)
        p16 = export(clip, tmp_path / "pcm16", ExportSettings(fmt=Format.WAV, wav_subtype="PCM_16"))
        p24 = export(clip, tmp_path / "pcm24", ExportSettings(fmt=Format.WAV, wav_subtype="PCM_24"))
        assert p24.stat().st_size > p16.stat().st_size

    def test_clip_to_segment_mono(self):
        """clip_to_segment should produce an AudioSegment with channels=1."""
        mono = _make_clip(channels=1, duration=0.1, sr=44100)
        seg = audio_io.clip_to_segment(mono)
        assert seg.channels == 1
        assert seg.frame_rate == 44100

    def test_clip_to_segment_stereo(self):
        stereo = _make_clip(channels=2, duration=0.1, sr=44100)
        seg = audio_io.clip_to_segment(stereo)
        assert seg.channels == 2
        assert seg.frame_rate == 44100

    def test_wav_different_sample_rates(self, tmp_path):
        """WAV I/O must preserve the sample rate."""
        for sr in (8000, 22050, 44100, 48000, 96000):
            clip = _make_clip(duration=0.1, sr=sr)
            path = tmp_path / f"sr_{sr}.wav"
            audio_io.save_wav(clip, path)
            loaded = audio_io.load(path)
            assert loaded.sample_rate == sr, f"Sample rate mismatch for {sr}"

    def test_export_no_loudness_normalisation(self, tmp_path):
        """ExportSettings with target_lufs=None must not apply normalisation."""
        clip = _make_clip(amp=0.3)
        settings = ExportSettings(fmt=Format.WAV, target_lufs=None)
        out = export(clip, tmp_path / "no_norm", settings)
        reloaded = audio_io.load(out)
        # Peak should be close to original (no loudness change)
        assert abs(reloaded.peak() - clip.peak()) < 0.05

    def test_batch_result_dataclass_fields(self, tmp_path):
        """BatchResult must have the expected fields."""
        r = batch_mod.BatchResult(
            source=Path("a.wav"),
            output=Path("out/a.wav"),
            ok=True,
            error=None,
        )
        assert r.ok is True
        assert r.error is None

    def test_export_settings_default_values(self):
        s = ExportSettings()
        assert s.fmt == Format.WAV
        assert s.wav_subtype == "PCM_16"
        assert s.mp3_bitrate == "192k"
        assert s.target_lufs is None
