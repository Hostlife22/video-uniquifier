"""Atomic, cancellable saving of a temporary desktop review result."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.runner import CancelToken


def _save_review_sample(
    source: Path, destination: Path, *, protected: tuple[Path, ...],
    token: CancelToken, progress: Callable[[float], None],
) -> Path:
    resolved = destination.resolve()
    if resolved in {path.resolve() for path in (source, *protected)}:
        raise PipelineError("Choose a different file to preserve the original video")
    if destination.exists() and any(
        path.exists() and os.path.samefile(destination, path) for path in (source, *protected)
    ):
        raise PipelineError("Choose a different file to preserve the original video")
    size = source.stat().st_size
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
            temporary = Path(target.name)
            copied = 0
            with source.open("rb") as incoming:
                while True:
                    if token.is_cancelled():
                        raise PipelineError("Saving sample cancelled")
                    chunk = incoming.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    copied += len(chunk)
                    progress(min(copied / max(size, 1), 1))
            target.flush()
            os.fsync(target.fileno())
        if token.is_cancelled():
            raise PipelineError("Saving sample cancelled")
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
