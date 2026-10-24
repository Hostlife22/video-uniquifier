"""Small shared adapters to the existing cancellable process runner."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

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


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
                             encoding="utf-8")
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
