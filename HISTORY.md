# Project History

A narrative log of how Crisp has evolved and *why* — the reasoning behind
decisions that the code and commit messages alone don't capture. Newest first.
For the concise, release-oriented list of changes, see
[CHANGELOG.md](CHANGELOG.md).

## 2026-05-24 — Project kickoff

Crisp began as the "Audio Cleanup Tool": a self-contained desktop app to
record, clean, A/B-compare, and export voice audio, headed for an eventual
paid release on Gumroad.

### Decisions

- **GUI framework: PySide6, not PyQt5.** PyQt5 was in the original brief, but
  it is GPL or a paid commercial license — shipping a closed-source paid
  product under its GPL terms isn't compliant. PySide6 is the official Qt for
  Python under LGPL, free to ship in a closed-source app, with a near-identical
  API. The PyInstaller spec explicitly excludes PyQt5/PyQt6.

- **Self-contained ffmpeg.** ffmpeg isn't on most users' PATH, but pydub and
  MP3/AAC export need it. We depend on `imageio-ffmpeg`, which ships a static
  binary per platform, and point pydub at it on startup. This keeps the final
  one-file exe truly self-contained.

- **Core/GUI split.** Everything in `crisp.core` is GUI-free and unit-testable;
  Qt lives only in `crisp.gui`. A single canonical audio representation
  (`AudioClip`: float32, frames×channels) flows through every processor, the
  waveform view, and the exporter, so they all share the same assumptions.

- **One processor module per cleanup stage.** Each of the six cleanup stages is
  its own module under `core/processors/`, mapping 1:1 to a UI checkbox. The
  riskier DSP (dereverb, the clarity compressor) is deliberately isolated so a
  better algorithm can drop into one file later without touching the rest.

- **Pragmatic DSP first.** Denoise (noisereduce), EQ/clarity/plosive (scipy
  biquads), and LUFS normalize (pyloudnorm) are solid. Dereverb uses spectral
  over-subtraction and the clarity compressor has no attack/release smoothing —
  good enough for v0.1, flagged for improvement.

### Added shortly after kickoff

- **Per-stage parameter controls.** Each stage declares its tunables via a
  `param_specs` list; the UI builds sliders/toggles generically, so adding a
  knob is a one-line change in the processor with no GUI code.
- **Waveform playhead.** A cursor tracks playback position across both
  waveforms, driven by a timer, auto-clearing when playback ends.
- **Save/load cleanup settings.** Toggle + slider state serializes to a
  `*.crisp.json` file and reloads back into the panels. `from_dict` ignores
  unknown keys so hand-edited or older files can't inject junk into the
  pipeline.

### Process

- Private GitHub repo created at `mourninggrace/crisp-audio`.
- We keep `CHANGELOG.md` (Keep a Changelog format) and this history current,
  committing and pushing after each meaningful change.
