"""Batch — directory of files iterated through run_full."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
)

from video_uniquifier.core.errors import VideoUniquifierError
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.paths import profiles_dir
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.file_picker import PathLabel
from video_uniquifier.gui.widgets.studio_table import StudioTable, TableTools
from video_uniquifier.gui.widgets.surfaces import FieldGrid
from video_uniquifier.gui.workers.batch_worker import BatchWorker

PROFILES_DIR = profiles_dir()


class BatchScreen(ScreenBase):
    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self.input_dir: Path | None = None
        self.output_dir: Path | None = None
        self.worker: BatchWorker | None = None
        self._completed_files: set[str] = set()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = self.page_layout(
            'Batch processing',
            'Process a folder of videos with one profile and track each result.',
        )

        # Input dir
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(self.tr("Input directory:")))
        self.input_label = PathLabel(self.tr("Not selected"))
        self.input_label.setObjectName("path")
        row1.addWidget(self.input_label, stretch=1)
        b1 = QPushButton(self.tr("&Browse…"))
        b1.clicked.connect(self._pick_input)
        mark(b1, "Browse input directory",
             "Pick the directory containing source videos to batch-process.")
        self.input_browse_btn = b1
        row1.addWidget(b1)
        layout.addLayout(row1)

        # Output dir
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(self.tr("Output directory:")))
        self.output_label = PathLabel(self.tr("Not selected"))
        self.output_label.setObjectName("path")
        row2.addWidget(self.output_label, stretch=1)
        b2 = QPushButton(self.tr("Bro&wse…"))
        b2.clicked.connect(self._pick_output)
        mark(b2, "Browse output directory",
             "Pick the destination directory for the uniquified outputs.")
        self.output_browse_btn = b2
        row2.addWidget(b2)
        layout.addLayout(row2)

        # Pattern + profile + encoder + continue-on-error
        row3 = FieldGrid()
        self.pattern_edit = QLineEdit("*.mp4")
        self.pattern_edit.textChanged.connect(self._refresh_preview)
        mark(self.pattern_edit, "Glob pattern",
             "File glob applied inside the input directory.")
        row3.add_field("File pattern", self.pattern_edit)
        self.profile_combo = QComboBox()
        for p in sorted(PROFILES_DIR.glob("*.yaml")):
            self.profile_combo.addItem(p.stem, str(p))
        preferred = self.state.profile_path or PROFILES_DIR / "soft.yaml"
        index = self.profile_combo.findData(str(preferred))
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        mark(self.profile_combo, "Profile",
             "Transform profile applied to every file in the batch.")
        row3.add_field("Profile", self.profile_combo)
        self.encoder_selector = EncoderSelector(self.state)
        row3.add_field("Encoder", self.encoder_selector)
        self.continue_check = QCheckBox(self.tr("&Continue on error"))
        self.continue_check.setChecked(True)
        mark(self.continue_check, "Continue on error",
             "If checked, a failed file logs to Notes and the batch keeps going.")
        row3.add_field("When a file fails", self.continue_check)
        layout.addWidget(row3)

        # Table
        self.table = StudioTable(5, self.state, "batch.header", 1)
        self.table.set_headers(
            ["File", "Status", "Output", "Notes",
             "Actions"],
        )
        self.table.restore_header()
        self.table_tools = TableTools(self.table)
        layout.addWidget(self.table_tools)
        layout.addWidget(self.table, stretch=1)

        # Overall progress bar (X of N files complete; updated on file_done)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("batch_progress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(self.tr("Files: %v / %m (%p%)"))
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Controls
        controls = QHBoxLayout()
        self.run_btn = QPushButton(self.tr("&Run batch"))
        self.run_btn.setObjectName("run")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._on_run)
        mark(self.run_btn, "Run batch",
             "Start the batch encode over every matched file.",
             shortcut="Ctrl+R")
        controls.addWidget(self.run_btn)
        self.run_selected_btn = QPushButton(self.tr("Process selected"))
        self.run_selected_btn.setAccessibleName(self.tr("Process selected"))
        self.run_selected_btn.clicked.connect(self._on_run_selected)
        self.run_selected_btn.setEnabled(False)
        controls.addWidget(self.run_selected_btn)
        self.table.itemSelectionChanged.connect(self._refresh_run_btn)
        self.cancel_btn = QPushButton(self.tr("Cance&l"))
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        mark(self.cancel_btn, "Cancel batch",
             "Stop after the current file finishes.", shortcut="Esc")
        controls.addWidget(self.cancel_btn)
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        controls.addWidget(self.status_label)
        controls.addStretch(1)
        self.add_action_bar(controls)

    def changeEvent(self, event: QEvent | None) -> None:
        if (event is not None and event.type() == QEvent.Type.LanguageChange
                and hasattr(self, "run_selected_btn")):
            self.run_selected_btn.setText(self.tr("Process selected"))
            self.run_selected_btn.setAccessibleName(self.tr("Process selected"))
            self.progress_bar.setFormat(self.tr("Files: %v / %m (%p%)"))
        super().changeEvent(event)

    # ---- handlers ----
    def _pick_input(self) -> None:
        if self.worker is not None:
            return
        d = QFileDialog.getExistingDirectory(self, "Input directory")
        if d:
            self.input_dir = Path(d)
            self.input_label.setText(d)
            self._refresh_preview()
            self._refresh_run_btn()

    def _pick_output(self) -> None:
        if self.worker is not None:
            return
        d = QFileDialog.getExistingDirectory(self, "Output directory")
        if d:
            self.output_dir = Path(d)
            self.output_label.setText(d)
            self._refresh_run_btn()

    def _refresh_preview(self) -> None:
        if self.worker is not None:
            return
        with self.table.updating():
            self._populate_preview()

    def _populate_preview(self) -> None:
        self.table.setRowCount(0)
        if self.input_dir is None:
            return
        for src in sorted(self.input_dir.glob(self.pattern_edit.text() or "*.mp4")):
            if not src.is_file():
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, self.table.file_item(src.name, str(src), str(src)))
            self.table.setItem(r, 1, self.table.status_item("pending"))
            self.table.setItem(r, 2, QTableWidgetItem(""))
            self.table.setItem(r, 3, QTableWidgetItem(""))
            self.table.setCellWidget(r, 4, self.table.row_actions(str(src)))
        count = self.table.rowCount()
        self.status_label.setText(self.tr("{count} files matched").format(count=count))
        self.progress_bar.setRange(0, max(1, count))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(count > 0)

    def _refresh_run_btn(self) -> None:
        ready = (
            self.input_dir is not None
            and self.output_dir is not None
            and self.worker is None
            and self.table.rowCount() > 0
        )
        self.run_btn.setEnabled(ready)
        self.run_selected_btn.setEnabled(ready and bool(self.table.selected_keys()))

    def _on_run_selected(self) -> None:
        files = [Path(key) for key in self.table.selected_keys()]
        if files:
            self._start_batch(files)

    def _on_run(self) -> None:
        self._start_batch([Path(self.table.row_key(row)) for row in range(self.table.rowCount())])

    def _start_batch(self, files: list[Path]) -> None:
        if self.input_dir is None or self.output_dir is None:
            return
        if self.worker is not None or not files:
            return
        try:
            profile = load_profile(Path(self.profile_combo.currentData()))
        except VideoUniquifierError as exc:
            QMessageBox.critical(self, "Profile error", str(exc))
            return

        self._completed_files.clear()
        self.worker = BatchWorker(
            self.input_dir,
            self.output_dir,
            profile,
            self.encoder_selector.currentData(),
            glob_pattern=self.pattern_edit.text() or "*.mp4",
            continue_on_error=self.continue_check.isChecked(),
            files=files,
        )
        self.worker.file_started.connect(
            lambda p: self._set_status(p, "running"),
        )
        self.worker.file_done.connect(
            lambda p, out: self._set_status(p, "done", out=out),
        )
        self.worker.file_failed.connect(
            lambda p, msg: self._set_status(p, "failed", note=msg),
        )
        self.worker.progress.connect(
            lambda _f, m: self.status_label.setText(m),
        )
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)

        self.run_btn.setEnabled(False)
        self.run_selected_btn.setEnabled(False)
        self._set_inputs_enabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("starting…")
        # Reset overall progress: max = number of files matched in the table.
        self.progress_bar.show()
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)
        self.worker.start()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        for control in (self.pattern_edit, self.input_browse_btn, self.output_browse_btn,
                        self.profile_combo, self.encoder_selector, self.continue_check):
            control.setEnabled(enabled)

    def _on_cancel(self) -> None:
        if self.worker is not None:
            self.worker.request_cancel()
            self.status_label.setText("cancelling…")

    def _on_done(self, _payload: object) -> None:
        self.status_label.setText("Done.")
        self._drop_worker()
        self.cancel_btn.setEnabled(False)
        self._set_inputs_enabled(True)
        self._refresh_run_btn()

    def _on_failed(self, msg: str) -> None:
        self.status_label.setText(f"FAILED: {msg}")
        self._drop_worker()
        self.cancel_btn.setEnabled(False)
        self._set_inputs_enabled(True)
        self._refresh_run_btn()

    def _drop_worker(self) -> None:
        """Join the BatchWorker QThread before dropping the Python ref.

        Qt delivers finished_ok / failed via QueuedConnection while the
        thread's run() may still be unwinding. Setting ``self.worker = None``
        without first quit()+wait() can leave a live C++ QThread behind
        the dropped Python reference, causing a "QThread: Destroyed
        while thread is still running" abort.
        """
        if self.worker is None:
            return
        self.worker.quit()
        self.worker.wait(1000)
        self.worker = None

    def _set_status(
        self, path: str, status: str, *, out: str = "", note: str = "",
    ) -> None:
        row = self.table.find_key(path)
        if row is None:
            return
        with self.table.updating():
            self.table.setItem(row, 1, self.table.status_item(status))
            if out:
                self.table.setItem(row, 2, self.table.path_item(out))
                self.table.setCellWidget(row, 4, self.table.row_actions(out))
            if note:
                self.table.setItem(row, 3, self.table.path_item(note))
        # Each transition to a terminal status advances the overall bar.
        if status in {"done", "failed"} and path not in self._completed_files:
            self._completed_files.add(path)
            self.progress_bar.setValue(self.progress_bar.value() + 1)
