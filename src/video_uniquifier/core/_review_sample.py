"""Private, bounded lossless reference extraction for desktop review samples."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.models import Plan, Profile
from video_uniquifier.core.orchestrator import build_plan
from video_uniquifier.core.pipeline import BuiltCommand
from video_uniquifier.core.probe import probe as probe_file
from video_uniquifier.core.runner import CancelToken, RunEvent, run
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin


def _prepare_review_sample(
    source: Path,
    profile: Profile,
    directory: Path,
    *,
    start_sec: float,
    duration_sec: float,
    encoder: str | None = None,
    cancel_token: CancelToken | None = None,
    on_event: Callable[[RunEvent], None] | None = None,
) -> Plan:
    """Cut at the requested decoded time, then use the normal processing plan.

    FFV1 and PCM keep the reference free of another lossy encoding generation.
    Input seeking followed by encoding performs accurate decoder preroll rather
    than extending the selection back to a keyframe. All audio tracks retain
    their shared input timeline; independently resetting their PTS would lose sync.
    """
    if not math.isfinite(start_sec) or start_sec < 0:
        raise PipelineError("Sample start must be a finite nonnegative time")
    if not math.isfinite(duration_sec) or not 0 < duration_sec <= 20:
        raise PipelineError("Review samples must be between 0 and 20 seconds")
    if cancel_token is not None and cancel_token.is_cancelled():
        raise PipelineError("Review sample cancelled by user")
    meta = probe_file(source)
    if not meta.video or start_sec >= meta.duration_sec:
        raise PipelineError("Choose a sample inside the source video")
    # FFV1 preserves samples, but cannot promise HDR mastering/dynamic side-data
    # preservation. Refuse an altered HDR reference rather than misrepresenting it.
    if any(video.color.is_hdr for video in meta.video):
        raise PipelineError("HDR review samples are not supported; use full processing for HDR")
    length = min(duration_sec, meta.duration_sec - start_sec)
    directory.mkdir(parents=True, exist_ok=True)
    reference = directory / "source.mkv"
    args = [
        ffmpeg_bin(), "-hide_banner", "-y", "-ss", f"{start_sec:.9f}",
        "-i", str(source), "-t", f"{length:.9f}",
        "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn",
        "-c:v", "ffv1", "-level", "3", "-threads", "2",
        "-c:a", "pcm_s24le", "-fps_mode", "passthrough",
        "-map_metadata", "0", "-avoid_negative_ts", "make_zero", str(reference),
    ]
    run(
        BuiltCommand(args=args), output=reference, on_event=on_event,
        cancel_token=cancel_token,
    )
    if cancel_token is not None and cancel_token.is_cancelled():
        raise PipelineError("Review sample cancelled by user")
    extracted = probe_file(reference)
    if not extracted.video or extracted.duration_sec <= 0:
        raise PipelineError("The selected sample contains no video frames")
    return build_plan(reference, profile, encoder)
