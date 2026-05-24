"""Processor interface shared by every cleanup stage."""
from __future__ import annotations

from dataclasses import dataclass

from crisp.core.audio import AudioClip


@dataclass(frozen=True)
class ParamSpec:
    """Describes one user-tunable parameter so the UI can build a control.

    ``kind`` is ``"float"`` (slider) or ``"bool"`` (checkbox). Float params map
    onto an integer slider internally using ``step``.
    """

    key: str
    label: str
    kind: str = "float"
    minimum: float = 0.0
    maximum: float = 1.0
    step: float = 0.01
    unit: str = ""


class Processor:
    """Base class for a single cleanup stage.

    Subclasses set :attr:`key`, :attr:`label`, :attr:`description` and implement
    :meth:`process`. ``params`` is a free-form dict of tunables; sensible
    defaults live in :attr:`default_params`, and :attr:`param_specs` declares
    which of them the UI should expose as sliders/toggles.
    """

    key: str = ""
    label: str = ""
    description: str = ""
    default_params: dict = {}
    param_specs: list[ParamSpec] = []

    def __init__(self, **params) -> None:
        self.params = {**self.default_params, **params}

    def process(self, clip: AudioClip) -> AudioClip:  # pragma: no cover - abstract
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} {self.params}>"
