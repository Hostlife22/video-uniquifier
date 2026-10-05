"""Desktop asset workers; core owns decoding and saving."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal

from video_uniquifier.core._review_export import _save_review_sample
from video_uniquifier.core._review_images import _review_thumbnails
from video_uniquifier.gui.workers.base import WorkerBase


class ThumbnailWorker(WorkerBase):
    thumbnail = pyqtSignal(object, float, bytes)

    def __init__(self, source: Path, duration: float) -> None:
        super().__init__()
        self.source = source
        self.duration = duration

    def run(self) -> None:
        try:
            for stamp, png in _review_thumbnails(self.source, self.duration, self.cancel_token):
                self.thumbnail.emit(self.source, stamp, png)
        except Exception as exc:
            if not self.cancel_token.is_cancelled():
                self.failed.emit(str(exc))


class SaveSampleWorker(WorkerBase):
    cancelled = pyqtSignal()

    def __init__(self, source: Path, destination: Path, protected: tuple[Path, ...]) -> None:
        super().__init__()
        self.source = source
        self.destination = destination
        self.protected = protected

    def run(self) -> None:
        try:
            result = _save_review_sample(
                self.source, self.destination, protected=self.protected,
                token=self.cancel_token, progress=lambda fraction: self.progress.emit(fraction, ""),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            if self.cancel_token.is_cancelled():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))
