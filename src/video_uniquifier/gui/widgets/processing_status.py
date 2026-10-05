"""Stage-scoped progress and conservative ETA without invented overall weights."""

from __future__ import annotations

import math
import time

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for

STAGES = ("prepare", "video", "audio", "save", "quality")
STAGE_LABELS = {
    "prepare": "Preparation", "video": "Video", "audio": "Audio",
    "save": "Saving", "quality": "Quality check",
}


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class ProcessingStatus(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.phase: str | None = None
        self.fraction: float | None = None
        self._started = 0.0
        self._phase_started = 0.0
        self._paused_at: float | None = None
        self._paused_total = 0.0
        self._paused_phase = 0.0
        self._last_advance = 0.0
        self._advances = 0
        self._finished_at: float | None = None
        self._success = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        row = QHBoxLayout()
        row.setSpacing(Space.SM)
        self.badges: dict[str, QLabel] = {}
        for stage in STAGES:
            badge = QLabel()
            row.addWidget(badge)
            self.badges[stage] = badge
        row.addStretch(1)
        layout.addLayout(row)
        self.time_label = QLabel()
        self.time_label.setObjectName("hint")
        self.time_label.setWordWrap(True)
        layout.addWidget(self.time_label)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        state.theme_changed.connect(self.refresh)
        self.hide()

    def start(self) -> None:
        self._started = time.monotonic()
        self._paused_total = self._paused_phase = 0.0
        self._paused_at = self._finished_at = None
        self.phase = None
        self._success = False
        self.show()
        self.set_phase("prepare", None)
        self.timer.start()

    def set_phase(self, phase: str, fraction: object) -> None:
        if phase.split(":", 1)[0] not in STAGES:
            return
        now = time.monotonic()
        if phase != self.phase:
            self.phase = phase
            self._phase_started = now
            self._paused_phase = 0.0
            self._last_advance = now
            self._advances = 0
            self.fraction = None
        value = (
            float(fraction) if isinstance(fraction, (int, float))
            and math.isfinite(fraction) else None
        )
        value = min(max(value, 0), 1) if value is not None else None
        if value is not None and (self.fraction is None or value > self.fraction):
            self._last_advance = now
            self._advances += 1
        elif value is not None and self.fraction is not None and value < self.fraction:
            # Retry / analysis-pass reset: an old rate cannot predict new work.
            self._phase_started = now
            self._paused_phase = 0.0
            self._advances = 0
        self.fraction = value
        self.refresh()

    def set_paused(self, paused: bool) -> None:
        now = time.monotonic()
        if paused and self._paused_at is None:
            self._paused_at = now
        elif not paused and self._paused_at is not None:
            pause = now - self._paused_at
            self._paused_total += pause
            self._paused_phase += pause
            self._last_advance = now
            self._paused_at = None
        self.refresh()

    def remaining_seconds(self) -> float | None:
        now = time.monotonic()
        elapsed = now - self._phase_started - self._paused_phase
        if (self._paused_at is not None or self._finished_at is not None
                or self.fraction is None or not 0.03 <= self.fraction < 0.98
                or elapsed < Metrics.ETA_MIN_SECONDS or self._advances < 2
                or now - self._last_advance > Metrics.ETA_STALE_SECONDS):
            return None
        return elapsed * (1 - self.fraction) / self.fraction

    def finish(self, *, success: bool) -> None:
        if self._paused_at is not None:
            self.set_paused(False)
        self._finished_at = time.monotonic()
        self._success = success
        self.timer.stop()
        self.refresh()

    def refresh(self) -> None:
        if self.phase is None:
            return
        stage = self.phase.split(":", 1)[0]
        current = STAGES.index(stage)
        tokens = tokens_for(self.state.theme)
        for index, key in enumerate(STAGES):
            done = self._success or index < current
            color = tokens["accent"] if done or index == current else tokens["fg_dim"]
            self.badges[key].setStyleSheet(f"color: {color};")
            self.badges[key].setText(f"{index + 1} {self.tr(STAGE_LABELS[key])}")
        now = self._finished_at
        if now is None:
            now = self._paused_at if self._paused_at is not None else time.monotonic()
        elapsed = max(0, now - self._started - self._paused_total)
        text = self.tr("Elapsed: {time}").format(time=format_duration(elapsed))
        remaining = self.remaining_seconds()
        if self._paused_at is not None:
            text += "  ·  " + self.tr("Paused")
        elif remaining is not None:
            text += "  ·  " + self.tr("Remaining in this stage: ≈ {time}").format(
                time=format_duration(remaining),
            )
        elif self._finished_at is None:
            text += "  ·  " + self.tr("Estimating stage time…")
        self.time_label.setText(text)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.refresh()
        super().changeEvent(event)
