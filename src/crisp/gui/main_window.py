"""The main application window."""
from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from crisp import APP_NAME, __version__
from crisp.core import audio_io
from crisp.core.audio import AudioClip
from crisp.core.engine import CleanupSettings
from crisp.core.exporter import export
from crisp.core.presets import PRESETS, ExportSettings, Format, WAV_SUBTYPES
from crisp.core.processors import ALL_PROCESSORS
from crisp.core.processors.loudness import LoudnessNormalize
from crisp.core.recorder import Recorder, default_input_device, list_input_devices
from crisp.gui.player import ABPlayer
from crisp.gui.waveform import WaveformPair
from crisp.gui.widgets import ProcessorPanel
from crisp.gui.workers import BatchWorker, CleanupWorker

_AUDIO_FILTER = "Audio (*.wav *.flac *.ogg *.mp3 *.m4a *.aac *.aiff)"
_SETTINGS_FILTER = "Crisp settings (*.crisp.json *.json)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1100, 720)

        self._original: AudioClip | None = None
        self._cleaned: AudioClip | None = None
        self._recorder: Recorder | None = None
        self._player = ABPlayer()
        self._cleanup_worker: CleanupWorker | None = None
        self._batch_worker: BatchWorker | None = None
        self._settings = CleanupSettings.defaults()

        # Drives the waveform playhead while audio is playing (~30 fps).
        self._playhead_timer = QtCore.QTimer(self)
        self._playhead_timer.setInterval(33)
        self._playhead_timer.timeout.connect(self._tick_playhead)

        self._build_ui()
        self._refresh_devices()

    # ----- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)

        root.addLayout(self._build_left_panel(), 0)
        root.addLayout(self._build_center(), 1)

        self.statusBar().showMessage("Ready")

    def _build_left_panel(self) -> QtWidgets.QVBoxLayout:
        col = QtWidgets.QVBoxLayout()

        # --- Source: device + record / open ---
        src_box = QtWidgets.QGroupBox("Source")
        src = QtWidgets.QVBoxLayout(src_box)
        self.device_combo = QtWidgets.QComboBox()
        src.addWidget(QtWidgets.QLabel("Input device"))
        src.addWidget(self.device_combo)

        btn_row = QtWidgets.QHBoxLayout()
        self.record_btn = QtWidgets.QPushButton("● Record")
        self.record_btn.clicked.connect(self._toggle_record)
        self.open_btn = QtWidgets.QPushButton("Open file…")
        self.open_btn.clicked.connect(self._open_file)
        btn_row.addWidget(self.record_btn)
        btn_row.addWidget(self.open_btn)
        src.addLayout(btn_row)

        self.level_bar = QtWidgets.QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        src.addWidget(QtWidgets.QLabel("Input level"))
        src.addWidget(self.level_bar)
        col.addWidget(src_box)

        # --- Cleanup: one collapsible panel per stage, each with sliders ---
        clean_box = QtWidgets.QGroupBox("Cleanup")
        clean = QtWidgets.QVBoxLayout(clean_box)
        
        # Create a tabbed interface for processor groups instead of just stacking 
        tab_widget = QtWidgets.QTabWidget()
        
        # Group processors by type for better organization
        noise_tab = QtWidgets.QWidget()
        noise_layout = QtWidgets.QVBoxLayout(noise_tab)
        noise_layout.setContentsMargins(5, 5, 5, 5)
        
        dereverb_tab = QtWidgets.QWidget()
        dereverb_layout = QtWidgets.QVBoxLayout(dereverb_tab)
        dereverb_layout.setContentsMargins(5, 5, 5, 5)
        
        eq_clarity_tab = QtWidgets.QWidget()
        eq_clarity_layout = QtWidgets.QVBoxLayout(eq_clarity_tab)
        eq_clarity_layout.setContentsMargins(5, 5, 5, 5)
        
        loudness_tab = QtWidgets.QWidget()
        loudness_layout = QtWidgets.QVBoxLayout(loudness_tab)
        loudness_layout.setContentsMargins(5, 5, 5, 5)
        
        # Processor grouping
        noise_processors = []
        dereverb_processors = []
        eq_clarity_processors = []
        loudness_processors = []
        
        # Add processors to appropriate tabs
        for proc in ALL_PROCESSORS:
            if 'noise' in proc.key.lower():
                noise_processors.append(proc)
            elif 'dereverb' in proc.key.lower():
                dereverb_processors.append(proc)
            elif 'eq' in proc.key.lower() or 'clarity' in proc.key.lower():
                eq_clarity_processors.append(proc)
            elif 'loudness' in proc.key.lower():
                loudness_processors.append(proc)
        
        # Create panels for each processor and add to their corresponding tabs
        self.panels: dict[str, ProcessorPanel] = {}
        
        # Noise reduction processors
        for proc in noise_processors:
            panel = ProcessorPanel(
                proc,
                enabled=self._settings.is_enabled(proc.key),
                params=self._settings.params.get(proc.key, {}),
                on_enabled=self._set_enabled,
                on_param=self._set_param,
            )
            noise_layout.addWidget(panel)
            self.panels[proc.key] = panel
        
        # Dereverb processors
        for proc in dereverb_processors:
            panel = ProcessorPanel(
                proc,
                enabled=self._settings.is_enabled(proc.key),
                params=self._settings.params.get(proc.key, {}),
                on_enabled=self._set_enabled,
                on_param=self._set_param,
            )
            dereverb_layout.addWidget(panel)
            self.panels[proc.key] = panel
            
        # EQ and clarity processors
        for proc in eq_clarity_processors:
            panel = ProcessorPanel(
                proc,
                enabled=self._settings.is_enabled(proc.key),
                params=self._settings.params.get(proc.key, {}),
                on_enabled=self._set_enabled,
                on_param=self._set_param,
            )
            eq_clarity_layout.addWidget(panel)
            self.panels[proc.key] = panel
            
        # Loudness processors
        for proc in loudness_processors:
            panel = ProcessorPanel(
                proc,
                enabled=self._settings.is_enabled(proc.key),
                params=self._settings.params.get(proc.key, {}),
                on_enabled=self._set_enabled,
                on_param=self._set_param,
            )
            loudness_layout.addWidget(panel)
            self.panels[proc.key] = panel
        
        # Add tabs to widget
        tab_widget.addTab(noise_tab, "Noise Reduction")
        tab_widget.addTab(dereverb_tab, "Dereverberation")
        tab_widget.addTab(eq_clarity_tab, "EQ & Clarity")
        tab_widget.addTab(loudness_tab, "Loudness")
        
        clean.addWidget(tab_widget)

        # Save / load custom cleanup settings (toggles + slider values).
        io_row = QtWidgets.QHBoxLayout()
        self.save_settings_btn = QtWidgets.QPushButton("Save settings…")
        self.save_settings_btn.clicked.connect(self._save_settings)
        self.load_settings_btn = QtWidgets.QPushButton("Load settings…")
        self.load_settings_btn.clicked.connect(self._load_settings)
        io_row.addWidget(self.save_settings_btn)
        io_row.addWidget(self.load_settings_btn)
        clean.addLayout(io_row)

        self.apply_btn = QtWidgets.QPushButton("Apply cleanup")
        self.apply_btn.clicked.connect(self._apply_cleanup)
        clean.addWidget(self.apply_btn)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        clean.addWidget(self.progress)
        col.addWidget(clean_box, 1)

        # --- Export ---
        col.addWidget(self._build_export_box())
        col.addStretch(1)
        return col

    def _build_export_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Export")
        form = QtWidgets.QFormLayout(box)

        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItem("Custom", userData=None)
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, userData=key)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        form.addRow("Preset", self.preset_combo)

        self.format_combo = QtWidgets.QComboBox()
        for fmt in Format:
            self.format_combo.addItem(fmt.value.upper(), userData=fmt)
        self.format_combo.currentIndexChanged.connect(self._update_export_fields)
        form.addRow("Format", self.format_combo)

        self.subtype_combo = QtWidgets.QComboBox()
        for label in WAV_SUBTYPES:
            self.subtype_combo.addItem(label, userData=WAV_SUBTYPES[label])
        form.addRow("Bit depth", self.subtype_combo)

        self.bitrate_combo = QtWidgets.QComboBox()
        self.bitrate_combo.addItems(["96k", "128k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText("192k")
        form.addRow("Bitrate", self.bitrate_combo)

        self.export_btn = QtWidgets.QPushButton("Export cleaned…")
        self.export_btn.clicked.connect(self._export_file)
        form.addRow(self.export_btn)

        self.batch_btn = QtWidgets.QPushButton("Batch folder…")
        self.batch_btn.clicked.connect(self._batch)
        form.addRow(self.batch_btn)

        self._update_export_fields()
        return box

    def _build_center(self) -> QtWidgets.QVBoxLayout:
        col = QtWidgets.QVBoxLayout()
        self.waveforms = WaveformPair()
        col.addWidget(self.waveforms, 1)

        # Transport / A-B row
        bar = QtWidgets.QHBoxLayout()
        self.play_btn = QtWidgets.QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._toggle_play)
        bar.addWidget(self.play_btn)

        self.ab_group = QtWidgets.QButtonGroup(self)
        self.a_btn = QtWidgets.QRadioButton("A · Original")
        self.b_btn = QtWidgets.QRadioButton("B · Cleaned")
        self.a_btn.setChecked(True)
        self.ab_group.addButton(self.a_btn)
        self.ab_group.addButton(self.b_btn)
        self.a_btn.toggled.connect(self._on_ab_changed)
        bar.addWidget(self.a_btn)
        bar.addWidget(self.b_btn)
        bar.addStretch(1)

        self.lufs_label = QtWidgets.QLabel("LUFS: —")
        bar.addWidget(self.lufs_label)
        col.addLayout(bar)
        return col

    # ----- Devices / recording --------------------------------------------

    def _refresh_devices(self) -> None:
        self.device_combo.clear()
        try:
            devices = list_input_devices()
        except Exception as exc:
            self.statusBar().showMessage(f"Could not list devices: {exc}")
            return
        default = default_input_device()
        for d in devices:
            self.device_combo.addItem(f"{d.name} ({d.max_input_channels}ch)", userData=d)
            if default and d.index == default.index:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)

    def _toggle_record(self) -> None:
        if self._recorder and self._recorder.is_recording:
            clip = self._recorder.stop()
            self._recorder = None
            self.record_btn.setText("● Record")
            self.level_bar.setValue(0)
            self._set_original(clip)
            self.statusBar().showMessage(f"Recorded {clip.duration:.1f}s")
            return

        device = self.device_combo.currentData()
        if device is None:
            self.statusBar().showMessage("No input device selected")
            return
        self._recorder = Recorder(
            device_index=device.index,
            sample_rate=device.default_samplerate,
            channels=1,
            level_callback=self._on_level,
        )
        try:
            self._recorder.start()
        except Exception as exc:
            self.statusBar().showMessage(f"Record failed: {exc}")
            self._recorder = None
            return
        self.record_btn.setText("■ Stop")
        self.statusBar().showMessage("Recording…")

    def _on_level(self, level: float) -> None:
        # Called from the audio thread; marshal to the GUI thread.
        QtCore.QMetaObject.invokeMethod(
            self.level_bar, "setValue", QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(int, int(min(level, 1.0) * 100)),
        )

    # ----- Loading / cleanup ----------------------------------------------

    def _open_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open audio", "", _AUDIO_FILTER)
        if not path:
            return
        try:
            clip = audio_io.load(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._set_original(clip)
        self.statusBar().showMessage(f"Loaded {Path(path).name} · {clip.duration:.1f}s")

    def _set_original(self, clip: AudioClip) -> None:
        self._original = clip
        self._cleaned = None
        self._player.set_clip("A", clip)
        self._player.set_clip("B", None)
        self.waveforms.set_before(clip)
        self.waveforms.set_after(None)
        self.a_btn.setChecked(True)
        self._update_lufs()

    def _set_enabled(self, key: str, on: bool) -> None:
        self._settings.enabled[key] = on

    def _set_param(self, key: str, param: str, value: object) -> None:
        self._settings.params.setdefault(key, {})[param] = value

    def _save_settings(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save cleanup settings", "cleanup.crisp.json", _SETTINGS_FILTER
        )
        if not path:
            return
        try:
            self._settings.save(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.statusBar().showMessage(f"Saved settings to {Path(path).name}")

    def _load_settings(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load cleanup settings", "", _SETTINGS_FILTER
        )
        if not path:
            return
        try:
            self._settings = CleanupSettings.load(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(exc))
            return
        # Reflect the loaded values back into every panel's controls.
        for key, panel in self.panels.items():
            panel.set_state(self._settings.is_enabled(key), self._settings.params.get(key, {}))
        self.statusBar().showMessage(f"Loaded settings from {Path(path).name}")

    def _apply_cleanup(self) -> None:
        if self._original is None:
            self.statusBar().showMessage("Load or record audio first")
            return
        if self._cleanup_worker and self._cleanup_worker.isRunning():
            return
        self.apply_btn.setEnabled(False)
        self.progress.setValue(0)
        self._cleanup_worker = CleanupWorker(self._original, self._settings)
        self._cleanup_worker.progress.connect(self._on_cleanup_progress)
        self._cleanup_worker.finished_ok.connect(self._on_cleanup_done)
        self._cleanup_worker.failed.connect(self._on_cleanup_failed)
        self._cleanup_worker.start()

    def _on_cleanup_progress(self, label: str, frac: float) -> None:
        self.progress.setValue(int(frac * 100))
        self.statusBar().showMessage(f"Cleaning: {label}")

    def _on_cleanup_done(self, clip: AudioClip) -> None:
        self._cleaned = clip
        self._player.set_clip("B", clip)
        self.waveforms.set_after(clip)
        self.progress.setValue(100)
        self.apply_btn.setEnabled(True)
        self.b_btn.setChecked(True)
        self.statusBar().showMessage("Cleanup complete")
        self._update_lufs()

    def _on_cleanup_failed(self, msg: str) -> None:
        self.apply_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Cleanup failed", msg)

    # ----- Playback / A-B --------------------------------------------------

    def _toggle_play(self) -> None:
        if self._player.is_playing:
            self._stop_playback()
        else:
            self._player.play()
            self.play_btn.setText("■ Stop")
            self._playhead_timer.start()

    def _stop_playback(self) -> None:
        self._player.stop()
        self._playhead_timer.stop()
        self.play_btn.setText("▶ Play")
        self.waveforms.set_playhead(None)

    def _tick_playhead(self) -> None:
        # Playback can end on its own (clip ran out); detect and reset.
        if not self._player.is_playing:
            self._stop_playback()
            return
        self.waveforms.set_playhead(self._player.position_seconds())

    def _on_ab_changed(self) -> None:
        self._player.select("A" if self.a_btn.isChecked() else "B")
        self._update_lufs()

    def _update_lufs(self) -> None:
        clip = self._cleaned if self.b_btn.isChecked() else self._original
        if clip is None or clip.frames == 0:
            self.lufs_label.setText("LUFS: —")
            return
        try:
            lufs = LoudnessNormalize().measure_lufs(clip)
            self.lufs_label.setText(f"LUFS: {lufs:.1f}")
        except Exception:
            self.lufs_label.setText("LUFS: —")

    # ----- Export ----------------------------------------------------------

    def _current_format(self) -> Format:
        return self.format_combo.currentData()

    def _update_export_fields(self) -> None:
        fmt = self._current_format()
        self.subtype_combo.setEnabled(fmt in (Format.WAV, Format.FLAC))
        self.bitrate_combo.setEnabled(fmt in (Format.MP3, Format.AAC, Format.OGG))

    def _apply_preset(self) -> None:
        key = self.preset_combo.currentData()
        if key is None:
            return
        es = PRESETS[key].export
        self.format_combo.setCurrentText(es.fmt.value.upper())
        for label, sub in WAV_SUBTYPES.items():
            if sub == es.wav_subtype:
                self.subtype_combo.setCurrentText(label)
        self.bitrate_combo.setCurrentText(es.mp3_bitrate)
        self._update_export_fields()
        target = "default" if es.target_lufs is None else f"{es.target_lufs:g} LUFS"
        self.statusBar().showMessage(f"Preset: {PRESETS[key].name} ({target})")

    def _build_export_settings(self) -> ExportSettings:
        key = self.preset_combo.currentData()
        target = PRESETS[key].export.target_lufs if key else None
        return ExportSettings(
            fmt=self._current_format(),
            wav_subtype=self.subtype_combo.currentData(),
            mp3_bitrate=self.bitrate_combo.currentText(),
            target_lufs=target,
        )

    def _export_file(self) -> None:
        clip = self._cleaned or self._original
        if clip is None:
            self.statusBar().showMessage("Nothing to export")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export", "", "Audio files (*.*)")
        if not path:
            return
        try:
            out = export(clip, path, self._build_export_settings())
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {out.name}")

    def _batch(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder of audio to clean")
        if not folder:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder")
        if not out_dir:
            return
        if self._batch_worker and self._batch_worker.isRunning():
            return
        self.batch_btn.setEnabled(False)
        self._batch_worker = BatchWorker(
            Path(folder), Path(out_dir), self._settings, self._build_export_settings()
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished_all.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.start()

    def _on_batch_progress(self, name: str, idx: int, total: int, status: str) -> None:
        self.statusBar().showMessage(f"[{idx + 1}/{total}] {name}: {status}")

    def _on_batch_done(self, results: list) -> None:
        self.batch_btn.setEnabled(True)
        ok = sum(1 for r in results if r.ok)
        QtWidgets.QMessageBox.information(
            self, "Batch complete", f"Processed {ok}/{len(results)} files successfully."
        )

    def _on_batch_failed(self, msg: str) -> None:
        self.batch_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Batch failed", msg)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._player.stop()
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
        super().closeEvent(event)
