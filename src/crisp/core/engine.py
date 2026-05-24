"""The cleanup engine: runs the enabled processors in pipeline order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from crisp.core.audio import AudioClip
from crisp.core.processors import ALL_PROCESSORS, Processor

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
