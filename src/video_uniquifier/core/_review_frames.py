"""Private, cancellable nearby frame timestamps for native review stepping."""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.utils.ffmpeg_paths import ffprobe_bin


def _capture(args: list[str], token: CancelToken, deadline: float) -> str:
    if token.is_cancelled():
        raise PipelineError("Frame lookup cancelled")
    with subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) as process:
        while True:
            if token.is_cancelled() or time.monotonic() >= deadline:
                process.kill()
                process.communicate(timeout=2)
                raise PipelineError("Frame lookup cancelled or timed out")
            try:
                output, errors = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise PipelineError(errors.decode(errors="replace")[-2000:])
        return output.decode()


def _review_frame_window(
    path: Path, position_sec: float, cancel_token: CancelToken,
) -> tuple[float, ...]:
    """Read a nearby interval, never index an entire film before reviewing it.

    Container-origin offsets are removed to match the media player's timeline.
    Seeking semantics differ among demuxers, so an offset-origin retry is allowed
    within the same ten-second deadline if the first window misses the position.
    """
    if not math.isfinite(position_sec) or position_sec < 0:
        raise PipelineError("Invalid frame position")
    deadline = time.monotonic() + 10
    origin = 0.0
    frames: tuple[float, ...] = ()
    for attempt in range(2):
        offset = origin if attempt else 0
        start = max(0, position_sec - 2 + offset)
        end = position_sec + 2 + offset
        output = _capture([
            ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
            # An absolute endpoint reaches the target even when seeking lands
            # on a much earlier keyframe in a long GOP. A relative +8 endpoint
            # would stop before the requested position in that case.
            "-read_intervals", f"{start:.9f}%{end:.9f}", "-show_frames", "-show_format",
            "-show_entries", "frame=best_effort_timestamp_time:format=start_time",
            "-of", "json", str(path),
        ], cancel_token, deadline)
        data = json.loads(output)
        if not isinstance(data, dict):
            raise PipelineError("Invalid frame metadata")
        metadata = data.get("format", {})
        try:
            origin = float(metadata.get("start_time", 0))
        except (ValueError, TypeError, AttributeError):
            origin = 0.0
        values: list[float] = []
        for frame in data.get("frames", []):
            try:
                timestamp = float(frame["best_effort_timestamp_time"]) - origin
            except (KeyError, ValueError, TypeError):
                continue
            if math.isfinite(timestamp) and timestamp >= -0.001:
                values.append(max(0, timestamp))
        frames = tuple(sorted(set(values)))
        if frames and frames[0] <= position_sec + 0.001 and frames[-1] >= position_sec:
            return frames
        if abs(origin) < 0.001:
            break
    raise PipelineError("No nearby video frames; use the timeline to seek")
