"""Small shared adapters to the existing cancellable process runner."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from video_uniquifier.core.errors import PipelineError, VideoUniquifierError
from video_uniquifier.core.pipeline import BuiltCommand
from video_uniquifier.core.runner import CancelToken, RunEvent, run


class ReelsError(VideoUniquifierError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def check_cancel(token: CancelToken) -> None:
    if token.is_cancelled():
        raise ReelsError("cancelled", "Task cancelled by the user.")


def confined_path(root: Path, path: Path) -> Path:
    """Resolve symlinks and reject paths outside the caller's trusted storage root."""
    root = root.resolve()
    path = path.resolve()
    if not path.is_relative_to(root) or path == root:
        raise ReelsError("storage_path", "Storage path must stay inside the configured root.")
    return path


def atomic_json(path: Path, value: object, *, root: Path) -> None:
    path = confined_path(root, path)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def content_hash(path: Path, token: CancelToken) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            check_cancel(token)
            digest.update(block)
    return digest.hexdigest()


def execute(
    args: list[str], log: Path, token: CancelToken, *, timeout: float = 14400,
    on_event: Callable[[RunEvent], None] | None = None, progress: bool = True,
) -> str:
    check_cancel(token)
    try:
        run(BuiltCommand(args=args), output=Path(args[-1]), log_path=log,
            cancel_token=token, on_event=on_event, progress_via_stdout=progress,
            wall_timeout_sec=timeout)
    except PipelineError as exc:
        check_cancel(token)
        raise ReelsError("process_failed", str(exc), retryable=True) from exc
    check_cancel(token)
    return log.read_text(encoding="utf-8", errors="replace")


def json_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value
