"""Private bounded frame decoding for the desktop filmstrip."""
from __future__ import annotations

import math
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin


def _review_thumbnails(
    source: Path, duration_sec: float, token: CancelToken,
) -> Iterator[tuple[float, bytes]]:
    if not math.isfinite(duration_sec) or duration_sec <= 0:
        raise PipelineError("Invalid thumbnail duration")
    deadline = time.monotonic() + 25
    for index in range(5):
        if token.is_cancelled() or time.monotonic() >= deadline:
            raise PipelineError("Thumbnail preparation cancelled or timed out")
        stamp = max(0, duration_sec - 0.1) * index / 4
        args = [
            ffmpeg_bin(), "-v", "error", "-nostdin", "-ss", f"{stamp:.6f}",
            "-threads", "2", "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn",
            "-frames:v", "1", "-vf",
            "scale=160:90:force_original_aspect_ratio=decrease,"
            "pad=160:90:(ow-iw)/2:(oh-ih)/2", "-threads", "1",
            "-f", "image2pipe", "-c:v", "png", "pipe:1",
        ]
        with subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) as process:
            while True:
                if token.is_cancelled() or time.monotonic() >= deadline:
                    process.kill()
                    process.communicate(timeout=2)
                    raise PipelineError("Thumbnail preparation cancelled or timed out")
                try:
                    png, errors = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode or not png:
                raise PipelineError(errors.decode(errors="replace")[-1000:])
        yield stamp, png
