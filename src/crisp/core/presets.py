"""Export presets and supported output formats.

A preset bundles an output format, encoding quality, and a loudness target so
the user can pick "YouTube" and get a correctly-loudness-targeted file.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Format(str, Enum):
    WAV  = "wav"
    FLAC = "flac"
    MP3  = "mp3"
    AAC  = "aac"      # .m4a container
    OGG  = "ogg"
    OPUS = "opus"     # .opus via ffmpeg — excellent quality at low bitrates
    AIFF = "aiff"     # uncompressed, Mac-friendly


# libsndfile subtypes for the bit-depth selector (WAV / FLAC / AIFF).
WAV_SUBTYPES = {
    "16-bit PCM": "PCM_16",
    "24-bit PCM": "PCM_24",
    "32-bit float": "FLOAT",
}


@dataclass(frozen=True)
class ExportSettings:
    """Everything the exporter needs to write one file."""

    fmt: Format = Format.WAV
    wav_subtype: str = "PCM_16"   # used for WAV / FLAC / AIFF
    mp3_bitrate: str = "192k"     # used for MP3 / AAC / OGG / OPUS
    target_lufs: float | None = None  # if set, normalise before encoding


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    export: ExportSettings


PRESETS: dict[str, Preset] = {
    # ---- Streaming / video ------------------------------------------------
    "youtube": Preset(
        "YouTube",
        "Streaming target, −14 LUFS, 192 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="192k", target_lufs=-14.0),
    ),
    "spotify": Preset(
        "Spotify",
        "Music streaming, −14 LUFS, 320 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="320k", target_lufs=-14.0),
    ),
    # ---- Podcasting -------------------------------------------------------
    "podcast": Preset(
        "Podcast (general)",
        "Spoken-word target, −16 LUFS, 128 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="128k", target_lufs=-16.0),
    ),
    "apple_podcasts": Preset(
        "Apple Podcasts",
        "Apple Podcasts spec, −16 LUFS, 128 kbps AAC.",
        ExportSettings(Format.AAC, mp3_bitrate="128k", target_lufs=-16.0),
    ),
    # ---- Broadcast / professional -----------------------------------------
    "broadcast": Preset(
        "Broadcast (EBU R128)",
        "EBU R128, −23 LUFS, 24-bit WAV.",
        ExportSettings(Format.WAV, wav_subtype="PCM_24", target_lufs=-23.0),
    ),
    "broadcast_tv": Preset(
        "Broadcast TV (ATSC A/85)",
        "US broadcast TV, −24 LUFS, 24-bit WAV.",
        ExportSettings(Format.WAV, wav_subtype="PCM_24", target_lufs=-24.0),
    ),
    "church_livestream": Preset(
        "Church / Livestream",
        "Live-service mix, −16 LUFS, 256 kbps AAC.",
        ExportSettings(Format.AAC, mp3_bitrate="256k", target_lufs=-16.0),
    ),
    # ---- Voice-over / audiobook -------------------------------------------
    "voice_over": Preset(
        "Voice-Over / ACX",
        "ACX audiobook spec: −19 to −23 LUFS, set at −20 LUFS, 192 kbps MP3.",
        ExportSettings(Format.MP3, mp3_bitrate="192k", target_lufs=-20.0),
    ),
    # ---- Archival ---------------------------------------------------------
    "archival": Preset(
        "Archival (lossless)",
        "Lossless master, no loudness change, 24-bit FLAC.",
        ExportSettings(Format.FLAC, wav_subtype="PCM_24", target_lufs=None),
    ),
}
