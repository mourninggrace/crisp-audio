# Crisp — Audio Cleanup Tool

Record, clean, A/B-compare, and export voice audio from a single self-contained
desktop app. Built with Python + PySide6, shipped as one executable via
PyInstaller.

> Working title — rebrand freely before the Gumroad release.

## Features

- **Record** from any input device, with a live level meter.
- **Cleanup engine** — toggle each stage independently:
  - Remove background noise (spectral gating)
  - Reduce reverb / room sound
  - Remove plosives (breath pops)
  - Balance EQ (corrective voice curve)
  - Enhance voice clarity (presence lift + gentle leveling)
  - Normalize loudness to a target LUFS
- **A/B toggle** to compare original vs cleaned instantly.
- **Waveform display**, before and after, x-linked.
- **Batch processing** of a whole folder.
- **Export** to WAV (16/24-bit, 32-bit float), FLAC, MP3, AAC, OGG.
- **Presets**: YouTube (−14 LUFS), Podcast (−16 LUFS), Broadcast (−23 LUFS),
  Archival (lossless, no loudness change).

## Project layout

```
src/crisp/
  core/                 # no-GUI audio engine (unit-testable)
    audio.py            # AudioClip value object (float32, frames×channels)
    audio_io.py         # load/save via soundfile + pydub
    recorder.py         # sounddevice input + device enumeration
    dsp.py              # shared biquad filters / dynamics
    engine.py           # CleanupSettings + pipeline runner
    presets.py          # formats + delivery presets
    exporter.py         # format/bit-depth/bitrate encoding
    batch.py            # folder processing
    ffmpeg.py           # locates the bundled ffmpeg
    processors/         # one module per cleanup stage (one checkbox each)
  gui/                  # PySide6 UI (main_window, waveform, player, workers)
tests/                  # headless engine tests
crisp.spec              # PyInstaller single-file build
```

The `core` package never imports Qt, so the whole engine is testable and
scriptable without a display.

## Develop

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m crisp            # launch the GUI
pytest                     # run the headless engine tests
```

ffmpeg ships with the `imageio-ffmpeg` dependency — no system install needed.

## Build the executable

```powershell
pip install -r requirements.txt
pyinstaller crisp.spec
# -> dist/Crisp.exe
```

## License note

Built on **PySide6 (LGPL)** so the app can ship as a closed-source paid product.
Avoid swapping in PyQt5 unless you hold a PyQt commercial license.
