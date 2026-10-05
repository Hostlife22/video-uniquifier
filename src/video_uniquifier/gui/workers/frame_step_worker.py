"""Decode only nearby frame metadata away from the GUI thread."""

from __future__ import annotations

from pathlib import Path

from video_uniquifier.core._review_frames import _review_frame_window
from video_uniquifier.gui.workers.base import WorkerBase


class FrameStepWorker(WorkerBase):
    def __init__(self, path: Path, position_sec: float) -> None:
        super().__init__()
        self.path = path
        self.position_sec = position_sec

    def run(self) -> None:
        try:
            frames = _review_frame_window(self.path, self.position_sec, self.cancel_token)
            self.finished_ok.emit(frames)
        except Exception as exc:
            self.failed.emit(str(exc))
