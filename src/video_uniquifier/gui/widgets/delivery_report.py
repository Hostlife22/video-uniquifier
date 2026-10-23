"""Human-readable delivery report using the existing core's measured results."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.design import Space

FAILURE_LABELS = {
    "missing_video": "Video decode check", "decode_failed": "Video decode check",
    "video_format": "Output format", "display_aspect": "Aspect ratio",
    "sample_aspect": "Aspect ratio", "sdr_rec709": "Framing & color",
    "frame_rate": "Frame rate", "container": "Output format", "faststart": "Fast start",
    "duration": "Duration", "audio_count": "Audio channels", "audio_format": "Audio format",
    "audio_profile": "Audio format", "av_timing": "Audio/video synchronization",
    "loudness_unverified": "Integrated loudness", "audio_clipping": "Measured true peak",
    "loudness_target": "Integrated loudness", "true_peak_target": "Measured true peak",
}


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(value: object) -> dict[str, Any]:
    return _object(value[0]) if isinstance(value, list) and value else {}


class DeliveryReportDialog(QDialog):
    """Read-only comparison of source/export metadata, checks and editorial choices."""

    def __init__(self, report: dict[str, Any], *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report = deepcopy(report)
        self.resize(900, 700)
        self.setMinimumSize(600, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        layout.setSpacing(Space.MD)
        self.title = self._label("", layout)
        self.title.setObjectName("title")
        self.context = self._label(str(_object(report.get("source")).get("filename", "")), layout)
        self.context.setObjectName("hint")
        self.summary = self._label("", layout)
        self.tabs = QTabWidget()
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        self.comparison = self._table(overview_layout)
        self.changes = self._label("", overview_layout)
        self.tabs.addTab(overview, "")
        checks = QWidget()
        checks_layout = QVBoxLayout(checks)
        self.checks = self._table(checks_layout)
        notices_scroll = QScrollArea()
        notices_scroll.setWidgetResizable(True)
        notices_scroll.setMinimumHeight(0)
        notices_scroll.setMaximumHeight(140)
        notices_body = QWidget()
        self.notices = self._label("", QVBoxLayout(notices_body))
        notices_scroll.setWidget(notices_body)
        checks_layout.addWidget(notices_scroll)
        self.tabs.addTab(checks, "")
        layout.addWidget(self.tabs, stretch=1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.close)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)
        self._render()

    @staticmethod
    def _label(text: str, layout: QVBoxLayout) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    @staticmethod
    def _table(layout: QVBoxLayout) -> QTableWidget:
        table = QTableWidget()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setWordWrap(True)
        table.setMinimumHeight(0)
        vertical = table.verticalHeader()
        if vertical is not None:
            vertical.hide()
            vertical.setDefaultSectionSize(42)
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, stretch=1)
        return table

    def _number(self, value: object, unit: str, *, divisor: float = 1, digits: int = 2) -> str:
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value)):
            return self.tr("Not measured")
        return f"{value / divisor:.{digits}f} {self.tr(unit)}".strip()

    def _status(self, value: object) -> str:
        labels = {
            "passed": "Passed", "failed": "Failed", "manual_required": "Manual review needed",
            "not_computed": "Not measured", "disabled": "Disabled", "missing": "No audio track",
            "silent": "Silent audio", "detected": "Detected",
        }
        return self.tr(labels.get(str(value), "Not measured"))

    def _metadata(self, media: dict[str, Any], *, source: bool) -> list[str]:
        video = _first(media.get("video"))
        audio = _first(media.get("audio"))
        unknown = self.tr("Not measured")
        width, height = video.get("width"), video.get("height")
        resolution = (f"{width} × {height}" if isinstance(width, int) and width > 0
                      and isinstance(height, int) and height > 0 else unknown)
        if source:
            normalization = _object(self._report.get("audio_normalization"))
            loudness = _object(normalization.get("measurement")).get("input_i")
        else:
            quality = _object(self._report.get("quality_check"))
            loudness = _first(_object(quality.get("loudness")).get("streams")).get(
                "integrated_lufs",
            )
        no_audio = media.get("audio") == []
        audio_values = [self._number(loudness, "LUFS"),
                        self._number(audio.get("sample_rate"), "kHz", divisor=1000, digits=1),
                        self._number(audio.get("bit_rate"), "kbps", divisor=1000, digits=0),
                        self._number(audio.get("channels"), "", digits=0)]
        return [resolution, self._number(video.get("fps"), "fps"),
                self._number(media.get("duration_sec"), "s", digits=3),
                str(video["codec"]).upper() if video.get("codec") else unknown,
                self._number(video.get("bit_rate"), "Mbps", divisor=1_000_000),
                self._number(media.get("size_bytes"), "MB", divisor=1_000_000, digits=1),
                *([self.tr("No audio track")] * 4 if no_audio else audio_values)]

    def _fill(self, table: QTableWidget, headers: list[str], rows: list[tuple[str, ...]]) -> None:
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels([self.tr(header) for header in headers])
        table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))

    def _packaging_status(self, packaging: dict[str, Any], key: str) -> str:
        enabled = packaging.get("enabled")
        option = _object(packaging.get(key)).get("enabled")
        if enabled is False or option is False:
            return self.tr("Disabled")
        return self.tr("Enabled" if enabled is True and option is True else "Not measured")

    def _render(self) -> None:
        self.setWindowTitle(self.tr("Delivery quality report"))
        self.title.setText(self.tr("Delivery quality report"))
        self.close_btn.setText(self.tr("Close"))
        self.tabs.setTabText(0, self.tr("Before / after"))
        self.tabs.setTabText(1, self.tr("Checks & notices"))
        report = self._report
        quality = _object(report.get("quality_check"))
        self.summary.setText(self.tr("Technical QA: {status}").format(
            status=self._status(quality.get("status"))))
        labels = ["Resolution", "Frame rate", "Duration", "Video codec", "Video bitrate",
                  "File size", "Integrated loudness", "Audio sample rate", "Audio bitrate",
                  "Audio channels"]
        before = self._metadata(_object(report.get("source")), source=True)
        after = self._metadata(_object(report.get("output")), source=False)
        self._fill(self.comparison, ["Item", "Original video", "Processed video"], [
            (self.tr(label), first, second)
            for label, first, second in zip(labels, before, after, strict=True)
        ])
        self.comparison.setAccessibleName(self.tr("Original and processed video measurements"))
        timing = _object(quality.get("timing"))
        faststart = quality.get("faststart")
        checks = [
            ("Video decode check", self._status(quality.get("decode"))),
            ("Fast start", self.tr("Passed") if faststart is True else
             self.tr("Failed") if faststart is False else self.tr("Not measured")),
            ("Duration difference", self._number(quality.get("duration_delta_sec"), "s", digits=3)),
            ("Start A/V drift", self._number(timing.get("start_drift_ms"), "ms")),
            ("End A/V drift", self._number(timing.get("end_drift_ms"), "ms")),
            ("Measured true peak", self._number(
                _first(_object(quality.get("loudness")).get("streams")).get("true_peak_dbtp"),
                "dBTP")),
            ("Listening review", self._status(quality.get("listening_review"))),
            ("Subtitle review", self._status(quality.get("subtitle_review"))),
            ("Visual similarity", self._status(
                _object(quality.get("visual_similarity")).get("status"))),
        ]
        self._fill(self.checks, ["Check", "Result"], [
            (self.tr(label), value) for label, value in checks
        ])
        self.checks.setAccessibleName(self.tr("Technical checks and manual review"))
        rules = _object(report.get("effective_rules"))
        scenes = _object(rules.get("scenes"))
        packaging = _object(rules.get("packaging"))
        self.changes.setText(self.tr(
            "Trim: start {start}, end {end}. Title: {title}. Logo: {logo}.",
        ).format(
            start=self._number(scenes.get("trim_start_sec"), "s"),
            end=self._number(scenes.get("trim_end_sec"), "s"),
            title=self._packaging_status(packaging, "title"),
            logo=self._packaging_status(packaging, "logo"),
        ) + "\n" + self.tr("A larger file does not imply sharper picture quality."))
        warnings = report.get("warnings")
        failures = quality.get("failures")
        notices = [self.tr("Review dialogue and subtitles before delivery.")]
        if isinstance(failures, list):
            notices.extend(self.tr("Failed") + ": " + self.tr(
                FAILURE_LABELS.get(value, "Technical checks and manual review"),
            ) for value in failures if isinstance(value, str))
        if isinstance(warnings, list):
            notices.extend(self.tr(value) for value in warnings if isinstance(value, str))
        self.notices.setText("\n".join(notices))

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._render()
        super().changeEvent(event)
