"""Export presets and supported output formats.

A preset bundles an output format, encoding quality, and a loudness target so
the user can pick "YouTube" and get a correctly-loudness-targeted file.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Format(str, Enum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"
    AAC = "aac"      # .m4a container
    OGG = "ogg"


# libsndfile subtypes for the bit-depth selector (WAV/FLAC).
WAV_SUBTYPES = {
    "16-bit PCM": "PCM_16",
    "24-bit PCM": "PCM_24",
    "32-bit float": "FLOAT",
}


@dataclass(frozen=True)
class ExportSettings:
    """Everything the exporter needs to write one file."""

    fmt: Format = Format.WAV
    wav_subtype: str = "PCM_16"   # used for WAV/FLAC
    mp3_bitrate: str = "192k"     # used for MP3/AAC/OGG
    target_lufs: float | None = None  # if set, normalise before encoding


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    export: ExportSettings


# The four delivery presets from the spec, with appropriate loudness targets.
PRESETS: dict[str, Preset] = {
    "youtube": Preset(
        "YouTube",
        "Streaming target, −14 LUFS, 192 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="192k", target_lufs=-14.0),
    ),
    "podcast": Preset(
        "Podcast",
        "Spoken-word target, −16 LUFS, 128 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="128k", target_lufs=-16.0),
    ),
    "broadcast": Preset(
        "Broadcast",
        "EBU R128, −23 LUFS, 24-bit WAV.",
        ExportSettings(Format.WAV, wav_subtype="PCM_24", target_lufs=-23.0),
    ),
    "archival": Preset(
        "Archival",
        "Lossless master, no loudness change, 24-bit FLAC.",
        ExportSettings(Format.FLAC, wav_subtype="PCM_24", target_lufs=None),
    ),
}
