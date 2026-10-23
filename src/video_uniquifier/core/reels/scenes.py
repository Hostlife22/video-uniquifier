"""Report source shots and their retained timeline; never rearrange or drop shots."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.runtime import ReelsError, execute
from video_uniquifier.core.runner import CancelToken


def build_timeline(
    boundaries: list[float], duration: float, minimum: float,
    trim_start: float = 0.0, trim_end: float = 0.0,
) -> dict[str, list[dict[str, float | int]]]:
    """Keep unrounded source seconds and map explicit trim onto output coordinates."""
    accepted = [0.0]
    for boundary in sorted(set(boundaries)):
        if boundary - accepted[-1] >= minimum and duration - boundary >= minimum:
            accepted.append(boundary)
    accepted.append(duration)
    source: list[dict[str, float | int]] = []
    output: list[dict[str, float | int]] = []
    for index, (start, end) in enumerate(zip(accepted[:-1], accepted[1:], strict=True), start=1):
        source.append({"scene_id": index, "start_sec": start, "end_sec": end,
                       "duration_sec": end - start})
        kept_start, kept_end = max(start, trim_start), min(end, duration - trim_end)
        if kept_end > kept_start:
            output.append({"scene_id": index, "source_start_sec": kept_start,
                           "source_end_sec": kept_end, "start_sec": kept_start - trim_start,
                           "end_sec": kept_end - trim_start, "duration_sec": kept_end - kept_start})
    return {"source_timeline": source, "output_timeline": output}


def detect_timeline(
    path: Path, duration: float, rules: ReelsRules, work: Path, token: CancelToken,
) -> dict[str, list[dict[str, float | int]]]:
    if importlib.util.find_spec("scenedetect") is None:
        raise ReelsError("scene_dependency", "Scene detection needs the [scene] extra. "
                         "Install video-uniquifier[scene], or explicitly disable "
                         "scenes.detect_enabled.")
    destination = work / "scene-boundaries.json"
    execute([sys.executable, "-m", "video_uniquifier.core.reels.scene_worker", str(path),
             str(rules.scenes.threshold), str(rules.scenes.min_scene_length_sec), str(destination)],
            work / "scenes.log", token, timeout=rules.worker.wall_timeout_sec, progress=False)
    boundaries = json.loads(destination.read_text(encoding="utf-8"))
    return build_timeline(boundaries, duration, rules.scenes.min_scene_length_sec,
                          rules.scenes.trim_start_sec, rules.scenes.trim_end_sec)
