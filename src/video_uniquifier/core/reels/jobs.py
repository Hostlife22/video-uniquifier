"""Bounded local job lifecycle, independent of HTTP and external queue vendors."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from video_uniquifier import __version__
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.processor import process_video
from video_uniquifier.core.reels.runtime import ReelsError, atomic_json, json_object
from video_uniquifier.core.runner import CancelToken

TERMINAL = frozenset({"success", "failed", "cancelled"})


class JobManager:
    def __init__(self, root: Path, presets: dict[str, ReelsRules], asset_root: Path,
                 *, max_pending_jobs: int = 32) -> None:
        if not presets or max_pending_jobs < 1:
            raise ValueError("presets and positive queue capacity are required")
        self.root = root.resolve()
        self.asset_root = asset_root.resolve()
        self.presets = {key: value.model_copy(deep=True) for key, value in presets.items()}
        self.max_pending_jobs = max_pending_jobs
        self.uploads = self.root / "uploads"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, CancelToken] = {}
        self._futures: dict[str, Future[None]] = {}
        self._inputs: dict[str, tuple[Path, ReelsRules]] = {}
        capacity = min(p.worker.max_cpu_jobs for p in presets.values())
        self._pool = ThreadPoolExecutor(max_workers=capacity, thread_name_prefix="reels")
        self._closed = False
        self._restore()

    def _restore(self) -> None:
        store = self.root / "jobs.json"
        if not store.exists():
            return
        raw = json_object(store)
        for item in raw.get("jobs", [])[-1000:]:
            identifier = item.get("job_id")
            if not isinstance(identifier, str) or len(identifier) != 32:
                continue
            if item.get("status") not in TERMINAL:
                item.update(status="failed", error={"code": "worker_restarted",
                            "message": "Worker restarted before publication; submit a new job."})
            self._records[identifier] = item

    def _save(self) -> None:
        # The durable queue belongs to BullMQ; local terminal records survive a
        # restart and are bounded. Deployment uses a single API process.
        records = sorted(self._records.values(), key=lambda r: r["updated_at"])[-1000:]
        atomic_json(self.root / "jobs.json", {"jobs": records})

    def submit(self, source: Path, rules: ReelsRules, *, job_id: str | None = None) -> str:
        if not source.resolve().is_relative_to(self.uploads) or source.is_symlink():
            raise ReelsError("input_path", "Uploaded input must stay inside the upload root.")
        identifier = job_id or uuid4().hex
        if len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
            raise ReelsError("job_id", "API job ids must be 32 hexadecimal characters.")
        with self._lock:
            if self._closed:
                raise ReelsError("worker_closed", "Worker is shutting down.")
            if identifier in self._records:
                raise ReelsError("job_exists", "Job id already exists.")
            active = sum(record["status"] not in TERMINAL for record in self._records.values())
            if active >= self.max_pending_jobs:
                raise ReelsError("queue_full", "Local job queue is full; retry later.",
                                 retryable=True)
            snapshot = rules.model_copy(deep=True)
            self._inputs[identifier] = (source, snapshot)
            self._tokens[identifier] = CancelToken()
            self._records[identifier] = {
                "job_id": identifier, "preset_id": snapshot.preset_id, "status": "queued",
                "progress": 0.0, "error": None, "cancel_requested": False,
                "created_at": time.time(), "updated_at": time.time(),
                "output_url": None, "report_url": f"/api/video-jobs/{identifier}/report",
            }
            self._save()
            self._futures[identifier] = self._pool.submit(self._run, identifier)
        return identifier

    def _update(self, identifier: str, state: str, progress: float) -> None:
        with self._lock:
            record = self._records[identifier]
            record.update(status=state, progress=max(record["progress"], progress),
                          updated_at=time.time())
            if state == "success":
                record["output_url"] = f"/api/video-jobs/{identifier}/files/output.mp4"
            self._save()

    def _run(self, identifier: str) -> None:
        source, rules = self._inputs[identifier]
        try:
            process_video(source, rules, self.root, job_id=identifier, asset_root=self.asset_root,
                          cancel_token=self._tokens[identifier],
                          on_status=lambda state, progress: self._update(
                              identifier, state, progress))
        except Exception as exc:
            error = exc if isinstance(exc, ReelsError) else ReelsError("worker_failed", str(exc))
            with self._lock:
                record = self._records[identifier]
                record.update(status="cancelled" if error.code == "cancelled" else "failed",
                              error={"code": error.code, "message": str(error),
                                     "retryable": error.retryable}, updated_at=time.time())
                failure = self.root / "failures" / f"{identifier}.json"
                if not failure.exists():
                    atomic_json(failure, {"job_id": identifier, "preset_id": rules.preset_id,
                                         "engine_version": __version__, "source": None,
                                         "output": None, "warnings": [], "quality_check": None,
                                         "status": record["status"], "error": record["error"]})
                self._save()

    def snapshot(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            if identifier not in self._records:
                raise KeyError(identifier)
            return {**self._records[identifier]}

    def cancel(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(identifier)
            if record is None:
                raise KeyError(identifier)
            if record["status"] not in TERMINAL:
                record["cancel_requested"] = True
                self._tokens[identifier].cancel()
                if self._futures[identifier].cancel():
                    record.update(status="cancelled", error={"code": "cancelled",
                                  "message": "Queued task cancelled before processing."})
                    rules = self._inputs[identifier][1]
                    atomic_json(self.root / "failures" / f"{identifier}.json", {
                        "job_id": identifier, "preset_id": rules.preset_id,
                        "engine_version": __version__, "source": None, "output": None,
                        "warnings": [], "quality_check": None, "status": "cancelled",
                        "error": record["error"],
                    })
                record["updated_at"] = time.time()
                self._save()
            return self.snapshot(identifier)

    def retry(self, identifier: str) -> str:
        with self._lock:
            record = self.snapshot(identifier)
            if record["status"] not in {"failed", "cancelled"}:
                raise ReelsError("retry_state", "Only failed or cancelled tasks can be retried.")
            if identifier not in self._inputs:
                raise ReelsError("retry_upload", "Upload the source again after a worker restart.")
            source, rules = self._inputs[identifier]
            return self.submit(source, rules)

    def report_path(self, identifier: str) -> Path:
        record = self.snapshot(identifier)
        if record["status"] not in TERMINAL:
            raise ReelsError("report_pending", "Report is available when processing terminates.")
        if record["status"] == "success":
            return self.root / "results" / identifier / "report.json"
        return self.root / "failures" / f"{identifier}.json"

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for identifier in self._tokens:
                if self._records[identifier]["status"] not in TERMINAL:
                    self.cancel(identifier)
        self._pool.shutdown(wait=True, cancel_futures=True)
