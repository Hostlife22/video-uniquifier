"""Single-file Run screen. Replaces the entire v0.4 GUI flow."""

from __future__ import annotations

import contextlib
import json
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.core.errors import VideoUniquifierError
from video_uniquifier.core.models import Plan, SourceMeta
from video_uniquifier.core.orchestrator import RunOptions, build_plan
from video_uniquifier.core.preflight import has_fail
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.paths import profiles_dir
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.divergence_indicator import DivergenceIndicator
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.file_picker import FilePickerRow
from video_uniquifier.gui.widgets.kpi_pills import KpiPills
from video_uniquifier.gui.widgets.log_console import LogConsole
from video_uniquifier.gui.widgets.preflight_panel import PreflightPanel
from video_uniquifier.gui.widgets.processing_status import STAGE_LABELS, ProcessingStatus
from video_uniquifier.gui.widgets.profile_cards import ProfileCards
from video_uniquifier.gui.widgets.sample_timeline import SampleTimeline, TimecodeSpinBox
from video_uniquifier.gui.widgets.segment_timeline import SegmentTimeline
from video_uniquifier.gui.widgets.surfaces import Disclosure, SectionCard
from video_uniquifier.gui.workers.preflight_worker import PreflightWorker
from video_uniquifier.gui.workers.probe_worker import ProbeWorker
from video_uniquifier.gui.workers.review_assets_worker import SaveSampleWorker, ThumbnailWorker
from video_uniquifier.gui.workers.run_worker import RunWorker
from video_uniquifier.gui.workers.sample_worker import SampleWorker

PROFILES_DIR = profiles_dir()


@dataclass(frozen=True)
class PlanCacheEntry:
    """Cached Plan keyed by the inputs that produced it.

    Replaces a positional 4-tuple. Named fields make the cache hit/miss
    check at _on_run readable and robust to future field additions
    (e.g. a workers override) without index shifts.
    """

    input_path: Path
    profile_path: Path
    encoder: str | None
    plan: Plan

    def matches(
        self,
        input_path: Path,
        profile_path: Path,
        encoder: str | None,
    ) -> bool:
        return (
            self.input_path == input_path
            and self.profile_path == profile_path
            and self.encoder == encoder
        )


class RunScreen(ScreenBase):
    """Single-file uniquification: probe → preflight → run → QA."""

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        # Forward-declare optional CalibrateWorker so type-checkers see
        # the right `T | None` shape from the first assignment. Imported
        # locally because it pulls Qt + calibration deps that the
        # PreflightWorker tests stub at module load time.
        from video_uniquifier.gui.workers.calibrate_worker import CalibrateWorker
        self.run_worker: RunWorker | None = None
        self.probe_worker: ProbeWorker | None = None
        self.preflight_worker: PreflightWorker | None = None
        self._tune_worker: CalibrateWorker | None = None
        self._tune_source_path: Path | None = None
        self.qa_html_path: Path | None = None
        # Cached Plan from the most recent preflight, keyed by
        # (input_path, profile_path, encoder). Lets _on_run reuse the
        # Plan that _on_preflight already produced when the user clicked
        # Preflight first — avoids a redundant probe and prevents the
        # two paths from diverging.
        self._plan_cache: PlanCacheEntry | None = None
        self._preflight_blocked = False
        self._completed_output_path: Path | None = None
        self._suggested_output: Path | None = None
        self._source_meta: SourceMeta | None = None
        self._sample_worker: SampleWorker | None = None
        self._sample_directory: TemporaryDirectory[str] | None = None
        self._sample_mode = False
        self._review_source: Path | None = None
        self._review_pair: tuple[Path, Path] | None = None
        self._compare_dialog: QWidget | None = None
        self._shutting_down = False
        self._thumbnail_worker: ThumbnailWorker | None = None
        self._thumbnail_pending: SourceMeta | None = None
        self._save_worker: SaveSampleWorker | None = None
        self._sample_input_path: Path | None = None
        self._build_ui()
        self._result_reveal_timer = QTimer(self)
        self._result_reveal_timer.setSingleShot(True)
        self._result_reveal_timer.timeout.connect(self._reveal_result)
        self._refresh_run_button()

    def _reveal_result(self) -> None:
        content = self.page_scroll.widget()
        layout = content.layout() if content is not None else None
        if layout is not None:
            layout.activate()
        self.page_scroll.ensureWidgetVisible(self.result_actions)
        if self._sample_mode and self._review_pair is not None:
            self._open_comparison()

    def _build_ui(self) -> None:
        layout = self.page_layout(
            "Process video",
            "Choose a video, adjust processing and save the result.",
        )

        source = SectionCard("01  Source & destination")
        files = QHBoxLayout()
        files.setSpacing(Space.LG)
        self.input_picker = FilePickerRow(
            "Input video", "input", "Video (*.mp4 *.mov *.mkv *.webm);;All (*)", self.state,
        )
        self.input_picker.path_changed.connect(self._on_input_changed)
        files.addWidget(self.input_picker, stretch=1)
        self.output_picker = FilePickerRow("Save result to", "output", "MP4 (*.mp4)", self.state)
        self.output_picker.path_changed.connect(self._on_output_changed)
        files.addWidget(self.output_picker, stretch=1)
        source.body.addLayout(files)
        self.source_metadata = QLabel(self.tr("Choose a source video to see its details."))
        self.source_metadata.setObjectName("source_metadata")
        self.source_metadata.setWordWrap(True)
        details = QHBoxLayout()
        self.source_thumbnail = QLabel(self.tr("Video preview"))
        self.source_thumbnail.setObjectName("hint")
        self.source_thumbnail.setFixedSize(Metrics.SOURCE_THUMB_WIDTH, Metrics.SOURCE_THUMB_HEIGHT)
        self.source_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_thumbnail.setAccessibleName(self.tr("Source video thumbnail"))
        details.addWidget(self.source_thumbnail)
        details.addWidget(self.source_metadata, stretch=1)
        self.preview_source_btn = QPushButton(self.tr("Preview original"))
        self.preview_source_btn.clicked.connect(self._preview_original)
        mark(self.preview_source_btn, "Preview original", "View the source without processing it.")
        details.addWidget(self.preview_source_btn)
        source.body.addLayout(details)
        layout.addWidget(source)

        processing = SectionCard("02  Processing")
        self.profile_cards = ProfileCards()
        self.profile_cards.selected.connect(self._select_profile_card)
        processing.body.addWidget(self.profile_cards)
        row = QHBoxLayout()
        self.profile_label = QLabel(self.tr("Profile"))
        self.profile_label.setObjectName("field_label")
        row.addWidget(self.profile_label)
        self.profile_combo = QComboBox()
        for p in sorted(PROFILES_DIR.glob("*.yaml")):
            self.profile_combo.addItem(p.stem, str(p))
        saved = self.state.profile_path
        preferred = str(saved) if saved is not None else str(PROFILES_DIR / "soft.yaml")
        idx = self.profile_combo.findData(preferred)
        if idx < 0:
            idx = self.profile_combo.findText("soft")
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        mark(self.profile_combo, "Profile", "Choose how strongly the video is transformed.")
        row.addWidget(self.profile_combo, stretch=1)
        processing.body.addLayout(row)
        self.profile_hint = QLabel()
        self.profile_hint.setObjectName("hint")
        self.profile_hint.setWordWrap(True)
        processing.body.addWidget(self.profile_hint)

        self.advanced = Disclosure(
            "Advanced settings", "Expand encoder selection, profile editing and auto-tuning.",
        )
        encoder_row = QHBoxLayout()
        self.encoder_label = QLabel(self.tr("Encoder"))
        encoder_row.addWidget(self.encoder_label)
        self.encoder_selector = EncoderSelector(self.state)
        self.encoder_selector.encoder_changed.connect(self.state.set_encoder_name)
        self.encoder_selector.encoder_changed.connect(self._on_encoder_changed)
        encoder_row.addWidget(self.encoder_selector, stretch=1)
        self.advanced.body.addLayout(encoder_row)
        advanced_actions = QHBoxLayout()
        self.edit_profile_btn = QPushButton(self.tr("Edit profile…"))
        self.edit_profile_btn.clicked.connect(self._open_profile_editor)
        mark(self.edit_profile_btn, "Edit profile", "Open the selected profile in the editor.")
        advanced_actions.addWidget(self.edit_profile_btn)
        self.auto_tune_btn = QPushButton(self.tr("Auto-tune for this source"))
        self.auto_tune_btn.clicked.connect(self._on_auto_tune)
        mark(
            self.auto_tune_btn, "Auto-tune profile",
            "Calibrate this profile against the selected video and save a tuned copy.",
            shortcut="Ctrl+T",
        )
        advanced_actions.addWidget(self.auto_tune_btn)
        advanced_actions.addStretch(1)
        self.advanced.body.addLayout(advanced_actions)
        processing.body.addWidget(self.advanced)
        self.sample_controls = Disclosure(
            "Test a short fragment", "Compare a processed sample before starting the full video.",
        )
        sample_options = QHBoxLayout()
        self.sample_start_label = QLabel(self.tr("Start time"))
        sample_options.addWidget(self.sample_start_label)
        self.sample_start = TimecodeSpinBox()
        self.sample_start.setDecimals(2)
        self.sample_start.setRange(0, 0)
        mark(self.sample_start, "Sample start", "Choose where the review sample starts.")
        sample_options.addWidget(self.sample_start)
        self.sample_length = QComboBox()
        for seconds in (10, 15, 20):
            self.sample_length.addItem(self.tr("{seconds} s").format(seconds=seconds), seconds)
        self.sample_length.setCurrentIndex(1)
        mark(self.sample_length, "Sample length", "Choose a 10, 15 or 20 second sample.")
        sample_options.addWidget(self.sample_length)
        self.sample_btn = QPushButton(self.tr("Process sample"))
        self.sample_btn.clicked.connect(self._on_sample)
        mark(self.sample_btn, "Process sample",
             "Process only the selected fragment and compare it.")
        sample_options.addWidget(self.sample_btn)
        self.sample_controls.body.addLayout(sample_options)
        self.sample_timeline = SampleTimeline(self.state)
        self.sample_controls.body.addWidget(self.sample_timeline)
        self.sample_timeline.valueChanged.connect(
            lambda value: self.sample_start.setValue(value / 1000),
        )
        self.sample_start.valueChanged.connect(self._sample_selection_changed)
        self.sample_length.currentIndexChanged.connect(self._sample_selection_changed)
        self.sample_hint = QLabel(self.tr(
            "Uses the selected profile. The full output destination stays unchanged.",
        ))
        self.sample_hint.setObjectName("hint")
        self.sample_hint.setWordWrap(True)
        self.sample_controls.body.addWidget(self.sample_hint)
        processing.body.addWidget(self.sample_controls)
        layout.addWidget(processing)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self._update_profile_hint()

        self.preflight_panel = PreflightPanel(self.state)
        self.preflight_panel.has_fail.connect(self._on_has_fail)
        layout.addWidget(self.preflight_panel)

        result = SectionCard("03  Progress & result")
        status_row = QHBoxLayout()
        self.status_label = QLabel(self.tr("Your result will appear here after processing."))
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, stretch=1)
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("hint")
        status_row.addWidget(self.progress_label)
        result.body.addLayout(status_row)
        self.processing_status = ProcessingStatus(self.state)
        result.body.addWidget(self.processing_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("main_progress")
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setAccessibleName(self.tr("Video processing progress"))
        result.body.addWidget(self.progress_bar)
        self.audio_progress_bar = QProgressBar()
        self.audio_progress_bar.setObjectName("audio_progress")
        self.audio_progress_bar.setRange(0, 1000)
        self.audio_progress_bar.setFormat("Audio: %p%")
        self.audio_progress_bar.setTextVisible(False)
        self.audio_progress_bar.setFixedHeight(10)
        self.audio_progress_bar.setAccessibleName(self.tr("Audio processing progress"))
        self.audio_progress_bar.setVisible(False)
        result.body.addWidget(self.audio_progress_bar)
        self.timeline = SegmentTimeline(self.state)
        self.timeline.setVisible(False)
        result.body.addWidget(self.timeline)
        self.divergence_indicator = DivergenceIndicator(self.state)
        result.body.addWidget(self.divergence_indicator)
        self.kpi_pills = KpiPills(self.state)
        self.metrics_details = Disclosure(
            "Measured metrics", "Expand quality and similarity values.",
        )
        self.metrics_details.body.addWidget(self.kpi_pills)
        self.result_actions = QWidget()
        actions_column = QVBoxLayout(self.result_actions)
        actions_column.setContentsMargins(0, 0, 0, 0)
        result_actions = QHBoxLayout()
        actions_column.addLayout(result_actions)
        self.open_output_btn = QPushButton(self.tr("Open processed video"))
        self.open_output_btn.clicked.connect(self._on_open_output)
        mark(self.open_output_btn, "Open processed video", "Play the last completed output.")
        result_actions.addWidget(self.open_output_btn)
        self.open_qa_btn = QPushButton(self.tr("Open quality report"))
        self.open_qa_btn.setEnabled(False)
        self.open_qa_btn.clicked.connect(self._on_open_qa)
        mark(self.open_qa_btn, "Open QA report", "Open the report from the last completed run.",
             shortcut="Ctrl+Q")
        result_actions.addWidget(self.open_qa_btn)
        result_actions.addStretch(1)
        comparison_actions = QHBoxLayout()
        actions_column.addLayout(comparison_actions)
        self.compare_btn = QPushButton(self.tr("Compare before / after"))
        self.compare_btn.clicked.connect(self._open_comparison)
        mark(self.compare_btn, "Compare before / after", "Inspect the completed source and result.")
        comparison_actions.addWidget(self.compare_btn)
        self.save_sample_btn = QPushButton(self.tr("Save sample…"))
        mark(self.save_sample_btn, self.tr("Save sample"))
        self.save_sample_btn.clicked.connect(self._save_sample)
        self.save_sample_btn.hide()
        comparison_actions.addWidget(self.save_sample_btn)
        comparison_actions.addStretch(1)
        result.body.addWidget(self.result_actions)
        self.result_actions.hide()
        result.body.addWidget(self.metrics_details)
        self.metrics_details.hide()
        layout.addWidget(result)

        self.log_details = Disclosure("Activity log", "Expand detailed processing messages.")
        self.log = LogConsole(state=self.state)
        self.log.setFixedHeight(Metrics.LOG_HEIGHT)
        self.log.error_logged.connect(lambda _message: self.log_details.set_expanded(True))
        self.log_details.body.addWidget(self.log)
        layout.addWidget(self.log_details)
        layout.addStretch(1)

        # Keep the primary action visible even while the page is scrolled.
        action_bar = QWidget()
        action_bar.setObjectName("action_bar")
        controls = QHBoxLayout(action_bar)
        controls.setContentsMargins(Space.PAGE, Space.MD, Space.PAGE, Space.MD)
        controls.setSpacing(Space.SM)
        self.readiness_hint = QLabel()
        self.readiness_hint.setObjectName("hint")
        self.readiness_hint.setWordWrap(True)
        controls.addWidget(self.readiness_hint, stretch=1)
        self.preflight_btn = QPushButton(self.tr("Check video"))
        self.preflight_btn.clicked.connect(self._on_preflight)
        mark(self.preflight_btn, "Run preflight", "Check the source and encoder before processing.",
             shortcut="Ctrl+P")
        controls.addWidget(self.preflight_btn)
        self.pause_btn = QPushButton(self.tr("&Pause"))
        self.pause_btn.setObjectName("pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause_toggle)
        mark(self.pause_btn, "Pause run", "Pause or resume the current encode.", shortcut="Space")
        controls.addWidget(self.pause_btn)
        self.pause_btn.hide()
        self.cancel_btn = QPushButton(self.tr("&Cancel"))
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        mark(self.cancel_btn, "Cancel run", "Stop the current encode.", shortcut="Esc")
        controls.addWidget(self.cancel_btn)
        self.cancel_btn.hide()
        self.run_btn = QPushButton(self.tr("Start processing"))
        self.run_btn.setObjectName("run")
        self.run_btn.clicked.connect(self._on_run)
        mark(self.run_btn, "Run", "Process the selected video.", shortcut="Ctrl+R")
        controls.addWidget(self.run_btn)
        self.outer_layout.addWidget(action_bar)

    def _update_profile_hint(self) -> None:
        hints = {
            "soft": "Soft · Subtle changes. A good starting point for reviewing quality.",
            "medium": "Medium · More visible changes. Compare a short clip before a full run.",
            "aggressive": "Strong · Pronounced changes that may reduce picture quality.",
        }
        data = self.profile_combo.currentData()
        path = Path(str(data)) if data else None
        stem = (path.stem if path is not None and path.parent.resolve() == PROFILES_DIR.resolve()
                else "")
        self.profile_cards.set_selected(stem)
        self.profile_hint.setText(self.tr(hints.get(
            stem, "Custom profile · Review its settings in the profile editor.",
        )))

    def _select_profile_card(self, preset: str) -> None:
        index = self.profile_combo.findData(str(PROFILES_DIR / f"{preset}.yaml"))
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self._update_profile_hint()

    def _sample_selection_changed(self, _value: object = None) -> None:
        block = self.sample_timeline.blockSignals(True)
        self.sample_timeline.setValue(round(self.sample_start.value() * 1000))
        self.sample_timeline.blockSignals(block)
        self.sample_timeline.length_sec = float(self.sample_length.currentData() or 15)
        self.sample_timeline.update()

    def _select_sample_time(self, source: Path, seconds: float) -> None:
        if source != self.state.input_path or not self.sample_start.isEnabled():
            return
        self.sample_start.setValue(seconds)
        self.sample_controls.set_expanded(True)
        self.page_scroll.ensureWidgetVisible(self.sample_start)

    def _start_thumbnails(self, meta: SourceMeta) -> None:
        if not meta.path.is_file() or self._shutting_down:
            return
        if self._thumbnail_worker is not None:
            self._thumbnail_worker.request_cancel()
            self._thumbnail_pending = meta
            return
        self._thumbnail_worker = ThumbnailWorker(meta.path, meta.duration_sec)
        self._thumbnail_worker.thumbnail.connect(self._on_thumbnail)
        self._thumbnail_worker.failed.connect(self._thumbnail_failed)
        self._thumbnail_worker.finished.connect(self._thumbnails_finished)
        self._thumbnail_worker.start()

    def _thumbnail_failed(self, message: str) -> None:
        if not self._shutting_down:
            self.log.log(f"Thumbnails: {message}", "info")

    def _on_thumbnail(self, source: object, stamp: float, png: bytes) -> None:
        if source != self.state.input_path or self._shutting_down:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(png, "PNG"):
            return
        self.sample_timeline.add_frame(stamp, pixmap)
        if stamp == 0:
            self.source_thumbnail.setPixmap(pixmap.scaled(
                self.source_thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def _thumbnails_finished(self) -> None:
        if self._thumbnail_worker is not None:
            self._thumbnail_worker.wait()
            self._thumbnail_worker = None
        pending, self._thumbnail_pending = self._thumbnail_pending, None
        if pending is not None and pending.path == self.state.input_path:
            self._start_thumbnails(pending)

    def _save_sample(self) -> None:
        if (not self._sample_mode or self._review_pair is None
                or self._save_worker is not None or self.run_worker is not None
                or self._sample_worker is not None or self._tune_worker is not None):
            return
        original = self._sample_input_path
        suggestion = (original.with_name(f"{original.stem}.sample.mp4")
                      if original is not None else Path("sample.mp4"))
        filename, _filter = QFileDialog.getSaveFileName(
            self, self.tr("Save sample"), str(suggestion), "MP4 (*.mp4)",
        )
        if not filename:
            return
        destination = Path(filename)
        if not destination.suffix:
            destination = destination.with_suffix(".mp4")
        protected = (self._review_pair[0],) + ((original,) if original is not None else ())
        self._save_worker = SaveSampleWorker(self._review_pair[1], destination, protected)
        self._save_worker.finished_ok.connect(self._sample_saved)
        self._save_worker.failed.connect(self._sample_save_failed)
        self._save_worker.cancelled.connect(self._sample_save_cancelled)
        self._save_worker.progress.connect(self._sample_save_progress)
        self.status_label.setText(self.tr("Saving sample…"))
        self._save_worker.start()
        self._refresh_run_button()

    def _sample_save_progress(self, fraction: float, _label: str) -> None:
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(round(fraction * 1000))
        self.progress_label.setText(f"{fraction:.0%}")

    def _release_save_worker(self) -> None:
        if self._save_worker is not None:
            self._save_worker.wait()
            self._save_worker = None

    def _sample_saved(self, destination: object) -> None:
        self._release_save_worker()
        if isinstance(destination, Path):
            self.status_label.setText(self.tr("Sample saved: {file}").format(file=destination.name))
            self.status_label.setToolTip(str(destination))
        self._refresh_run_button()

    def _sample_save_failed(self, message: str) -> None:
        self._release_save_worker()
        self.log.log(message, "error")
        self.status_label.setText(self.tr("Could not save sample. Try another destination."))
        self._refresh_run_button()

    def _sample_save_cancelled(self) -> None:
        self._release_save_worker()
        self.status_label.setText(self.tr(
            "Saving cancelled; the temporary sample is still available.",
        ))
        self._refresh_run_button()

    def _on_profile_changed(self, _index: int) -> None:
        data = self.profile_combo.currentData()
        self.state.set_profile_path(Path(str(data)) if data else None)
        self._invalidate_preflight()
        self._update_profile_hint()
        self._refresh_run_button()

    def _on_encoder_changed(self, _encoder: object) -> None:
        self._invalidate_preflight()
        self._refresh_run_button()

    def _invalidate_preflight(self) -> None:
        self._plan_cache = None
        self._preflight_blocked = False
        self.preflight_panel.set_findings([])

    def _open_profile_editor(self) -> None:
        data = self.profile_combo.currentData()
        if data:
            self.state.set_profile_path(Path(str(data)))
            self.navigate_requested.emit("Profile Editor")

    def _on_open_output(self) -> None:
        if self._completed_output_path is not None and self._completed_output_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._completed_output_path.resolve())))

    # ---- event handlers ----
    def _on_input_changed(self, path: object) -> None:
        if path is not None and not isinstance(path, Path):
            return
        self.state.set_input_path(path)
        self._source_meta = None
        self.source_thumbnail.clear()
        self.source_thumbnail.setText(self.tr("Video preview"))
        self.sample_timeline.reset()
        self._thumbnail_pending = None
        if self._thumbnail_worker is not None:
            self._thumbnail_worker.request_cancel()
        self.sample_start.setRange(0, 0)
        self._invalidate_preflight()
        if path is not None and (
            self.state.output_path is None or self.state.output_path == self._suggested_output
        ):
            candidate = path.with_name(f"{path.stem}.processed.mp4")
            suffix = 2
            while candidate.exists():
                candidate = path.with_name(f"{path.stem}.processed-{suffix}.mp4")
                suffix += 1
            self._suggested_output = candidate
            self.output_picker.set_path(candidate)
        self._refresh_run_button()
        if path is None:
            self.source_metadata.setText(self.tr("Choose a source video to see its details."))
            return
        self.source_metadata.setText(self.tr("Reading video details…"))
        # Auto-probe
        self._drop_probe_worker()
        self.probe_worker = ProbeWorker(path)
        self.probe_worker.probed.connect(self._on_probed)
        self.probe_worker.failed.connect(self._on_probe_failed)
        self.probe_worker.start()

    def _on_output_changed(self, path: object) -> None:
        if path is not None and not isinstance(path, Path):
            return
        self.state.set_output_path(path)
        self._refresh_run_button()

    def _on_probe_failed(self, message: str) -> None:
        self.source_metadata.setText(self.tr("Could not read this video. See the activity log."))
        self.log.log(f"probe: {message}", "error")
        self._drop_probe_worker()

    def _on_probed(self, meta: object) -> None:
        if not isinstance(meta, SourceMeta):
            return
        if meta.path != self.state.input_path:
            return
        if not meta.video:
            self.log.log("probe: no video stream", "error")
            return
        v = meta.video[0]
        self._source_meta = meta
        self.sample_start.setMaximum(max(0, meta.duration_sec - 0.1))
        self.sample_timeline.setRange(0, max(0, round(meta.duration_sec * 1000)))
        self._start_thumbnails(meta)
        self._refresh_run_button()
        minutes, seconds = divmod(int(meta.duration_sec), 60)
        dynamic_range = "HDR" if v.color.is_hdr else "SDR"
        self.source_metadata.setText(
            f"{v.width} × {v.height}  ·  {v.fps:.2f} fps  ·  "
            f"{minutes}:{seconds:02d}  ·  {dynamic_range}  ·  {v.codec.upper()}",
        )
        self.log.log(
            f"probed: {v.codec} {v.width}×{v.height} @ {v.fps:.2f}fps · "
            f"{meta.duration_sec:.1f}s · HDR={v.color.is_hdr}",
            "info",
        )
        # Probe done — release the worker so the QThread doesn't sit
        # idle in Python's ref graph until the next input change.
        self._drop_probe_worker()

    def _drop_probe_worker(self) -> None:
        if self.probe_worker is None:
            return
        self.probe_worker.quit()
        self.probe_worker.wait(500)
        self.probe_worker = None

    def _on_preflight(self) -> None:
        if self.state.input_path is None:
            return
        if self.preflight_worker is not None:
            return  # already running
        profile_path = Path(self.profile_combo.currentData())
        enc_override = self.encoder_selector.currentData()
        self.preflight_btn.setEnabled(False)
        self.log.log("preflight: probing source + checking encoder…", "info")
        self.preflight_worker = PreflightWorker(
            self.state.input_path, profile_path, enc_override,
        )
        # Capture (input, profile_path, enc_override) for the plan-ready
        # slot so it can build the cache key even if the user has
        # tweaked the UI selectors while preflight ran.
        cache_key = (self.state.input_path, profile_path, enc_override)
        self.preflight_worker.plan_ready.connect(
            lambda plan, findings: self._on_preflight_ready(plan, findings, cache_key),
        )
        self.preflight_worker.failed.connect(self._on_preflight_failed)
        self.preflight_worker.start()
        self._refresh_run_button()

    def _on_preflight_ready(
        self,
        plan: object,
        findings: object,
        cache_key: tuple[Path, Path, str | None],
    ) -> None:
        if not isinstance(plan, Plan) or not isinstance(findings, list):
            self._drop_preflight_worker()
            self.preflight_btn.setEnabled(True)
            return
        current_key = (
            self.state.input_path, Path(str(self.profile_combo.currentData())),
            self.encoder_selector.currentData(),
        )
        if current_key != cache_key:
            self._drop_preflight_worker()
            self._refresh_run_button()
            return
        self.preflight_panel.set_findings(findings)
        input_path, profile_path, encoder = cache_key
        self._plan_cache = PlanCacheEntry(
            input_path=input_path,
            profile_path=profile_path,
            encoder=encoder,
            plan=plan,
        )
        self.log.log(
            f"preflight: {len(findings)} finding(s), "
            f"{'FAIL' if has_fail(findings) else 'PASS'}",
            "info",
        )
        self._drop_preflight_worker()
        self.preflight_btn.setEnabled(True)
        self._refresh_run_button()

    def _on_preflight_failed(self, msg: str) -> None:
        self.log.log(f"preflight: {msg}", "error")
        QMessageBox.critical(self, "Plan error", msg)
        self._drop_preflight_worker()
        self.preflight_btn.setEnabled(True)
        self._refresh_run_button()

    def _drop_preflight_worker(self) -> None:
        if self.preflight_worker is None:
            return
        self.preflight_worker.quit()
        self.preflight_worker.wait(500)
        self.preflight_worker = None

    def _on_has_fail(self, has_fail_now: bool) -> None:
        self._preflight_blocked = has_fail_now
        self._refresh_run_button(preflight_fail=has_fail_now)

    def _on_run(self) -> None:
        if self.state.input_path is None or self.state.output_path is None:
            return
        if (self.run_worker is not None or self._sample_worker is not None
                or self._tune_worker is not None or self._save_worker is not None
                or self.preflight_worker is not None or self._preflight_blocked
                or self.profile_combo.currentData() is None
                or self.state.input_path.resolve() == self.state.output_path.resolve()):
            self._refresh_run_button()
            return
        try:
            profile_path = Path(self.profile_combo.currentData())
            enc_override = self.encoder_selector.currentData()
            # Reuse the Plan that Preflight already built when the
            # user's selections have not changed — avoids re-probing
            # the source and guarantees the two paths see the same
            # encoder, plan_hash, and findings.
            if self._plan_cache is not None and self._plan_cache.matches(
                self.state.input_path, profile_path, enc_override,
            ):
                plan = self._plan_cache.plan
            else:
                profile = load_profile(profile_path)
                plan = build_plan(
                    self.state.input_path, profile, enc_override,
                )
        except VideoUniquifierError as exc:
            QMessageBox.critical(self, "Plan error", str(exc))
            return

        work_dir = Path.home() / ".cache" / "video_uniquifier" / "work" / plan.plan_hash
        # v0.7 R5: pull NotificationConfig from AppState (set via Settings).
        # AppState.notifications is annotated as `object` to keep the module
        # importable without core.notifications; narrow via isinstance before
        # forwarding so a corrupt-on-disk value can't poison RunOptions.
        from video_uniquifier.core.notifications import NotificationConfig
        raw_notif = self.state.notifications
        notif_cfg = raw_notif if isinstance(raw_notif, NotificationConfig) else None
        options = RunOptions(
            work_dir=work_dir,
            output=self.state.output_path,
            keep_segments=False,
            enforce_preflight=True,
            notifications=notif_cfg,
        )
        self._sample_mode = False
        self.processing_status.start()
        self._start_run(plan, options)

    def _start_run(self, plan: Plan, options: RunOptions) -> None:
        self._review_source = plan.source.path
        self._review_pair = None

        # If a previous worker is still being torn down, disconnect its
        # signals before dropping the reference. Otherwise the C++ side
        # may continue to deliver into now-dangling Python slots when
        # the screen is rebuilt.
        if self.run_worker is not None:
            # `QObject.disconnect()` with no args removes every signal
            # connection on this object. The PyQt6 typeshed dropped the
            # `disconnect(receiver)` overload; the no-arg form is the
            # supported way to detach all slots before dropping the
            # Python reference.
            with contextlib.suppress(TypeError, RuntimeError):
                self.run_worker.disconnect()

        self.run_worker = RunWorker(
            plan, options, run_qa=True, fast_qa=False,
            state=None if self._sample_mode else self.state,
        )
        self.run_worker.progress.connect(self._on_progress)
        self.run_worker.audio_progress.connect(self._on_audio_progress)
        self.run_worker.stage_progress.connect(self._on_stage_progress)
        self.run_worker.log.connect(lambda m: self.log.log(m, "log"))
        self.run_worker.segment_progress.connect(
            lambda idx, status: self.timeline.update_segment(idx, status),
        )
        self.run_worker.divergence_sample.connect(
            self.divergence_indicator.push_sample,
        )
        self.run_worker.finished_ok.connect(self._on_done)
        self.run_worker.failed.connect(self._on_failed)
        self.run_worker.cancelled.connect(self._on_cancelled)
        # v0.7 R6 / F5 — pause button label & state machine.
        self.run_worker.paused_changed.connect(self._on_paused_changed)

        # Initialise timeline with rough segment estimate.
        n_segments = max(1, int(plan.source.duration_sec / options.target_segment_sec))
        self.timeline.init(n_segments + 1)

        self.qa_html_path = None
        self._completed_output_path = None
        self.result_actions.hide()
        self.metrics_details.hide()
        self.open_qa_btn.setEnabled(False)
        self.kpi_pills.clear()
        self.divergence_indicator.reset()
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.timeline.show()
        self.audio_progress_bar.setValue(0)
        self.audio_progress_bar.setVisible(False)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText(self.tr("&Pause"))
        self.status_label.setText(
            f"Running on {plan.encoder.name} ({plan.encoder.vendor})…",
        )
        self.log.log(f"--- Run started: plan_hash={plan.plan_hash} ---", "info")
        self.run_worker.start()
        self._refresh_run_button()

    def _preview_original(self) -> None:
        path = self.state.input_path
        if path is not None and path.is_file():
            self._show_comparison(path, None)

    def _show_comparison(self, source: Path, candidate: Path | None) -> None:
        from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
        if self._compare_dialog is not None:
            if not self._compare_dialog.close():
                return
            self._compare_dialog.deleteLater()
        dialog = VideoCompareDialog(source, candidate, parent=self)
        dialog.wipe.set_theme(self.state.theme)
        self.state.theme_changed.connect(dialog.wipe.set_theme)
        dialog.sample_selected.connect(lambda seconds: self._select_sample_time(source, seconds))
        self._compare_dialog = dialog
        dialog.show()

    def _open_comparison(self) -> None:
        if self._review_pair is not None:
            source, candidate = self._review_pair
            if source.is_file() and candidate.is_file():
                self._show_comparison(source, candidate)

    def _on_sample(self) -> None:
        if (self._source_meta is None or self.state.input_path is None
                or self._source_meta.path != self.state.input_path
                or self._source_meta.duration_sec <= 0
                or self.run_worker is not None or self._sample_worker is not None
                or self._tune_worker is not None or self.preflight_worker is not None
                or self._save_worker is not None
                or self._preflight_blocked or self.profile_combo.currentData() is None):
            return
        if self._compare_dialog is not None:
            if not self._compare_dialog.close():
                return
            self._compare_dialog.deleteLater()
            self._compare_dialog = None
        if self._sample_directory is not None:
            self._sample_directory.cleanup()
        self._sample_directory = TemporaryDirectory(
            prefix="video-uniquifier-review-", ignore_cleanup_errors=True,
        )
        self._sample_mode = True
        self._sample_input_path = self.state.input_path
        self._review_pair = None
        self._completed_output_path = None
        self.result_actions.hide()
        self.metrics_details.hide()
        length = min(
            float(self.sample_length.currentData()),
            self._source_meta.duration_sec - self.sample_start.value(),
        )
        self._sample_worker = SampleWorker(
            self.state.input_path, Path(self.profile_combo.currentData()),
            Path(self._sample_directory.name), self.sample_start.value(), length,
            self.encoder_selector.currentData(),
        )
        self._sample_worker.stage_progress.connect(self._on_stage_progress)
        self._sample_worker.finished_ok.connect(self._on_sample_prepared)
        self._sample_worker.failed.connect(self._on_sample_failed)
        self._sample_worker.cancelled.connect(self._on_sample_cancelled)
        self.processing_status.start()
        self._on_stage_progress("prepare", None)
        self._sample_worker.start()
        self._refresh_run_button()

    def _release_sample_worker(self) -> None:
        if self._sample_worker is not None:
            self._sample_worker.wait()
            self._sample_worker = None

    def _on_sample_prepared(self, plan: object) -> None:
        self._release_sample_worker()
        if self._shutting_down:
            return
        if not isinstance(plan, Plan) or self._sample_directory is None:
            self._on_failed(self.tr("Could not prepare the selected sample."))
            return
        directory = Path(self._sample_directory.name)
        options = RunOptions(
            work_dir=directory / "work", output=directory / "processed.mp4",
            keep_segments=False, enforce_preflight=True,
        )
        self._start_run(plan, options)

    def _on_sample_failed(self, message: str) -> None:
        self._release_sample_worker()
        self._on_failed(message)

    def _on_sample_cancelled(self) -> None:
        self._release_sample_worker()
        self._on_cancelled()

    def _on_stage_progress(self, phase: str, fraction: object) -> None:
        self.processing_status.set_phase(phase, fraction)
        stage = phase.split(":", 1)[0]
        self.status_label.setText(self.tr(STAGE_LABELS.get(stage, "Preparation")))
        value = self.processing_status.fraction
        self.progress_bar.setRange(0, 0 if value is None else 1000)
        if value is not None:
            self.progress_bar.setValue(round(value * 1000))
        self.progress_label.setText("…" if value is None else f"{value:.0%}")
        self.pause_btn.setEnabled(
            self.run_worker is not None and stage in {"video", "audio", "save"},
        )

    def _on_progress(self, fraction: float, message: str) -> None:
        if self.processing_status.phase is not None:
            return
        self.status_label.setText(message)
        self.progress_bar.setValue(int(fraction * 1000))
        self.progress_label.setText(f"{fraction:.0%}")

    def _on_audio_progress(self, fraction: float, label: str) -> None:
        # First audio event reveals the sub-bar; from that point onwards
        # it tracks loudnorm pass progress while the main bar stays
        # pinned to the video-segments total.
        if not self.audio_progress_bar.isVisible():
            self.audio_progress_bar.setVisible(True)
        self.audio_progress_bar.setValue(int(fraction * 1000))
        if self.processing_status.phase is None:
            self.progress_label.setText(self.tr("Audio") + f": {fraction:.0%}")
        self.audio_progress_bar.setFormat(f"Audio ({label}): %p%")

    def _on_done(self, output: str, qa_html: str) -> None:
        label = "Sample ready: {file}" if self._sample_mode else "Completed: {file}"
        self.status_label.setText(self.tr(label).format(file=Path(output).name))
        self.processing_status.finish(success=True)
        self.status_label.setToolTip(output)
        self._completed_output_path = Path(output)
        if self._review_source is not None:
            self._review_pair = (self._review_source, Path(output))
        self.compare_btn.setEnabled(self._review_pair is not None)
        self.save_sample_btn.setVisible(self._sample_mode)
        self.result_actions.show()
        self.metrics_details.setVisible(bool(qa_html))
        self._result_reveal_timer.start(0)
        self.timeline.reset()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_label.setText("100%")
        if self.audio_progress_bar.isVisible():
            self.audio_progress_bar.setValue(1000)
        self.run_worker = None
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(self.tr("&Pause"))
        if qa_html:
            self.qa_html_path = Path(qa_html)
            self.open_qa_btn.setEnabled(True)
            qa_json = self.qa_html_path.with_suffix(".json")
            try:
                qa = json.loads(qa_json.read_text())
                self.kpi_pills.set_qa(qa)
            except (OSError, json.JSONDecodeError) as exc:
                # KPI pills are best-effort decoration; the QA HTML
                # report is the authoritative artifact. Log so a missing
                # JSON file is visible during triage instead of a silent
                # empty pill row.
                self.log.log(f"KPI: failed to read {qa_json.name}: {exc}", "log")
        self._refresh_run_button()

    def _on_failed(self, message: str) -> None:
        self.processing_status.finish(success=False)
        self.progress_bar.setRange(0, 1000)
        self.status_label.setText(self.tr("Failed."))
        self.log.log(f"!!! {message}", "error")
        self.run_worker = None
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(self.tr("&Pause"))
        self._refresh_run_button()

    def _on_cancelled(self) -> None:
        """Distinct from _on_failed: user cancellation is not an error."""
        self.processing_status.finish(success=False)
        self.progress_bar.setRange(0, 1000)
        self.status_label.setText(self.tr("Cancelled."))
        self.log.log("--- Cancelled by user ---", "info")
        self.run_worker = None
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(self.tr("&Pause"))
        self._refresh_run_button()

    def _on_cancel(self) -> None:
        if self._save_worker is not None:
            self._save_worker.request_cancel()
        if self._sample_worker is not None:
            self._sample_worker.request_cancel()
            self.status_label.setText(self.tr("Cancelling…"))
        if self.run_worker is not None:
            self.run_worker.request_cancel()
            self.status_label.setText(self.tr("Cancelling…"))

    # v0.7 R6 / F5 — Pause / Resume handlers.
    def _on_pause_toggle(self) -> None:
        """Flip the worker's pause state. Idempotent.

        Visual feedback (label flip, status banner) is driven entirely
        by the `paused_changed` signal so a future channel that flips
        pause from elsewhere (e.g. headless RPC) stays in sync.
        """
        if self.run_worker is None:
            return
        if self.run_worker.is_paused():
            self.run_worker.request_resume()
        else:
            self.run_worker.request_pause()

    def _on_paused_changed(self, paused: bool) -> None:
        self.processing_status.set_paused(paused)
        if paused:
            self.pause_btn.setText(self.tr("&Resume"))
            self.status_label.setText(self.tr("Paused — encode suspended."))
        else:
            self.pause_btn.setText(self.tr("&Pause"))
            self.status_label.setText(self.tr("Resumed."))

    def _on_open_qa(self) -> None:
        if self.qa_html_path and self.qa_html_path.exists():
            webbrowser.open(self.qa_html_path.as_uri())

    def _refresh_run_button(self, *, preflight_fail: bool = False) -> None:
        busy = (self.run_worker is not None or self._tune_worker is not None
                or self._sample_worker is not None or self._save_worker is not None)
        same_path = (
            self.state.input_path is not None and self.state.output_path is not None
            and self.state.input_path.resolve() == self.state.output_path.resolve()
        )
        ready = (
            self.state.input_path is not None
            and self.state.output_path is not None
            and not busy and self.preflight_worker is None
            and self.profile_combo.currentData() is not None
            and not (preflight_fail or self._preflight_blocked or same_path)
        )
        self.run_btn.setEnabled(ready)
        for widget in (self.input_picker, self.output_picker, self.profile_combo,
                       self.profile_cards, self.sample_timeline,
                       self.encoder_selector, self.edit_profile_btn,
                       self.sample_start, self.sample_length):
            widget.setEnabled(not busy)
        self.pause_btn.setVisible(self.run_worker is not None)
        cancellable = (self.run_worker is not None or self._sample_worker is not None
                       or self._save_worker is not None)
        self.cancel_btn.setVisible(cancellable)
        self.cancel_btn.setEnabled(cancellable)
        self.save_sample_btn.setEnabled(not busy)
        self.preview_source_btn.setEnabled(self.state.input_path is not None)
        sample_hdr = self._source_meta is not None and any(
            video.color.is_hdr for video in self._source_meta.video
        )
        self.sample_hint.setText(self.tr(
            "HDR samples are unavailable; use full processing to preserve HDR metadata."
            if sample_hdr else
            "Uses the selected profile. The full output destination stays unchanged."
        ))
        self.sample_btn.setEnabled(
            self._source_meta is not None and self._source_meta.duration_sec > 0
            and not sample_hdr
            and self._source_meta.path == self.state.input_path
            and not busy and self.preflight_worker is None
            and not (self._preflight_blocked or preflight_fail)
            and self.profile_combo.currentData() is not None,
        )
        self.preflight_btn.setEnabled(
            self.state.input_path is not None and self.profile_combo.currentData() is not None
            and not busy and self.preflight_worker is None,
        )
        if busy:
            message = (
                "Saving sample…" if self._save_worker is not None else
                "Processing…" if self.run_worker is not None or self._sample_worker is not None
                else "Auto-tuning…"
            )
        elif self.state.input_path is None:
            message = "Choose a video to get started."
        elif self.profile_combo.currentData() is None:
            message = "Choose a processing profile."
        elif same_path:
            message = "Choose a different output file to preserve the source."
        elif self._preflight_blocked or preflight_fail:
            message = "Resolve the issues shown above before processing."
        elif self.preflight_worker is not None:
            message = "Checking video…"
        elif self.state.output_path is None:
            message = "Choose where to save the result."
        else:
            message = "Ready to process"
        self.readiness_hint.setText(self.tr(message))
        # Auto-tune only needs an input + a profile; output isn't required
        # because we're not encoding the final file yet.  Also gated on no
        # in-flight CalibrateWorker so multiple tunes can't stack.
        self.auto_tune_btn.setEnabled(
            self.state.input_path is not None
            and self.profile_combo.currentData() is not None
            and getattr(self, "_tune_worker", None) is None
            and self.run_worker is None,
            # Sample preparation shares the same user selections.
        )
        if self._sample_worker is not None or self._save_worker is not None:
            self.auto_tune_btn.setEnabled(False)

    def shutdown_workers(self, wait_ms: int = 16_000) -> bool:
        self._shutting_down = True
        stopped = super().shutdown_workers(wait_ms)
        if stopped:
            self._result_reveal_timer.stop()
            self.processing_status.timer.stop()
            if self._compare_dialog is not None:
                if not self._compare_dialog.close():
                    return False
                self._compare_dialog = None
            if self._sample_directory is not None:
                self._sample_directory.cleanup()
                self._sample_directory = None
        return stopped

    def changeEvent(self, event: QEvent | None) -> None:
        if (event is not None and event.type() == QEvent.Type.LanguageChange
                and hasattr(self, "run_btn")):
            for widget, source in (
                (self.run_btn, "Start processing"), (self.preflight_btn, "Check video"),
                (self.edit_profile_btn, "Edit profile…"),
                (self.auto_tune_btn, "Auto-tune for this source"),
                (self.open_output_btn, "Open processed video"),
                (self.open_qa_btn, "Open quality report"), (self.cancel_btn, "&Cancel"),
                (self.preview_source_btn, "Preview original"),
                (self.compare_btn, "Compare before / after"),
                (self.sample_btn, "Process sample"), (self.save_sample_btn, "Save sample…"),
            ):
                widget.setText(self.tr(source))
            self.save_sample_btn.setAccessibleName(self.tr("Save sample"))
            self.sample_start_label.setText(self.tr("Start time"))
            for index in range(self.sample_length.count()):
                self.sample_length.setItemText(index, self.tr("{seconds} s").format(
                    seconds=self.sample_length.itemData(index),
                ))
            if self.source_thumbnail.pixmap().isNull():
                self.source_thumbnail.setText(self.tr("Video preview"))
            self.profile_label.setText(self.tr("Profile"))
            self.encoder_label.setText(self.tr("Encoder"))
            self._update_profile_hint()
            self._refresh_run_button()
            if self.state.input_path is None:
                self.source_metadata.setText(self.tr("Choose a source video to see its details."))
            if self.run_worker is None and self._completed_output_path is None:
                self.status_label.setText(self.tr("Your result will appear here after processing."))
        super().changeEvent(event)

    # --- F7 Auto-tune ----------------------------------------------------
    def _on_auto_tune(self) -> None:
        """Spawn a CalibrateWorker on (input, current profile).

        Saves the tuned profile next to the original as
        ``<stem>.tuned.yaml`` and switches ``state.profile_path`` to
        it.  Errors surface as a QMessageBox; cancel is wired through
        ``CalibrateWorker.request_cancel`` like other workers.
        """
        from video_uniquifier.core.calibration.loop import CalibrationTarget
        from video_uniquifier.core.profile_loader import load_profile
        from video_uniquifier.gui.workers.calibrate_worker import CalibrateWorker

        if self.state.input_path is None:
            return
        profile_data = self.profile_combo.currentData()
        if not profile_data:
            return
        try:
            profile = load_profile(Path(profile_data))
        except VideoUniquifierError as exc:
            QMessageBox.critical(self, "Profile error", str(exc))
            return

        # Conservative defaults — same as the Calibrate screen's
        # starting knob positions.  Users who want different knobs
        # use the dedicated Calibrate screen.
        target = CalibrationTarget(
            max_self_match=0.2,
            min_quality=88.0,
            max_iterations=5,
            test_clip_sec=60.0,
        )

        worker = CalibrateWorker(self.state.input_path, profile, target)
        self._tune_worker = worker
        self._tune_source_path = Path(profile_data)
        worker.failed.connect(self._on_auto_tune_failed)
        worker.completed.connect(self._on_auto_tune_completed)
        worker.finished_ok.connect(self._on_auto_tune_finished)
        self.auto_tune_btn.setEnabled(False)
        self.status_label.setText(self.tr("Auto-tuning profile…"))
        self.log.log(
            f"--- Auto-tune started on {self.state.input_path.name} "
            f"with {Path(profile_data).stem} ---", "info",
        )
        worker.start()
        self._refresh_run_button()

    def _on_auto_tune_completed(self, tuned_profile: object) -> None:
        """Persist the tuned profile and switch state.profile_path to it."""
        from video_uniquifier.core.models import Profile as _Profile
        from video_uniquifier.core.profile_loader import dump_profile

        if not isinstance(tuned_profile, _Profile):
            return
        source = getattr(self, "_tune_source_path", None)
        if source is None:
            return
        tuned_path = source.with_name(f"{source.stem}.tuned.yaml")
        try:
            dump_profile(tuned_profile, tuned_path)
        except Exception as exc:  # noqa: BLE001 — surface dump failures to user
            QMessageBox.critical(self, "Save tuned profile failed", str(exc))
            return
        # Reload the combo so the new file appears, then select it.
        self._reload_profile_combo()
        idx = self.profile_combo.findData(str(tuned_path))
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        self.state.set_profile_path(tuned_path)
        self.log.log(f"Auto-tune saved tuned profile: {tuned_path}", "info")
        self.status_label.setText(f"Tuned profile saved: {tuned_path.name}")

    def _on_auto_tune_failed(self, message: str) -> None:
        self.log.log(f"Auto-tune failed: {message}", "error")
        self.status_label.setText(self.tr("Auto-tune failed."))
        QMessageBox.critical(self, "Auto-tune failed", message)

    def _on_auto_tune_finished(self, _payload: object) -> None:
        worker = getattr(self, "_tune_worker", None)
        if worker is not None:
            with contextlib.suppress(TypeError, RuntimeError):
                worker.disconnect()
            worker.quit()
            worker.wait(2000)
        self._tune_worker = None
        self._refresh_run_button()

    def _reload_profile_combo(self) -> None:
        """Repopulate the profile dropdown so a newly-saved tuned file shows up."""
        prev = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in sorted(PROFILES_DIR.glob("*.yaml")):
            self.profile_combo.addItem(p.stem, str(p))
        if prev:
            idx = self.profile_combo.findData(prev)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        self.profile_combo.blockSignals(False)
