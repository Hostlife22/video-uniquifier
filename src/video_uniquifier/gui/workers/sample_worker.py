"""Prepare a bounded reference; encoding stays in the existing RunWorker."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal

from video_uniquifier.core._review_sample import _prepare_review_sample
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.core.runner import RunEvent
from video_uniquifier.gui.workers.base import WorkerBase


class SampleWorker(WorkerBase):
    cancelled = pyqtSignal()
    stage_progress = pyqtSignal(str, object)

    def __init__(
        self, source: Path, profile: Path, directory: Path,
        start_sec: float, duration_sec: float, encoder: str | None,
    ) -> None:
        super().__init__()
        self.source = source
        self.profile = profile
        self.directory = directory
        self.start_sec = start_sec
        self.duration_sec = duration_sec
        self.encoder = encoder

    def _on_event(self, event: RunEvent) -> None:
        if event.kind == "progress":
            raw = event.payload.get("out_time_us")
            try:
                fraction = min(max(int(str(raw)) / (self.duration_sec * 1_000_000), 0), 1)
            except (ValueError, TypeError):
                fraction = None
            self.stage_progress.emit("prepare", fraction)

    def run(self) -> None:
        try:
            self.stage_progress.emit("prepare", None)
            plan = _prepare_review_sample(
                self.source, load_profile(self.profile), self.directory,
                start_sec=self.start_sec, duration_sec=self.duration_sec, encoder=self.encoder,
                cancel_token=self.cancel_token, on_event=self._on_event,
            )
            if self.cancel_token.is_cancelled():
                self.cancelled.emit()
                return
            self.stage_progress.emit("prepare", None)
            self.finished_ok.emit(plan)
        except Exception as exc:
            if self.cancel_token.is_cancelled():
                self.cancelled.emit()
            else:
                self.failed.emit(f"{type(exc).__name__}: {exc}")
