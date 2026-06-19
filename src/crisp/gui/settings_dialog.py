"""Settings dialog — Appearance, Audio, Playback, Processing, Export, About.

The dialog reads from and writes to a simple JSON settings store
(``~/.crisp/settings.json``).  It emits ``settings_changed`` so the main
window can react without polling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6 import QtCore, QtWidgets

from crisp import APP_NAME, __version__
from crisp.gui.themes import THEMES, THEME_KEYS, DEFAULT_THEME, apply_theme

_SETTINGS_PATH = Path.home() / ".crisp" / "settings.json"

# ---------------------------------------------------------------------------
# Persistent settings store
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "theme": DEFAULT_THEME,
    "default_sample_rate": 44100,
    "default_channels": 1,
    "input_device_index": None,
    "output_device_index": None,
    "playback_volume": 1.0,
    "auto_play_after_cleanup": False,
    "default_format": "wav",
    "default_bitrate": "192k",
    "default_wav_subtype": "PCM_24",
    "normalize_on_export": False,
    "default_target_lufs": -16.0,
    "auto_enable_noise": True,
    "auto_enable_loudness": True,
    "confirm_before_batch": True,
    "show_lufs_on_load": True,
}


def load_settings() -> dict:
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def save_settings(data: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(QtWidgets.QDialog):
    """Tabbed settings dialog.  Call ``exec()`` to show modally."""

    settings_changed = QtCore.Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Settings")
        self.setMinimumSize(560, 480)
        self._data = load_settings()

        outer = QtWidgets.QVBoxLayout(self)

        self._tabs = QtWidgets.QTabWidget()
        outer.addWidget(self._tabs)

        self._tabs.addTab(self._build_appearance(),  "🎨  Appearance")
        self._tabs.addTab(self._build_audio(),        "🎙  Audio Devices")
        self._tabs.addTab(self._build_playback(),     "▶  Playback")
        self._tabs.addTab(self._build_processing(),   "🔧  Processing")
        self._tabs.addTab(self._build_export_tab(),   "💾  Export")
        self._tabs.addTab(self._build_about(),        "ℹ  About")

        # OK / Cancel
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_appearance(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setSpacing(12)

        layout.addWidget(QtWidgets.QLabel(
            "<b>Colour theme</b><br>"
            "<small>Changes apply immediately for preview; "
            "confirmed on OK.</small>"
        ))

        self._theme_list = QtWidgets.QListWidget()
        self._theme_list.setFixedHeight(200)
        current = self._data.get("theme", DEFAULT_THEME)
        for key in THEME_KEYS:
            theme = THEMES[key]
            label = f"{'🌙' if theme.dark else '☀️'}  {theme.name}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self._theme_list.addItem(item)
            if key == current:
                self._theme_list.setCurrentItem(item)

        self._theme_list.currentItemChanged.connect(self._preview_theme)
        layout.addWidget(self._theme_list)

        layout.addStretch(1)
        return w

    def _preview_theme(self, current, _previous) -> None:
        if current is None:
            return
        key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        app = QtWidgets.QApplication.instance()
        if app:
            apply_theme(app, key)

    def _build_audio(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setSpacing(10)

        # Input device
        self._input_device_combo = QtWidgets.QComboBox()
        self._output_device_combo = QtWidgets.QComboBox()
        self._populate_device_combos()

        form.addRow("Input device:", self._input_device_combo)
        form.addRow("Output device:", self._output_device_combo)

        # Default sample rate
        self._sr_combo = QtWidgets.QComboBox()
        for sr in [22050, 44100, 48000, 88200, 96000]:
            self._sr_combo.addItem(f"{sr} Hz", userData=sr)
        self._sr_combo.setCurrentText(f"{self._data.get('default_sample_rate', 44100)} Hz")
        form.addRow("Default sample rate:", self._sr_combo)

        # Default channels
        self._ch_combo = QtWidgets.QComboBox()
        self._ch_combo.addItem("Mono (1)", userData=1)
        self._ch_combo.addItem("Stereo (2)", userData=2)
        idx = 0 if self._data.get("default_channels", 1) == 1 else 1
        self._ch_combo.setCurrentIndex(idx)
        form.addRow("Default recording channels:", self._ch_combo)

        refresh_btn = QtWidgets.QPushButton("Refresh device list")
        refresh_btn.clicked.connect(self._populate_device_combos)
        form.addRow("", refresh_btn)

        return w

    def _populate_device_combos(self) -> None:
        try:
            from crisp.core.recorder import list_input_devices
            import sounddevice as sd

            self._input_device_combo.clear()
            self._output_device_combo.clear()
            self._input_device_combo.addItem("System default", userData=None)
            self._output_device_combo.addItem("System default", userData=None)

            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    self._input_device_combo.addItem(f"{d['name']}", userData=i)
                if d["max_output_channels"] > 0:
                    self._output_device_combo.addItem(f"{d['name']}", userData=i)

            # Restore saved selection
            in_idx = self._data.get("input_device_index")
            out_idx = self._data.get("output_device_index")
            for i in range(self._input_device_combo.count()):
                if self._input_device_combo.itemData(i) == in_idx:
                    self._input_device_combo.setCurrentIndex(i)
            for i in range(self._output_device_combo.count()):
                if self._output_device_combo.itemData(i) == out_idx:
                    self._output_device_combo.setCurrentIndex(i)

        except Exception as exc:
            for combo in (self._input_device_combo, self._output_device_combo):
                combo.clear()
                combo.addItem(f"Error: {exc}", userData=None)

    def _build_playback(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setSpacing(10)

        # Volume slider
        self._vol_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(int(self._data.get("playback_volume", 1.0) * 100))
        self._vol_label = QtWidgets.QLabel(f"{self._vol_slider.value()}%")
        self._vol_slider.valueChanged.connect(
            lambda v: self._vol_label.setText(f"{v}%")
        )
        vol_row = QtWidgets.QHBoxLayout()
        vol_row.addWidget(self._vol_slider, 1)
        vol_row.addWidget(self._vol_label)
        form.addRow("Playback volume:", vol_row)

        # Auto-play after cleanup
        self._auto_play_cb = QtWidgets.QCheckBox("Auto-play B (cleaned) after cleanup finishes")
        self._auto_play_cb.setChecked(bool(self._data.get("auto_play_after_cleanup", False)))
        form.addRow("", self._auto_play_cb)

        # Show LUFS on load
        self._show_lufs_cb = QtWidgets.QCheckBox("Show LUFS measurement when file is loaded")
        self._show_lufs_cb.setChecked(bool(self._data.get("show_lufs_on_load", True)))
        form.addRow("", self._show_lufs_cb)

        return w

    def _build_processing(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setSpacing(10)

        self._auto_noise_cb = QtWidgets.QCheckBox("Enable Noise Reduction by default")
        self._auto_noise_cb.setChecked(bool(self._data.get("auto_enable_noise", True)))
        form.addRow("", self._auto_noise_cb)

        self._auto_loud_cb = QtWidgets.QCheckBox("Enable Loudness Normalization by default")
        self._auto_loud_cb.setChecked(bool(self._data.get("auto_enable_loudness", True)))
        form.addRow("", self._auto_loud_cb)

        self._batch_confirm_cb = QtWidgets.QCheckBox("Confirm before starting batch jobs")
        self._batch_confirm_cb.setChecked(bool(self._data.get("confirm_before_batch", True)))
        form.addRow("", self._batch_confirm_cb)

        return w

    def _build_export_tab(self) -> QtWidgets.QWidget:
        from crisp.core.presets import Format, WAV_SUBTYPES

        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setSpacing(10)

        self._def_fmt_combo = QtWidgets.QComboBox()
        for fmt in Format:
            self._def_fmt_combo.addItem(fmt.value.upper(), userData=fmt.value)
        saved_fmt = self._data.get("default_format", "wav")
        for i in range(self._def_fmt_combo.count()):
            if self._def_fmt_combo.itemData(i) == saved_fmt:
                self._def_fmt_combo.setCurrentIndex(i)
        form.addRow("Default format:", self._def_fmt_combo)

        self._def_subtype_combo = QtWidgets.QComboBox()
        for label, sub in WAV_SUBTYPES.items():
            self._def_subtype_combo.addItem(label, userData=sub)
        saved_sub = self._data.get("default_wav_subtype", "PCM_24")
        for i in range(self._def_subtype_combo.count()):
            if self._def_subtype_combo.itemData(i) == saved_sub:
                self._def_subtype_combo.setCurrentIndex(i)
        form.addRow("Default bit depth (WAV/FLAC/AIFF):", self._def_subtype_combo)

        self._def_bitrate_combo = QtWidgets.QComboBox()
        for br in ["64k", "96k", "128k", "192k", "256k", "320k"]:
            self._def_bitrate_combo.addItem(br, userData=br)
        self._def_bitrate_combo.setCurrentText(self._data.get("default_bitrate", "192k"))
        form.addRow("Default bitrate (MP3/AAC/OPUS/OGG):", self._def_bitrate_combo)

        self._norm_export_cb = QtWidgets.QCheckBox("Always normalize loudness on export")
        self._norm_export_cb.setChecked(bool(self._data.get("normalize_on_export", False)))
        form.addRow("", self._norm_export_cb)

        self._lufs_spin = QtWidgets.QDoubleSpinBox()
        self._lufs_spin.setRange(-30.0, -9.0)
        self._lufs_spin.setSingleStep(0.5)
        self._lufs_spin.setSuffix(" LUFS")
        self._lufs_spin.setValue(float(self._data.get("default_target_lufs", -16.0)))
        self._lufs_spin.setEnabled(self._norm_export_cb.isChecked())
        self._norm_export_cb.toggled.connect(self._lufs_spin.setEnabled)
        form.addRow("Loudness target:", self._lufs_spin)

        return w

    def _build_about(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setSpacing(8)
        layout.addStretch(1)

        title = QtWidgets.QLabel(f"<h2>{APP_NAME}</h2>")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver = QtWidgets.QLabel(f"<b>Version:</b> {__version__}")
        ver.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        desc = QtWidgets.QLabel(
            "Audio cleanup and enhancement tool.\n"
            "Built with PySide6 · scipy · noisereduce · pyloudnorm · soundfile · ffmpeg."
        )
        desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        settings_path_label = QtWidgets.QLabel(
            f"<small>Settings file: <code>{_SETTINGS_PATH}</code></small>"
        )
        settings_path_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(settings_path_label)

        reset_btn = QtWidgets.QPushButton("Reset all settings to defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        return w

    # ------------------------------------------------------------------
    # Accept / reject
    # ------------------------------------------------------------------

    def _reset_defaults(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self, "Reset settings",
            "Reset all settings to factory defaults? This cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self._data = dict(_DEFAULTS)
            save_settings(self._data)
            QtWidgets.QMessageBox.information(self, "Reset", "Settings reset. Restart to apply.")

    def _on_ok(self) -> None:
        # --- Appearance ---
        item = self._theme_list.currentItem()
        if item:
            self._data["theme"] = item.data(QtCore.Qt.ItemDataRole.UserRole)

        # --- Audio ---
        self._data["input_device_index"]  = self._input_device_combo.currentData()
        self._data["output_device_index"] = self._output_device_combo.currentData()
        self._data["default_sample_rate"] = self._sr_combo.currentData()
        self._data["default_channels"]    = self._ch_combo.currentData()

        # --- Playback ---
        self._data["playback_volume"]          = self._vol_slider.value() / 100.0
        self._data["auto_play_after_cleanup"]  = self._auto_play_cb.isChecked()
        self._data["show_lufs_on_load"]        = self._show_lufs_cb.isChecked()

        # --- Processing ---
        self._data["auto_enable_noise"]    = self._auto_noise_cb.isChecked()
        self._data["auto_enable_loudness"] = self._auto_loud_cb.isChecked()
        self._data["confirm_before_batch"] = self._batch_confirm_cb.isChecked()

        # --- Export ---
        self._data["default_format"]      = self._def_fmt_combo.currentData()
        self._data["default_wav_subtype"] = self._def_subtype_combo.currentData()
        self._data["default_bitrate"]     = self._def_bitrate_combo.currentText()
        self._data["normalize_on_export"] = self._norm_export_cb.isChecked()
        self._data["default_target_lufs"] = self._lufs_spin.value()

        save_settings(self._data)
        self.settings_changed.emit(self._data)
        self.accept()

    def reject(self) -> None:
        # Revert preview theme to whatever was saved.
        saved = load_settings().get("theme", DEFAULT_THEME)
        app = QtWidgets.QApplication.instance()
        if app:
            apply_theme(app, saved)
        super().reject()
