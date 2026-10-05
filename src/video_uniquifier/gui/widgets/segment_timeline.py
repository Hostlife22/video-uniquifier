"""SegmentTimeline — horizontal bar of coloured cells per segment."""

from __future__ import annotations

from typing import Literal

from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

from video_uniquifier.gui.design import Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for

SegmentStatus = Literal["pending", "in_progress", "done", "failed"]

_COLOR_TOKENS = {
    "pending": "border", "in_progress": "accent", "done": "success", "failed": "danger",
}


class SegmentTimeline(QWidget):
    """N coloured cells representing per-segment status.

    Public API:
      init(n_segments)
      update_segment(idx, status)
      reset()
    """

    def __init__(self, state: AppState | None = None) -> None:
        super().__init__()
        self._theme = state.theme if state is not None else "dark"
        if state is not None:
            state.theme_changed.connect(self._on_theme_changed)
        self._statuses: list[SegmentStatus] = []
        self.setFixedHeight(Space.SM)
        self.setAccessibleName("Segment progress")

    def _on_theme_changed(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def init(self, n_segments: int) -> None:
        self._statuses = ["pending"] * n_segments
        self.update()

    def update_segment(self, idx: int, status: SegmentStatus) -> None:
        if 0 <= idx < len(self._statuses):
            self._statuses[idx] = status
            self.update()

    def reset(self) -> None:
        self._statuses = []
        self.update()

    def statuses(self) -> list[SegmentStatus]:
        """Read-only snapshot (test introspection)."""
        return list(self._statuses)

    def paintEvent(self, _event: object) -> None:
        if not self._statuses:
            return
        painter = QPainter(self)
        try:
            w = self.width()
            h = self.height()
            n = len(self._statuses)
            cell_w = w / n
            gap = 1
            for i, status in enumerate(self._statuses):
                x = int(i * cell_w) + gap
                cw = max(2, int(cell_w) - 2 * gap)
                painter.fillRect(
                    x, gap, cw, h - 2 * gap,
                    QColor(tokens_for(self._theme)[_COLOR_TOKENS.get(status, "border")]),
                )
        finally:
            painter.end()
