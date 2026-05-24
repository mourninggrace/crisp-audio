# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Per-stage parameter controls: each cleanup stage is now a collapsible,
  checkable panel with sliders/toggles for its tunables (denoise strength,
  EQ amounts, plosive sensitivity, LUFS target, etc.).
- Waveform playhead: a cursor tracks playback position across both the original
  and cleaned waveforms while audio plays.
- Save/load custom cleanup settings: toggle + slider state persists to a
  `*.crisp.json` file and reloads into the panels. Loading ignores unknown keys
  so older or hand-edited files can't corrupt the pipeline.
- `HISTORY.md`: a narrative history / decision log alongside this changelog.

## [0.1.0] - 2026-05-24

Initial scaffold — a runnable foundation for **Crisp**, the Audio Cleanup Tool.

### Added
- Core audio engine (`crisp.core`, GUI-free and unit-tested):
  - `AudioClip` value object (float32, frames×channels).
  - File load/save via `soundfile` + `pydub`; bundled ffmpeg from
    `imageio-ffmpeg` so the build is self-contained.
  - Recording and input-device enumeration via `sounddevice`.
  - Six cleanup processors, each toggled independently: background-noise
    removal, reverb reduction, plosive removal, EQ balance, voice clarity,
    and LUFS loudness normalization.
  - Pipeline runner (`CleanupEngine` + `CleanupSettings`).
  - Export to WAV (16/24-bit, 32-bit float), FLAC, MP3, AAC, OGG.
  - Delivery presets: YouTube (−14 LUFS), Podcast (−16 LUFS),
    Broadcast (−23 LUFS), Archival (lossless).
  - Batch folder processing.
- PySide6 GUI: device picker, record, cleanup toggles, before/after waveform
  display, A/B playback, export controls, and threaded DSP so the UI stays
  responsive.
- Packaging: `requirements.txt`, `pyproject.toml`, PyInstaller spec
  (`crisp.spec`) for a single-file executable.
- Headless engine tests (`tests/test_pipeline.py`).

[Unreleased]: https://github.com/mourninggrace/crisp-audio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mourninggrace/crisp-audio/releases/tag/v0.1.0
