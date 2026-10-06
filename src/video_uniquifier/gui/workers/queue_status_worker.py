"""Polls FileQueue.stats() periodically and emits stats dict."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal

from video_uniquifier.core.queue.leasing import FileQueue
from video_uniquifier.gui.workers.base import WorkerBase


class QueueStatusWorker(WorkerBase):
    """Long-running poller — emits stats every `poll_sec` until cancelled."""

    stats = pyqtSignal(dict)              # {"pending": N, "in_progress": N, ...}
    files = pyqtSignal(object)             # tuple[(path, bucket)] for presentation only

    def __init__(self, root: Path, *, poll_sec: float = 2.0) -> None:
        super().__init__()
        self.root = root
        self.poll_sec = poll_sec

    def run(self) -> None:
        if not (self.root / "pending").exists():
            self.failed.emit(
                f"queue not initialised at {self.root} "
                "(run `video-uniq queue init` or use the Init button)",
            )
            return
        try:
            q = FileQueue(self.root)
        except Exception as exc:
            self.failed.emit(f"queue not initialised: {exc}")
            return

        while not self.cancel_token.is_cancelled():
            try:
                s = q.stats()
                self.stats.emit(dict(s))
                rows: list[tuple[str, str]] = []
                for bucket in ("pending", "in_progress", "done", "failed"):
                    directory = getattr(q.layout, bucket)
                    for path in directory.iterdir():
                        if self.cancel_token.is_cancelled():
                            break
                        candidates = path.iterdir() if path.is_dir() else (path,)
                        for candidate in candidates:
                            if self.cancel_token.is_cancelled():
                                break
                            if (candidate.is_file() and not candidate.name.startswith(".")
                                    and not candidate.name.endswith((".alive", ".err.txt"))):
                                rows.append((str(candidate), bucket))
                if not self.cancel_token.is_cancelled():
                    self.files.emit(tuple(sorted(rows)))
            except Exception as exc:
                self.log.emit(f"stats error: {exc}")
            # cancel_token.wait blocks on the underlying threading.Event,
            # so cancel wakes the thread immediately — no 100 ms wakeup
            # latency, no 10 Hz spin. Returns True if cancelled within
            # the timeout, in which case we exit promptly.
            if self.cancel_token.wait(self.poll_sec):
                return
