# AudioCleanUpTool (Crisp)

> **Free and open source.** Use it, modify it, share it — no restrictions. MIT licensed.

A self-contained desktop audio cleanup tool for voice recordings, podcasts, livestreams, and anything that needs to sound better. Built with Python + PySide6, ships as a single `.exe` — no Python installation required.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Download

Grab the latest installer from [**Releases**](https://github.com/mourninggrace/crisp-audio/releases) → `AudioCleanUpTool-x.x.x-Setup.exe`. Run it, done.

---

## Features

- **Auto Clean** — one button. Analyses your audio and applies the right settings automatically.
- **10 audio processors**, each independently toggleable:
  - Noise Reduction (hum, hiss, fans, AC)
  - Dereverb (room tail / reverb reduction)
  - Plosive Removal (breath pops / p-pops)
  - EQ Balance (rumble cut, de-box, air lift)
  - Voice Clarity (presence lift + gentle leveling)
  - Loudness Normalise (ITU-R BS.1770 / LUFS)
  - Trim (manual gain)
  - Chorus (LFO-modulated depth effect)
  - Widener (M/S stereo widening)
  - Panner (constant-power stereo positioning)
- **A/B comparison** — toggle between original and cleaned in real time
- **Live waveform display** — before and after, x-linked
- **Recording** from any input device with a live level meter
- **Batch processing** of entire folders
- **Export formats:** WAV (16/24-bit, 32-bit float), FLAC, MP3, AAC, OGG, OPUS, AIFF
- **Export presets:** YouTube, Spotify, Podcast, Apple Podcasts, Broadcast (EBU R128), Broadcast TV (ATSC A/85), Church/Livestream, Voice-Over/ACX, Archival
- **7 themes:** Dark Default, Midnight Blue, Charcoal Orange, Deep Purple, Hacker Green, Light Clean, Warm Cream
- **Save/load cleanup settings** as `.crisp.json` files
- **Settings dialog** (`Ctrl+,`) for playback volume and theme preferences

---

## User Guide

See [`docs/AudioCleanUpTool_User_Guide.pdf`](docs/AudioCleanUpTool_User_Guide.pdf) for full documentation.

---

## Project layout

```
src/crisp/
  core/                 # no-GUI audio engine (unit-testable, scriptable)
    audio.py            # AudioClip value object (float32, frames×channels)
    audio_io.py         # load/save via soundfile + pydub
    recorder.py         # sounddevice input + device enumeration
    dsp.py              # shared biquad filters / dynamics
    engine.py           # CleanupSettings + pipeline runner
    analyser.py         # AutoAnalyser + AnalysisReport
    presets.py          # formats + delivery presets
    exporter.py         # format/bit-depth/bitrate encoding
    batch.py            # folder processing
    ffmpeg.py           # locates the bundled ffmpeg
    processors/         # one module per cleanup stage
  gui/                  # PySide6 UI (main_window, waveform, player, workers)
installer/              # Inno Setup build script
tests/                  # 173 tests, all passing
```

The `core` package never imports Qt — fully testable and scriptable headlessly.

---

## Develop

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m crisp          # launch the GUI
pytest                   # run the test suite
```

ffmpeg ships with `imageio-ffmpeg` — no system install needed.

## Build the executable

```powershell
pip install -e ".[dev]"
pyinstaller crisp.spec
# -> dist/Crisp.exe

# Then package as installer:
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\crisp.iss
# -> dist/AudioCleanUpTool-x.x.x-Setup.exe
```

---

## Licence

[MIT](LICENSE) — free for personal and commercial use, modification, and redistribution.
