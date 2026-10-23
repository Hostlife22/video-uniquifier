"""Desktop Reels workflow: source -> settings -> sample -> delivery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml
from PyQt6.QtCore import QEvent, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QHideEvent, QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.core.models import SourceMeta
from video_uniquifier.core.reels.config import ReelsRules, load_rules
from video_uniquifier.gui.design import Space
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.state import AppState, HistoryEntry
from video_uniquifier.gui.widgets.file_picker import FilePickerRow
from video_uniquifier.gui.widgets.reels_options import ReelsOptions
from video_uniquifier.gui.widgets.studio_preview import StudioPreview
from video_uniquifier.gui.widgets.surfaces import Disclosure, SectionCard
from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
from video_uniquifier.gui.widgets.workflow_navigation import WorkflowNavigation
from video_uniquifier.gui.workers.probe_worker import ProbeWorker
from video_uniquifier.gui.workers.reels_worker import ReelsMode, ReelsWorker

PHASES = {"queued": "Waiting for a processing slot", "probing": "Checking source video",
          "processing": "Encoding video", "qa": "Checking picture and sound",
          "success": "Delivery complete"}
ERROR_HINTS = {
    "hdr_requires_tonemap": "Choose HDR to SDR in delivery settings, then check a sample.",
    "scene_dependency": "Install the scene extra or turn off shot detection in Audio & timeline.",
    "trim_duration": "Trim removes the entire video. Reduce the start/end values.",
    "trim_subtitle_track": "This video has selectable subtitles. Trim requires a prepared source.",
    "subtitle_zone_conflict": "Move the title/logo above the protected subtitle zone.",
    "title_lines": "Shorten the title or reduce its font size.",
    "quality_failed": "The delivery failed technical QA. Open details before trying again.",
}


class ReelsScreen(ScreenBase):
    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self.worker: ReelsWorker | None = None
        self.probe_worker: ProbeWorker | None = None
        self.source_meta: SourceMeta | None = None
        self.result_directory: Path | None = None
        self.sample_directory: Path | None = None
        self.last_report: dict[str, Any] | None = None
        self._review_pair: tuple[Path, Path] | None = None
        self._review_source_range: tuple[float, float] | None = None
        self._compare_dialog: VideoCompareDialog | None = None
        self._reveal_comparison = False
        self._sample_fingerprint: str | None = None
        self._preflight_fingerprint: str | None = None
        self._preview_storage = TemporaryDirectory(prefix="video_reels_preview_")
        self._output_suggested: str | None = None
        self._build_ui()
        self._refresh_controls()

    def _build_ui(self) -> None:
        layout = self.page_layout(
            "Video delivery", "Reels vertical preset · set up, preview and export in four steps.",
        )
        self.navigation = WorkflowNavigation((
            "Choose source", "Delivery settings", "Preview check", "Export result",
        ))
        self.navigation.currentChanged.connect(self._show_step)
        layout.addWidget(self.navigation)
        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.pages, stretch=1)
        self._build_source_page()
        self._build_settings_page()
        self._build_preview_page()
        self._build_result_page()
        self.feedback = QLabel(self.tr("Choose a video to get started."))
        self.feedback.setObjectName("workflow_feedback")
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)

        self.summary = QLabel()
        self.summary.setObjectName("hint")
        self.summary.setWordWrap(True)
        actions = QHBoxLayout()
        actions.addWidget(self.summary, stretch=1)
        self.back_btn = QPushButton(self.tr("Previous step"))
        self.back_btn.setProperty("variant", "quiet")
        self.back_btn.clicked.connect(lambda: self.navigation.setCurrentIndex(
            self.navigation.currentIndex() - 1))
        actions.addWidget(self.back_btn)
        self.cancel_btn = QPushButton(self.tr("Cancel task"))
        self.cancel_btn.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_btn)
        self.next_btn = QPushButton()
        self.next_btn.setProperty("variant", "primary")
        self.next_btn.clicked.connect(self._next)
        actions.addWidget(self.next_btn)
        self.add_action_bar(actions)
        for button in self.findChildren(QAbstractButton):
            if button.text() and not button.accessibleName():
                button.setAccessibleName(button.text())

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, Space.MD, 0, 0)
        layout.setSpacing(Space.LG)
        self.pages.addWidget(widget)
        return widget, layout

    def _label(self, source: str, *, hint: bool = True) -> QLabel:
        label = QLabel(self.tr(source))
        label.setObjectName("hint" if hint else "section_title")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        return label

    def _build_source_page(self) -> None:
        _, layout = self._page()
        row = QHBoxLayout()
        row.setSpacing(Space.LG)
        self.source_preview = StudioPreview(self.state)
        self.source_preview.select_sample.hide()
        self.source_preview.setMinimumWidth(260)
        self.source_preview.stage.setMinimumHeight(120)
        self.source_preview.choose_requested.connect(lambda: self.input_picker.browse_btn.click())
        self.source_preview.source_dropped.connect(lambda path: self.input_picker.set_path(path))
        row.addWidget(self.source_preview, stretch=3)
        self.source_card = SectionCard("Source & destination")
        self.source_card.setMinimumWidth(260)
        self.source_card.setMaximumWidth(370)
        self.input_picker = FilePickerRow("Input video", "input", state=self.state)
        self.input_picker.path_changed.connect(self._source_changed)
        self.source_card.body.addWidget(self.input_picker)
        self.metadata = self._label("Video details appear after you choose a source.")
        self.source_card.body.addWidget(self.metadata)
        self.source_card.body.addSpacing(Space.LG)
        self.source_card.body.addWidget(self._label("Export folder", hint=False))
        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText(self.tr("Choose an export folder…"))
        self.output_folder.setAccessibleName(self.tr("Export folder"))
        self.output_folder.textChanged.connect(self._refresh_controls)
        self.source_card.body.addWidget(self.output_folder)
        self.folder_btn = QPushButton(self.tr("Choose folder…"))
        self.folder_btn.clicked.connect(self._choose_folder)
        self.source_card.body.addWidget(self.folder_btn)
        self.source_card.body.addWidget(self._label(
            "Each export has its own video, report and preview folder.",
        ))
        self.source_card.body.addStretch(1)
        row.addWidget(self.source_card, stretch=2)
        layout.addLayout(row, stretch=1)

    def _build_settings_page(self) -> None:
        _, layout = self._page()
        top = QHBoxLayout()
        top.addWidget(self._label("Reels delivery preset", hint=False), stretch=1)
        self.import_btn = QPushButton(self.tr("Load configuration…"))
        self.import_btn.setProperty("variant", "quiet")
        self.import_btn.clicked.connect(self._import_rules)
        top.addWidget(self.import_btn)
        self.reset_btn = QPushButton(self.tr("Restore defaults"))
        self.reset_btn.setProperty("variant", "quiet")
        self.reset_btn.clicked.connect(lambda: self.options.set_rules(ReelsRules()))
        top.addWidget(self.reset_btn)
        layout.addLayout(top)
        self.options = ReelsOptions()
        self.options.changed.connect(self._settings_changed)
        layout.addWidget(self.options, stretch=1)

    def _build_preview_page(self) -> None:
        _, layout = self._page()
        self.review_hint = self._label(
            "Check a 10-second sample before exporting. Your full video is processed separately.",
        )
        layout.addWidget(self.review_hint)
        self.review_tabs = QStackedWidget()
        self.review_preview = StudioPreview(self.state)
        self.review_preview.select_sample.hide()
        self.review_preview.choose_requested.connect(lambda: self.navigation.setCurrentIndex(0))
        self.review_tabs.addWidget(self.review_preview)
        self.safe_preview = QLabel(self.tr("Generate a sample to inspect the safe area."))
        self.safe_preview.setObjectName("safe_area_preview")
        self.safe_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.safe_preview.setMinimumSize(0, 0)
        self.safe_preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.review_tabs.addWidget(self.safe_preview)
        layout.addWidget(self.review_tabs, stretch=1)
        controls = QHBoxLayout()
        self.check_btn = QPushButton(self.tr("Check configuration"))
        self.check_btn.clicked.connect(lambda: self._start("preflight"))
        controls.addWidget(self.check_btn)
        self.sample_btn = QPushButton(self.tr("Generate 10-second sample"))
        self.sample_btn.clicked.connect(lambda: self._start("sample"))
        controls.addWidget(self.sample_btn)
        self.safe_btn = QPushButton(self.tr("Show safe area"))
        self.safe_btn.setCheckable(True)
        self.safe_btn.toggled.connect(self._toggle_safe_area)
        controls.addWidget(self.safe_btn)
        controls.addStretch(1)
        layout.addLayout(controls)
        layout.addWidget(self._label(
            "Watch subtitles and listen to dialogue. Safe areas are internal guides.",
        ))

    def _build_result_page(self) -> None:
        _, layout = self._page()
        self.result_heading = self._label("Ready when you are", hint=False)
        layout.addWidget(self.result_heading)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)
        self.progress_bar.setAccessibleName(self.tr("Reels processing progress"))
        layout.addWidget(self.progress_bar)
        self.progress_text = self._label(
            "Your completed video and quality checks will appear here.",
        )
        layout.addWidget(self.progress_text)
        self.result_scroll = QScrollArea()
        self.result_scroll.setMinimumHeight(0)
        self.result_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.result_scroll.setWidgetResizable(True)
        content = QWidget()
        self.result_body = QVBoxLayout(content)
        self.result_body.setContentsMargins(Space.XS, Space.XS, Space.XS, Space.XS)
        self.result_body.setSpacing(Space.LG)
        self.result_summary = self._label("1080 × 1920 · H.264 MP4 · two-pass loudness")
        self.result_body.addWidget(self.result_summary)
        self.warnings = self._label("")
        self.result_body.addWidget(self.warnings)
        self.scene_table = QTableWidget(0, 4)
        self.scene_table.setProperty("studioTable", True)
        self.scene_table.setHorizontalHeaderLabels([
            self.tr("Shot"), self.tr("Source start"), self.tr("Output start"), self.tr("Duration"),
        ])
        self.scene_table.setAccessibleName(self.tr("Shot timeline"))
        header = self.scene_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scene_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scene_table.setMaximumHeight(220)
        self.scene_table.hide()
        self.result_body.addWidget(self.scene_table)
        self.details = Disclosure("Processing details", state=self.state)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setAccessibleName(self.tr("Processing details"))
        self.details.body.addWidget(self.details_text)
        self.result_body.addWidget(self.details)
        self.result_body.addStretch(1)
        self.result_scroll.setWidget(content)
        layout.addWidget(self.result_scroll, stretch=1)
        self.result_actions = QWidget()
        self.result_actions.setObjectName("action_bar")
        actions = QVBoxLayout(self.result_actions)
        actions.setContentsMargins(Space.PAGE, Space.SM, Space.PAGE, Space.SM)
        row = QHBoxLayout()
        self.compare_btn = QPushButton(self.tr("Compare before / after"))
        self.compare_btn.setProperty("variant", "primary")
        self.compare_btn.clicked.connect(lambda: self._open_comparison())
        row.addWidget(self.compare_btn)
        self.open_video_btn = QPushButton(self.tr("Play completed video"))
        self.open_video_btn.clicked.connect(lambda: self._open_comparison(result_only=True))
        row.addWidget(self.open_video_btn)
        row.addStretch(1)
        actions.addLayout(row)
        artifacts = QHBoxLayout()
        self.open_folder_btn = QPushButton(self.tr("Open export folder"))
        self.open_folder_btn.clicked.connect(lambda: self._open_artifact(""))
        artifacts.addWidget(self.open_folder_btn)
        self.open_report_btn = QPushButton(self.tr("Open quality report"))
        self.open_report_btn.clicked.connect(lambda: self._open_artifact("report.json"))
        artifacts.addWidget(self.open_report_btn)
        artifacts.addStretch(1)
        actions.addLayout(artifacts)
        self.outer_layout.addWidget(self.result_actions)
        self.result_actions.hide()

    def _show_step(self, index: int) -> None:
        if self._compare_dialog is not None:
            self._compare_dialog.pause()
        for preview in (self.source_preview, self.review_preview):
            preview.pause()
        self.pages.setCurrentIndex(index)
        self.result_actions.setVisible(index == 3 and self.result_directory is not None)
        self._refresh_controls()
        scrollbar = self.page_scroll.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(0)

    def _source_changed(self, path: object) -> None:
        self.source_meta = None
        self._settings_changed()
        source = path if isinstance(path, Path) else None
        self.source_preview.set_source(source)
        self.review_preview.set_source(source)
        self.metadata.setText(self.tr("Reading video details…" if source else
                                      "Video details appear after you choose a source."))
        if source is None:
            self._refresh_controls()
            return
        if not self.output_folder.text() or self.output_folder.text() == self._output_suggested:
            self._output_suggested = str(source.parent / "Reels")
            self.output_folder.setText(self._output_suggested)
        if self.probe_worker is None:
            self._probe(source)
        self._refresh_controls()

    def _probe(self, source: Path) -> None:
        worker = ProbeWorker(source)
        worker.setParent(self)
        self.probe_worker = worker
        worker.probed.connect(self._probed)
        worker.failed.connect(lambda message: self._set_feedback(message, error=True))
        worker.finished.connect(self._probe_finished)
        worker.start()

    def _probed(self, meta: object) -> None:
        if not isinstance(meta, SourceMeta) or meta.path != self.input_picker.current_path():
            return
        self.source_meta = meta
        if meta.video:
            video = meta.video[0]
            self.metadata.setText(self.tr(
                "{width} × {height} · {fps:.3f} fps · {seconds:.1f} s",
            ).format(
                width=video.width, height=video.height, fps=video.fps, seconds=meta.duration_sec,
            ) + "\n" + self.tr("{count} audio track(s) · {color}").format(
                count=len(meta.audio), color="HDR" if video.color.is_hdr else "SDR"))
        self._set_feedback(self.tr("Source loaded. Continue to delivery settings."))

    def _probe_finished(self) -> None:
        worker = self.probe_worker
        self.probe_worker = None
        if worker is not None:
            worker.deleteLater()
            current = self.input_picker.current_path()
            if current is not None and current != worker.path:
                self._probe(current)
        self._refresh_controls()

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self.tr("Export folder"),
                                                     self.output_folder.text())
        if directory:
            self.output_folder.setText(directory)

    def _settings_changed(self) -> None:
        self._sample_fingerprint = self._preflight_fingerprint = None
        self.sample_directory = None
        if hasattr(self, "review_hint"):
            self.review_hint.setText(self.tr(
                "Settings changed. Generate a fresh sample to review.",
            ))
            self.review_preview.set_result(None)
            self.safe_btn.setChecked(False)
            self.safe_preview.clear()
        if hasattr(self, "summary"):
            self._refresh_controls()

    def _fingerprint(self, rules: ReelsRules, assets: dict[str, Path]) -> str:
        return rules.model_dump_json() + str(self.input_picker.current_path()) + str(assets)

    def _refresh_controls(self) -> None:
        if not hasattr(self, "next_btn"):
            return
        busy = self.worker is not None or self.probe_worker is not None
        ready = self.source_meta is not None and bool(self.source_meta.video)
        for control in (self.input_picker, self.folder_btn, self.output_folder, self.options,
                        self.import_btn, self.reset_btn):
            control.setEnabled(not busy)
        self.source_preview.import_button.setEnabled(not busy)
        self.source_preview.setAcceptDrops(not busy)
        self.check_btn.setEnabled(ready and not busy)
        self.sample_btn.setEnabled(ready and not busy)
        self.safe_btn.setEnabled(not busy and self.sample_directory is not None)
        self.cancel_btn.setVisible(self.worker is not None)
        self.cancel_btn.setEnabled(self.worker is not None
                                   and not self.worker.cancel_token.is_cancelled())
        self.back_btn.setVisible(self.navigation.currentIndex() > 0)
        self.back_btn.setEnabled(not busy)
        index = self.navigation.currentIndex()
        self.next_btn.setText(self.tr("Next step" if index < 3 else "Export full video"))
        self.next_btn.setAccessibleName(self.next_btn.text())
        self.next_btn.setEnabled(ready and not busy and (
            index < 3 or bool(self.output_folder.text().strip())))
        width, height = self.options.resolution.currentData()
        self.summary.setText(self.tr("{width} × {height} · H.264 · local processing").format(
            width=width, height=height))

    def _next(self) -> None:
        if self.navigation.currentIndex() < 3:
            self.navigation.setCurrentIndex(self.navigation.currentIndex() + 1)
        else:
            self._start("export")

    def _start(self, mode: ReelsMode) -> None:
        if self.worker is not None or self.probe_worker is not None:
            return
        source = self.input_picker.current_path()
        if source is None:
            self.navigation.setCurrentIndex(0)
            self._set_feedback(self.tr("Choose a video to get started."), error=True)
            return
        try:
            rules, assets = self.options.configuration()
            if mode == "export" and not self.output_folder.text().strip():
                raise ValueError(self.tr("Choose an export folder…"))
        except ValueError as exc:
            self.navigation.setCurrentIndex(1)
            self._set_feedback(self.tr(
                "Check enabled options, local files and time ranges. See processing details.",
            ), error=True)
            self.details_text.setPlainText(str(exc))
            self.details.set_expanded(True)
            return
        if not self._close_comparison():
            return
        root = (Path(self.output_folder.text()).expanduser() if mode == "export"
                else Path(self._preview_storage.name))
        worker = ReelsWorker(source, rules, root, mode=mode, assets=assets)
        worker.setParent(self)
        self.worker = worker
        self._active_fingerprint = self._fingerprint(rules, assets)
        self._active_source = source
        self._active_rules = rules
        self.source_preview.pause()
        self.review_preview.pause()
        self.progress_bar.setValue(0)
        if mode == "export":
            self._review_pair = None
            self._review_source_range = None
            self._reveal_comparison = False
            self.result_directory = None
            self.result_actions.hide()
            self.scene_table.hide()
            self.warnings.clear()
            self.result_heading.setText(self.tr("Preparing delivery…"))
            self.navigation.setCurrentIndex(3)
        self._set_feedback(self.tr("Checking source video"))
        worker.progress.connect(self._progress)
        worker.finished_ok.connect(self._completed)
        worker.problem.connect(self._failed)
        worker.cancelled.connect(self._cancelled)
        worker.finished.connect(self._worker_finished)
        self._refresh_controls()
        worker.start()

    def _progress(self, fraction: float, phase: str) -> None:
        self.progress_bar.setValue(max(self.progress_bar.value(), round(fraction * 1000)))
        text = self.tr(PHASES.get(phase, phase))
        self.progress_text.setText(text + f" · {fraction:.0%}")
        self._set_feedback(text)

    def _completed(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        mode = payload["mode"]
        if mode == "preflight":
            self._preflight_fingerprint = self._active_fingerprint
            self._set_feedback(self.tr("Configuration check passed. You can generate a sample."))
            self.details_text.setPlainText(str(payload.get("findings", {})))
            if payload.get("warnings"):
                self._set_feedback(self.tr(
                    "Check passed with warnings. Review processing details.",
                ))
                self.details_text.appendPlainText("\n".join(payload["warnings"]))
            return
        directory = Path(payload["directory"])
        report = payload["report"]
        if mode == "sample":
            self.sample_directory = directory
            self._sample_fingerprint = self._active_fingerprint
            self.review_preview.set_result(directory / "output.mp4")
            self.review_hint.setText(self.tr(
                "Sample ready. Check dialogue, subtitles and safe areas.",
            ))
            self.navigation.setCurrentIndex(2)
            self._set_feedback(self.tr(
                "Sample ready. Full export uses the entire selected timeline.",
            ))
            if payload.get("warnings"):
                self._set_feedback(self.tr(str(payload["warnings"][0])))
            self._fit_safe_preview()
            return
        self.result_directory = directory
        self.last_report = report
        self._review_pair = (self._active_source, directory / "output.mp4")
        self._review_source_range = (
            self._active_rules.scenes.trim_start_sec,
            report["source"]["duration_sec"] - self._active_rules.scenes.trim_end_sec,
        )
        self._reveal_comparison = self.isVisible() and self.navigation.currentIndex() == 3
        self.progress_bar.setValue(1000)
        self.progress_text.setText(self.tr("Delivery complete"))
        self.result_heading.setText(self.tr("Your Reels video is ready"))
        self.result_actions.setVisible(self.navigation.currentIndex() == 3)
        quality = report["quality_check"]
        output = report["output"]
        video = output["video"][0]
        self.result_summary.setText(self.tr(
            "Technical QA: {status}\n{width} × {height} · {fps} fps · {seconds:.1f} s",
        ).format(status=self.tr("Passed" if quality["status"] == "passed" else "Failed"),
                 width=video["width"], height=video["height"], fps=report["delivery_fps"],
                 seconds=output["duration_sec"]))
        warning_lines = [self.tr("Listen to dialogue and check hard subtitles before publishing.")]
        warning_lines.extend(self.tr(str(warning)) for warning in report["warnings"])
        self.warnings.setText("\n".join(warning_lines))
        self.details_text.setPlainText((directory / "report.json").read_text(encoding="utf-8"))
        scenes = report.get("scenes", {}).get("output_timeline", [])
        self.scene_table.setRowCount(len(scenes))
        for row, scene in enumerate(scenes):
            keys = ("scene_id", "source_start_sec", "start_sec", "duration_sec")
            for column, key in enumerate(keys):
                value = scene[key]
                self.scene_table.setItem(row, column, QTableWidgetItem(
                    str(value) if column == 0 else f"{value:.2f} s"))
        self.scene_table.setVisible(bool(scenes))
        self._set_feedback(self.tr("Export saved. Compare the original and result in the app."))
        self._record_history(report)

    def _record_history(self, report: dict[str, Any]) -> None:
        if self.result_directory is None:
            return
        try:
            self.state.push_history(HistoryEntry(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                source_path=str(self._active_source), profile_name=self._active_rules.preset_id,
                encoder_name="libx264", output_path=str(self.result_directory / "output.mp4"),
                qa_html_path=None, plan_hash=report["plan_hash"], status="done",
            ))
        except OSError as exc:
            self.details_text.appendPlainText(str(exc))

    def _failed(self, code: str, message: str) -> None:
        self.result_directory = None
        self.result_actions.hide()
        self.result_heading.setText(self.tr("Processing stopped"))
        guidance = self.tr(ERROR_HINTS.get(
            code, "Review the settings and processing details, then try again.",
        ))
        self._set_feedback(guidance, error=True)
        self.details_text.setPlainText(f"{code}\n{message}")
        self.details.set_expanded(True)
        self.navigation.setCurrentIndex(3)
        self.progress_text.setText(self.tr("Failed") + f" · {code}")

    def _cancelled(self) -> None:
        self.result_heading.setText(self.tr("Task cancelled"))
        self.progress_text.setText(self.tr("Task cancelled"))
        self._set_feedback(self.tr("Task cancelled. You can change settings and try again."))

    def _worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self._refresh_controls()
        if self._reveal_comparison:
            self._reveal_comparison = False
            if self.isVisible() and self.navigation.currentIndex() == 3:
                self._open_comparison()

    def _cancel(self) -> None:
        if self.worker is not None:
            self.worker.request_cancel()
            self.cancel_btn.setEnabled(False)
            self._set_feedback(self.tr("Cancelling… waiting for the worker to stop."))

    def _set_feedback(self, text: str, *, error: bool = False) -> None:
        self.feedback.setText(text)
        self.feedback.setProperty("error", error)
        style = self.feedback.style()
        if style is not None:
            style.unpolish(self.feedback)
            style.polish(self.feedback)
        self.feedback.setAccessibleName(text)

    def _toggle_safe_area(self, checked: bool) -> None:
        self.review_preview.pause()
        self.review_tabs.setCurrentIndex(1 if checked else 0)
        self._fit_safe_preview()

    def _fit_safe_preview(self) -> None:
        if self.sample_directory is None:
            return
        path = self.sample_directory / "safe-area.png"
        if path.is_file():
            self.safe_preview.setPixmap(QPixmap(str(path)).scaled(
                self.safe_preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _open_artifact(self, name: str) -> None:
        if name == "output.mp4":
            self._open_comparison(result_only=True)
            return
        if self.result_directory is not None:
            path = self.result_directory / name
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _close_comparison(self) -> bool:
        if self._compare_dialog is not None:
            if not self._compare_dialog.close():
                return False
            self._compare_dialog.deleteLater()
            self._compare_dialog = None
        return True

    def _open_comparison(self, *, result_only: bool = False) -> None:
        if self._review_pair is None:
            return
        source, candidate = self._review_pair
        if not candidate.is_file() or (not result_only and not source.is_file()):
            self._set_feedback(self.tr(
                "Video file is unavailable. Check that the original and export still exist.",
            ), error=True)
            return
        if not self._close_comparison():
            return
        self.source_preview.pause()
        self.review_preview.pause()
        dialog = VideoCompareDialog(
            None if result_only else source, candidate,
            source_range=None if result_only else self._review_source_range, parent=self,
        )
        dialog.wipe.set_theme(self.state.theme)
        self.state.theme_changed.connect(dialog.wipe.set_theme)
        self._compare_dialog = dialog
        dialog.show()

    def hideEvent(self, event: QHideEvent | None) -> None:
        if self._compare_dialog is not None:
            self._compare_dialog.pause()
        super().hideEvent(event)

    def _import_rules(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.tr("Load configuration…"), "",
                                                 "YAML (*.yaml *.yml)")
        if not filename:
            return
        try:
            path = Path(filename)
            rules = load_rules(path)
            for relative in (rules.packaging.logo.source, rules.packaging.title.font_path):
                if relative:
                    from video_uniquifier.core.reels.config import resolve_asset
                    resolve_asset(path.parent, relative)
            self.options.set_rules(rules, path.parent)
            self._settings_changed()
            self._set_feedback(self.tr("Configuration loaded. Review settings before exporting."))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            self._set_feedback(self.tr(
                "Configuration could not be loaded. See processing details.",
            ), error=True)
            self.details_text.setPlainText(str(exc))
            self.details.set_expanded(True)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        if hasattr(self, "safe_preview"):
            self._fit_safe_preview()

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._refresh_controls()

    def shutdown_workers(self, wait_ms: int = 16000) -> bool:
        stopped = super().shutdown_workers(wait_ms)
        if stopped:
            if not self._close_comparison():
                return False
            self.source_preview.shutdown()
            self.review_preview.shutdown()
            self._preview_storage.cleanup()
        return stopped
