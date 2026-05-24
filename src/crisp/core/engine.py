"""The cleanup engine: runs the enabled processors in pipeline order."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from crisp import __version__
from crisp.core.audio import AudioClip
from crisp.core.processors import ALL_PROCESSORS, Processor

# Bumped if the on-disk settings schema ever changes incompatibly.
SETTINGS_SCHEMA = 1

# A progress callback receives (stage_label, fraction_complete 0..1).
ProgressCB = Callable[[str, float], None]


@dataclass
class CleanupSettings:
    """Which stages are enabled and their per-stage param overrides.

    ``enabled`` maps a processor ``key`` -> bool. ``params`` maps a processor
    ``key`` -> dict of overrides merged onto that processor's defaults.
    """

    enabled: dict[str, bool] = field(default_factory=dict)
    params: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "CleanupSettings":
        # Sensible "first run" defaults: everything except dereverb on, since
        # dereverb is the most colouring stage.
        enabled = {p.key: True for p in ALL_PROCESSORS}
        enabled["dereverb"] = False
        return cls(enabled=enabled)

    def is_enabled(self, key: str) -> bool:
        return self.enabled.get(key, False)

    def build_chain(self) -> list[Processor]:
        chain: list[Processor] = []
        for cls in ALL_PROCESSORS:
            if self.is_enabled(cls.key):
                chain.append(cls(**self.params.get(cls.key, {})))
        return chain

    # ----- Persistence -----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "schema": SETTINGS_SCHEMA,
            "app_version": __version__,
            "enabled": dict(self.enabled),
            "params": {k: dict(v) for k, v in self.params.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CleanupSettings":
        # Only accept keys that map to real processors, so a hand-edited or
        # older file can't inject junk into the pipeline.
        valid = {p.key for p in ALL_PROCESSORS}
        enabled = {k: bool(v) for k, v in data.get("enabled", {}).items() if k in valid}
        params = {k: dict(v) for k, v in data.get("params", {}).items() if k in valid}
        return cls(enabled=enabled, params=params)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CleanupSettings":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


class CleanupEngine:
    """Stateless-ish runner that applies a :class:`CleanupSettings` to a clip."""

    def run(
        self,
        clip: AudioClip,
        settings: CleanupSettings,
        progress: ProgressCB | None = None,
    ) -> AudioClip:
        chain = settings.build_chain()
        if not chain:
            if progress:
                progress("No cleanup selected", 1.0)
            return clip

        result = clip
        total = len(chain)
        for i, proc in enumerate(chain):
            if progress:
                progress(proc.label, i / total)
            result = proc.process(result)
        if progress:
            progress("Done", 1.0)
        return result
