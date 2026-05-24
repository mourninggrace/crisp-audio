"""Reusable UI building blocks: float slider and a per-processor panel."""
from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtWidgets

from crisp.core.processors.base import ParamSpec, Processor


class FloatSlider(QtWidgets.QWidget):
    """A labelled horizontal slider that emits float values.

    QSlider is integer-only, so we map ``[minimum, maximum]`` onto integer
    steps of size ``step`` and convert back and forth.
    """

    valueChanged = QtCore.Signal(float)

    def __init__(self, spec: ParamSpec, value: float, parent=None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._steps = max(1, round((spec.maximum - spec.minimum) / spec.step))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._name = QtWidgets.QLabel(spec.label)
        self._name.setMinimumWidth(96)
        self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._slider.setRange(0, self._steps)
        self._value_label = QtWidgets.QLabel()
        self._value_label.setMinimumWidth(64)
        self._value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        layout.addWidget(self._name)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._value_label)

        self._slider.setValue(self._to_step(value))
        self._update_label(value)
        self._slider.valueChanged.connect(self._on_slider)

    def set_value(self, value: float) -> None:
        """Programmatically move the slider without emitting ``valueChanged``."""
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_step(value))
        self._slider.blockSignals(False)
        self._update_label(value)

    def _to_step(self, value: float) -> int:
        return round((value - self._spec.minimum) / self._spec.step)

    def _to_value(self, step: int) -> float:
        return self._spec.minimum + step * self._spec.step

    def _update_label(self, value: float) -> None:
        text = f"{value:g}"
        if self._spec.unit:
            text += f" {self._spec.unit}"
        self._value_label.setText(text)

    def _on_slider(self, step: int) -> None:
        value = self._to_value(step)
        self._update_label(value)
        self.valueChanged.emit(value)


class ProcessorPanel(QtWidgets.QGroupBox):
    """A checkable group: the title checkbox toggles the stage on/off, and the
    body holds one control per :class:`ParamSpec`.

    ``on_enabled(key, bool)`` fires when toggled; ``on_param(key, param, value)``
    fires when a control changes.
    """

    def __init__(
        self,
        proc_cls: type[Processor],
        enabled: bool,
        params: dict,
        on_enabled: Callable[[str, bool], None],
        on_param: Callable[[str, str, object], None],
        parent=None,
    ) -> None:
        super().__init__(proc_cls.label, parent)
        self._key = proc_cls.key
        self._on_param = on_param
        self.setCheckable(True)
        self.setChecked(enabled)
        self.setToolTip(proc_cls.description)
        self.toggled.connect(lambda on: on_enabled(self._key, on))

        body = QtWidgets.QVBoxLayout(self)
        body.setSpacing(2)

        self._defaults = dict(proc_cls.default_params)
        self._controls: dict[str, QtWidgets.QWidget] = {}
        merged = {**proc_cls.default_params, **params}
        for spec in proc_cls.param_specs:
            value = merged.get(spec.key, 0)
            if spec.kind == "bool":
                cb = QtWidgets.QCheckBox(spec.label)
                cb.setChecked(bool(value))
                cb.toggled.connect(lambda on, s=spec: self._emit(s.key, on))
                body.addWidget(cb)
                self._controls[spec.key] = cb
            else:
                slider = FloatSlider(spec, float(value))
                slider.valueChanged.connect(lambda v, s=spec: self._emit(s.key, v))
                body.addWidget(slider)
                self._controls[spec.key] = slider

    def _emit(self, param_key: str, value: object) -> None:
        self._on_param(self._key, param_key, value)

    def set_state(self, enabled: bool, params: dict) -> None:
        """Refresh the panel from loaded settings without firing callbacks."""
        self.blockSignals(True)
        self.setChecked(enabled)
        self.blockSignals(False)

        merged = {**self._defaults, **params}
        for key, widget in self._controls.items():
            value = merged.get(key)
            if value is None:
                continue
            if isinstance(widget, FloatSlider):
                widget.set_value(float(value))
            else:  # QCheckBox
                widget.blockSignals(True)
                widget.setChecked(bool(value))
                widget.blockSignals(False)
