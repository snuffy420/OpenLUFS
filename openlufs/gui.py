"""Qt interface. All filesystem analysis and audio work runs on a worker thread."""
import json
import math
import os
from pathlib import Path
import sys
import threading
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QTextBrowser, QCheckBox, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QProgressBar, QPlainTextEdit, QStackedWidget,
    QScrollArea, QLayout, QSizePolicy)
from . import __version__
from .batch import process_batch, write_report
from .engine import Cancelled, Engine, resource_path
from .models import Settings, discover, plan_outputs, SUPPORTED_DISPLAY, SUPPORTED_SUMMARY, AUDIO_FILE_FILTER
from .theme import STYLE
from .help import ABOUT_HTML
from .analysis_cache import AnalysisCache


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    return result


def button(text, callback, name=None):
    result = QPushButton(text)
    if name:
        result.setObjectName(name)
    result.clicked.connect(callback)
    return result


def number(value, suffix=""):
    return f"{value:.2f}{suffix}" if math.isfinite(value) else "Unmeasurable"


class Worker(QThread):
    track_update = pyqtSignal(int, str, object)

    def __init__(self, mode, files, settings=None, planned=None, output=None, analysis_cache=None):
        super().__init__()
        self.mode, self.files, self.settings = mode, files, settings
        self.planned, self.output = planned, output
        self.cancel = threading.Event()
        self.outcome = None
        self.analysis_cache = analysis_cache if analysis_cache is not None else AnalysisCache()

    def run(self):
        try:
            if self.mode == "scan":
                self.outcome = {"files": discover(self.files, exclude=self.output, cancel=self.cancel)}
            elif self.mode == "analyze":
                engine, errors = Engine(self.cancel), []
                for i, path in enumerate(self.files):
                    if self.cancel.is_set():
                        break
                    self.track_update.emit(i, "Using analysis" if self.analysis_cache.get(path) is not None else "Measuring", None)
                    try:
                        measurement = self.analysis_cache.measure(path, engine.analyze)
                        self.track_update.emit(i, "Analyzed", measurement)
                    except Cancelled:
                        self.track_update.emit(i, "Cancelled", None)
                        break
                    except Exception as error:
                        errors.append(str(error))
                        self.track_update.emit(i, "Failed", str(error))
                self.outcome = {"errors": errors, "cancelled": self.cancel.is_set()}
            else:
                results, errors = process_batch(self.planned, self.settings, self.cancel, self.track_update.emit, self.analysis_cache)
                self.outcome = {"results": results, "errors": errors, "cancelled": self.cancel.is_set()}
                try:
                    self.outcome["report"] = str(write_report(self.output, self.settings, results, errors, self.cancel.is_set()))
                except Exception as error:
                    self.outcome["report_error"] = str(error)
        except Exception as error:
            self.outcome = {"fatal": str(error)}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenLUFS")
        self.setWindowIcon(QIcon(str(resource_path("assets/openlufs.ico"))))
        self.resize(1220, 830)
        self.setMinimumSize(780, 520)
        self.setAcceptDrops(True)
        self.files, self.details = [], {}
        self.analysis_cache = AnalysisCache()
        self.worker, self.source_root, self.report = None, None, None
        self.closing = False
        self._loading_settings = True
        self.preview_style = "Normal"
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else resource_path("")
        self.config_path = (Path.home()/"Library/Application Support/OpenLUFS/settings.json"
                            if sys.platform == "darwin" else base/"OpenLUFS.settings.json")
        self.build_ui()
        self.load_settings()
        self._loading_settings = False
        self.refresh_processing_controls()
        QShortcut(QKeySequence(QKeySequence.StandardKey.Open), self, activated=self.add_files)
        remove_shortcut = QShortcut(QKeySequence("Delete"), self.table, activated=self.remove_selected)
        remove_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.update_count()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        shell = QVBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        header = QWidget()
        header.setObjectName("Header")
        self.header_layout = top = QGridLayout(header)
        top.setContentsMargins(28, 19, 28, 19)
        top.setHorizontalSpacing(20)
        top.setVerticalSpacing(16)
        self.brand = QWidget()
        brand_row = QHBoxLayout(self.brand)
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(resource_path("assets/mark.png"))).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand_row.addWidget(logo)
        brand_row.addWidget(label("OpenLUFS", "Brand"))
        brand_row.addWidget(label(__version__, "Muted"))
        self.file_toolbar = QWidget()
        toolbar = QHBoxLayout(self.file_toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)
        self.add_button = button("Add files", self.add_files)
        self.folder_button = button("Add folder", self.add_folder)
        self.remove_button = button("Remove", self.remove_selected, "Quiet")
        self.clear_button = button("Clear", self.clear, "Quiet")
        for widget in [self.add_button, self.folder_button, self.remove_button, self.clear_button]:
            toolbar.addWidget(widget)
        self.preview_button = button("Preview", self.preview)
        toolbar.addWidget(self.preview_button)
        toolbar.addStretch()
        self.about_button = button("About", self.about, "Quiet")
        top.addWidget(self.brand, 0, 0)
        top.addWidget(self.file_toolbar, 0, 1)
        top.addWidget(self.about_button, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)
        top.setColumnStretch(1, 1)
        self.header_wrapped = False
        self.arrange_header()
        shell.addWidget(header)
        content = QWidget()
        body = QHBoxLayout(content)
        body.setContentsMargins(28, 16, 28, 14)
        body.setSpacing(22)
        body.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        left = QVBoxLayout()
        left.setSpacing(10)
        self.stack = QStackedWidget()
        empty = QFrame()
        empty.setObjectName("Panel")
        el = QVBoxLayout(empty)
        el.addStretch()
        artwork = QLabel()
        artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        artwork.setPixmap(QPixmap(str(resource_path("assets/empty-state.png"))))
        el.addWidget(artwork)
        heading = label("Add audio to begin", "PageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(heading)
        helper = label("Drop files or folders here, or use Add files.", "Muted")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(helper)
        self.supported_label = supported = label(SUPPORTED_SUMMARY, "Muted")
        supported.setToolTip(SUPPORTED_DISPLAY)
        supported.setWordWrap(True)
        supported.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addSpacing(14)
        el.addWidget(supported)
        el.addStretch()
        self.stack.addWidget(empty)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["TRACK", "TIME", "INPUT LUFS", "OUTPUT LUFS", "PEAK dBTP", "STATUS"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, width in [(1, 58), (2, 91), (3, 99), (4, 91), (5, 152)]:
            self.table.setColumnWidth(col, width)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.stack.addWidget(self.table)
        left.addWidget(self.stack, 1)
        self.details_panel = QFrame()
        self.details_panel.setObjectName("Panel")
        self.details_panel.setFixedHeight(116)
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(14, 10, 14, 10)
        details_layout.setSpacing(6)
        details_layout.addWidget(label("TRACK DETAILS", "Section"))
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("TrackDetails")
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(42)
        self.detail.setPlaceholderText("Select a track to inspect measurements, export paths, and processing notes.")
        details_layout.addWidget(self.detail, 1)
        left.addWidget(self.details_panel)
        body.addLayout(left, 1)
        self.normalization_panel = panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(286)
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(20, 16, 20, 16)
        controls.setSpacing(8)
        panel_title = QHBoxLayout()
        panel_title.addWidget(label("NORMALIZATION", "Section"))
        panel_title.addStretch()
        self.count_label = label("0 tracks", "Muted")
        panel_title.addWidget(self.count_label)
        controls.addLayout(panel_title)
        controls.addSpacing(2)
        self.normalize_enabled = QCheckBox("LUFS normalization")
        self.normalize_enabled.setChecked(True)
        self.normalize_enabled.toggled.connect(self.refresh_processing_controls)
        controls.addWidget(self.normalize_enabled)
        self.target = QDoubleSpinBox()
        self.target.setObjectName("Target")
        self.target.setRange(-36, -6)
        self.target.setDecimals(1)
        self.target.setSingleStep(0.5)
        self.target.setValue(-12)
        self.target.setMinimumHeight(58)
        self.target.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.target.setKeyboardTracking(False)
        self.target.setSuffix("  LUFS")
        self.target.setAccessibleName("Target integrated loudness in LUFS")
        controls.addWidget(self.target)
        controls.addSpacing(4)
        self.limiter_enabled = QCheckBox("True-peak limiter")
        self.limiter_enabled.setChecked(False)
        self.limiter_enabled.setToolTip("Enable peak limiting. Leave unchecked for constant gain that preserves dynamics and reports any peak-safe target shortfall.")
        self.limiter_enabled.toggled.connect(self.refresh_processing_controls)
        controls.addWidget(self.limiter_enabled)
        self.ceiling = QDoubleSpinBox()
        self.ceiling.setObjectName("Target")
        self.ceiling.setRange(-9, -0.1)
        self.ceiling.setDecimals(1)
        self.ceiling.setSingleStep(0.1)
        self.ceiling.setValue(-1)
        self.ceiling.setMinimumHeight(58)
        self.ceiling.setKeyboardTracking(False)
        self.ceiling.setAccessibleName("True-peak ceiling in dBTP")
        self.ceiling.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ceiling.setSuffix("  dBTP")
        controls.addWidget(self.ceiling)
        controls.addSpacing(6)
        controls.addWidget(label("EXPORT", "Section"))
        self.mirror = QCheckBox("Keep folder structure")
        self.mirror.setChecked(True)
        controls.addWidget(self.mirror)
        controls.addStretch()
        self.analyze_button = button("Analyze", self.analyze)
        controls.addWidget(self.analyze_button)
        self.report_button = button("Open report", self.open_report, "Quiet")
        self.report_button.setEnabled(True)
        controls.addWidget(self.report_button)
        body.addWidget(panel)
        self.content_scroll = QScrollArea()
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setWidget(content)
        shell.addWidget(self.content_scroll, 1)
        output = QHBoxLayout()
        output.setContentsMargins(28, 0, 28, 18)
        output.addWidget(label("Output folder", "Muted"))
        self.output = QLineEdit()
        self.output.setPlaceholderText("Choose a folder for normalized copies")
        output.addWidget(self.output, 1)
        output.addSpacing(12)
        self.browse_button = button("Browse", self.browse_output)
        output.addWidget(self.browse_button)
        shell.addLayout(output)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        shell.addWidget(self.progress)
        footer = QHBoxLayout()
        footer.setContentsMargins(28, 15, 28, 18)
        self.status = label("Ready", "Muted")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.cancel_button = button("Cancel", self.cancel, "Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        footer.addSpacing(12)
        self.normalize_button = button("Process LUFS", self.normalize, "Primary")
        self.normalize_button.setMinimumWidth(184)
        footer.addWidget(self.normalize_button)
        shell.addLayout(footer)
        self.lock_controls = [self.add_button, self.folder_button, self.remove_button,
            self.clear_button, self.analyze_button, self.target, self.ceiling,
            self.normalize_enabled, self.limiter_enabled, self.preview_button, self.mirror, self.output, self.browse_button, self.normalize_button]

    def busy(self):
        return self.worker is not None and self.worker.isRunning()

    def update_count(self):
        count = len(self.files)
        self.count_label.setText(f"{count} track{'s' if count != 1 else ''}")
        self.stack.setCurrentIndex(1 if count else 0)
        for control in (self.analyze_button, self.normalize_button, self.clear_button, self.remove_button):
            control.setEnabled(bool(count) and not self.busy())
        self.refresh_processing_controls()

    def add_files(self):
        if self.busy():
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Add audio files", "", AUDIO_FILE_FILTER)
        if files:
            self.source_root = None
            self.scan(files)

    def add_folder(self):
        if self.busy():
            return
        folder = QFileDialog.getExistingDirectory(self, "Add audio folder")
        if folder:
            self.source_root = Path(folder) if not self.files else None
            self.scan([folder])

    def scan(self, paths):
        if self.busy():
            return
        self.start_worker(Worker("scan", paths, output=self.output.text().strip() or None))

    def append_files(self, paths):
        known = set(self.files)
        for path in paths:
            if path in known:
                continue
            known.add(path)
            self.files.append(path)
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in enumerate([path.name, "—", "—", "—", "—", "Queued"]):
                item = QTableWidgetItem(text)
                item.setToolTip(str(path))
                if col in {1, 2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
        self.update_count()

    def remove_selected(self):
        if self.busy():
            return
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            self.analysis_cache.discard(self.files[row])
            self.details.pop(str(self.files[row]), None)
            self.files.pop(row)
            self.table.removeRow(row)
        self.update_count()

    def clear(self):
        if self.busy():
            return
        self.files.clear()
        self.details.clear()
        self.analysis_cache.clear()
        self.source_root = None
        self.table.setRowCount(0)
        self.detail.clear()
        self.progress.setValue(0)
        self.status.setText("Ready")
        self.update_count()

    def arrange_header(self):
        minimum = (self.brand.sizeHint().width() + self.file_toolbar.minimumSizeHint().width()
                   + self.about_button.sizeHint().width() + 96)
        wrapped = self.width() < minimum
        if wrapped == self.header_wrapped:
            return
        self.header_layout.removeWidget(self.file_toolbar)
        self.header_layout.addWidget(self.file_toolbar, 1 if wrapped else 0,
                                     0 if wrapped else 1, 1, 3 if wrapped else 1)
        self.header_wrapped = wrapped

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "header_layout"):
            self.arrange_header()

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output.text())
        if folder:
            self.output.setText(folder)

    def current_settings(self):
        self.target.interpretText(); self.ceiling.interpretText()
        return Settings(self.target.value(), self.ceiling.value(),
                        allow_limiter=self.limiter_enabled.isChecked(),
                        normalize_lufs=self.normalize_enabled.isChecked())

    def refresh_processing_controls(self, *args):
        if not hasattr(self, "lock_controls"):
            return
        self.target.setEnabled(self.normalize_enabled.isChecked() and not self.busy())
        # The ceiling also defines the safe gain cap when limiting is off.
        self.ceiling.setEnabled(not self.busy())
        active=self.normalize_enabled.isChecked() or self.limiter_enabled.isChecked()
        self.normalize_button.setEnabled(bool(self.files) and active and not self.busy())
        self.preview_button.setEnabled(bool(self.files) and active and not self.busy())

    def open_report(self):
        from .report_viewer import ReportDialog
        dialog=ReportDialog(self.report, self)
        dialog.exec()
        if dialog.report_path:
            self.report=str(dialog.report_path)
            self.save_settings()

    def preview(self):
        if self.busy() or not self.files:
            return
        from .preview import PreviewDialog
        row=self.table.currentRow()
        source=self.files[row if row>=0 else 0]
        try:
            settings=self.current_settings()
            self.save_settings()
            output=Path(self.output.text().strip()) if self.output.text().strip() else None
            parent=output if output and output.is_dir() else None
            dialog=PreviewDialog(source, settings, self, self.analysis_cache, parent, self.preview_style)
            dialog.exec()
            self.preview_style=dialog.style_combo.currentText()
            self.save_settings()
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,"Preview could not be opened",str(error))

    def analyze(self):
        if self.files and not self.busy():
            self.start_worker(Worker("analyze", list(self.files), analysis_cache=self.analysis_cache))

    def normalize(self):
        if self.busy() or not self.files:
            return
        if not self.output.text().strip():
            self.browse_output()
            if not self.output.text().strip():
                return
        try:
            settings = self.current_settings()
            output = Path(self.output.text().strip()).expanduser().resolve()
            # Exports within an imported directory are allowed; rescans exclude the output tree.
            planned = plan_outputs(self.files, output, settings.output_format, self.source_root if self.mirror.isChecked() else None)
            self.save_settings()
            self.start_worker(Worker("normalize", list(self.files), settings, planned, output, self.analysis_cache))
        except Exception as error:
            QMessageBox.warning(self, "Cannot normalize", str(error))

    def start_worker(self, worker):
        self.worker = worker
        self.completed_rows = set()
        for widget in self.lock_controls:
            widget.setEnabled(False)
        self.cancel_button.setEnabled(worker.mode == "normalize")
        self.cancel_button.setVisible(worker.mode == "normalize")
        if worker.mode != "scan":
            for row in range(len(self.files)):
                cached = self.analysis_cache.get(self.files[row])
                for col in ([3] if cached is not None else [1, 2, 3, 4]):
                    self.table.item(row, col).setText("—")
                if cached is not None:
                    self.measurement_cells(row, cached)
                self.table.item(row, 5).setText("Queued")
        self.progress.setRange(0, 0 if worker.mode == "scan" else len(self.files))
        self.progress.setValue(0)
        self.status.setText("Scanning audio files…" if worker.mode == "scan" else "Starting…")
        worker.track_update.connect(self.track_event)
        worker.finished.connect(self.worker_finished)
        worker.start()

    def track_event(self, row, stage, payload):
        if row >= len(self.files):
            return
        shown_stage=("Processing" if self.worker and self.worker.mode=="normalize" and stage not in {"Complete","Failed","Cancelled"} else stage)
        self.table.item(row, 5).setText(shown_stage)
        self.table.item(row, 5).setForeground(QColor("#f0b2a0" if stage == "Failed" else "#65e4bd" if stage in {"Complete", "Analyzed"} else "#a2b4ae"))
        self.status.setText(f"{row+1} / {len(self.files)} · {self.files[row].name} · {shown_stage}")
        if stage in {"Analyzed", "Source ready"}:
            self.measurement_cells(row, payload)
            self.details[str(self.files[row])] = self.describe_measurement(payload)
        elif stage == "Complete":
            self.measurement_cells(row, payload.before)
            self.table.item(row, 3).setText(number(payload.after.integrated))
            self.table.item(row, 4).setText(number(payload.after.true_peak))
            self.table.item(row, 5).setText(payload.mode)
            difference=payload.after.integrated-self.worker.settings.target if self.worker and self.worker.settings.normalize_lufs else None
            target_note=(f"\nTarget difference: {difference:+.2f} LU — target not matched. "
                         "Peak headroom or encoded gain steps prevented an exact match; this track is not equally loud by LUFS."
                         if difference is not None and abs(difference)>.100001 else "")
            gain_label="Input gain" if payload.processing.get("limited") else "Gain"
            self.details[str(self.files[row])] = (
                f"{payload.mode} · Output {payload.after.integrated:.2f} LUFS / {payload.after.true_peak:.2f} dBTP"
                +target_note+"\n"+self.describe_measurement(payload.before)+
                f"\nExport: {payload.destination}\n{gain_label} {payload.gain_db:+.2f} dB\n"+"\n".join(payload.warnings))
        elif stage == "Failed":
            previous = self.details.get(str(self.files[row]), "")
            self.details[str(self.files[row])] = (previous+"\n" if previous else "")+str(payload)
            for col in (3,):
                self.table.item(row, col).setText("—")
        if stage in {"Analyzed", "Complete", "Failed", "Cancelled"}:
            self.completed_rows.add(row)
            self.progress.setValue(len(self.completed_rows))
        self.show_details()

    def measurement_cells(self, row, m):
        seconds = int(m.duration)
        self.table.item(row, 1).setText(f"{seconds//60}:{seconds%60:02d}")
        self.table.item(row, 2).setText(number(m.integrated))
        self.table.item(row, 4).setText(number(m.true_peak))

    def describe_measurement(self, m):
        encoding=f"{m.bits}-bit" if m.codec.startswith("pcm_") or m.codec=="flac" else (f"{m.bitrate/1000:.0f} kb/s {m.bitrate_mode}" if m.bitrate else "")
        return f"Source: {number(m.integrated)} LUFS · {number(m.true_peak)} dBTP · LRA {number(m.loudness_range)} LU\n{m.sample_rate:,} Hz · {m.channels} channel(s) · {m.codec} · {encoding}"

    def show_details(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.files):
            path = self.files[row]
            self.detail.setPlainText(str(path)+"\n"+self.details.get(str(path), "Ready for analysis."))

    def worker_finished(self):
        worker = self.worker
        outcome = worker.outcome or {}
        self.worker = None
        worker.deleteLater()
        for widget in self.lock_controls:
            widget.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
        self.refresh_processing_controls()
        self.progress.setRange(0, max(1, len(self.files)))
        if "fatal" in outcome:
            self.status.setText("Could not complete the operation")
            QMessageBox.warning(self, "OpenLUFS", outcome["fatal"])
        elif worker.mode == "scan":
            self.append_files(outcome.get("files", []))
            self.status.setText(f"Ready · {len(self.files)} tracks")
        else:
            errors = outcome.get("errors", [])
            cancelled = outcome.get("cancelled", False)
            if worker.mode == "normalize":
                count = len(outcome.get("results", []))
                self.status.setText(f"{'Cancelled' if cancelled else 'Finished'} · {count} exported · {len(errors)} failed")
                self.report = outcome.get("report")
                self.report_button.setEnabled(True)
                self.save_settings()
                if outcome.get("report_error"):
                    QMessageBox.warning(self, "Report could not be saved", outcome["report_error"])
            else:
                self.status.setText(f"{'Cancelled' if cancelled else 'Analysis complete'} · {len(errors)} failed")
        self.update_count()
        if self.closing:
            self.close()

    def cancel(self):
        if self.busy():
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling current operation…")

    def load_settings(self):
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            settings = Settings(target=data["audio"]["target"], ceiling=data["audio"]["ceiling"])
            self.target.setValue(settings.target)
            self.ceiling.setValue(settings.ceiling)
            self.normalize_enabled.setChecked(bool(data["audio"].get("normalize_lufs",True)))
            self.limiter_enabled.setChecked(bool(data.get("limiter_enabled",False)))
            self.preview_style=str(data.get("preview_style","Normal"))
            self.report=data.get("last_report")
            if data.get("window_geometry"):
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromBase64(data["window_geometry"].encode("ascii")))
            self.mirror.setChecked(bool(data.get("mirror", True)))
            self.output.setText(str(data.get("output", "")))
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def save_settings(self):
        from dataclasses import asdict
        if self._loading_settings:
            return
        try:
            data = {"audio": asdict(self.current_settings()),
                    "mirror": self.mirror.isChecked(), "output": self.output.text().strip(),
                    "limiter_enabled": self.limiter_enabled.isChecked(), "preview_style": self.preview_style,
                    "last_report": self.report, "window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii")}
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.config_path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(temp, self.config_path)
        except OSError:
            pass  # A read-only portable folder is supported; preferences stay in memory.

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.busy():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths and not self.busy():
            self.source_root = Path(paths[0]) if len(paths) == 1 and Path(paths[0]).is_dir() and not self.files else None
            self.scan(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy():
            self.closing = True
            self.worker.cancel.set()
            self.status.setText("Stopping audio processing before closing…")
            event.ignore()
        else:
            self.save_settings()
            event.accept()

    def about(self):
        dialog = QDialog(self)
        dialog.setObjectName("AboutDialog")
        dialog.setWindowTitle("About OpenLUFS")
        dialog.setMinimumSize(500, 360)
        available = self.screen().availableGeometry()
        dialog.resize(min(720, available.width()-80), min(700, available.height()-80))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)
        content = QTextBrowser()
        content.setObjectName("AboutContent")
        content.setOpenExternalLinks(True)
        content.setHtml(ABOUT_HTML)
        layout.addWidget(content)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()


def launch():
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenLUFS.Desktop.1")
    app = QApplication(sys.argv)
    app.setApplicationName("OpenLUFS")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if os.name == "nt":
        try:
            import ctypes
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(window.winId()), 20, ctypes.byref(value), ctypes.sizeof(value))
        except (AttributeError, OSError):
            pass
    return app.exec()
