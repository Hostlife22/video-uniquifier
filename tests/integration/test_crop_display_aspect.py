"""Decoded-output regressions for micro-crop display geometry."""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from video_uniquifier.core.models import EncoderCandidate, Plan, Profile, Segment, TransformConfig
from video_uniquifier.core.pipeline import (
    FilterGraph,
    build_video_segment_command,
    build_video_segment_command_fused,
    compute_plan_hash,
)
from video_uniquifier.core.probe import probe
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin, ffprobe_bin

pytestmark = pytest.mark.integration


def _stream(path: Path) -> dict[str, str | int]:
    result = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,display_aspect_ratio,nb_read_frames",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)["streams"][0]  # type: ignore[no-any-return]


def _source(tmp_path: Path, size: str, sar: str) -> Path:
    source = tmp_path / "source.mkv"
    subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i",
         f"testsrc2=size={size}:rate=24:duration=0.5", "-vf", f"setsar={sar}:max=65535",
         "-c:v", "ffv1", str(source)],
        check=True, capture_output=True, timeout=30,
    )
    return source


def _encode(source: Path, output: Path, transforms: list[TransformConfig], path: str) -> None:
    metadata = probe(source)
    profile = Profile(name="geometry-regression", transforms=transforms)
    encoder = EncoderCandidate(name="libx264", vendor="x264", codec="h264", works=True)
    plan = Plan(
        source=metadata, profile=profile, encoder=encoder, run_seed=11,
        plan_hash=compute_plan_hash(metadata, profile, encoder),
    )
    if path == "whole":
        command = FilterGraph(plan, output).build()
    elif path == "segment":
        command = build_video_segment_command(plan, source, output)
    else:
        command = build_video_segment_command_fused(
            plan, Segment(idx=0, start_sec=0, end_sec=0.5), source, output,
        )
    subprocess.run(command.args, check=True, capture_output=True, timeout=30)


@pytest.mark.parametrize("path", ["whole", "segment", "fused"])
@pytest.mark.parametrize(
    "size,sar,strength,rotate",
    [
        ("320x180", "1/1", 0.025, False),
        ("320x180", "2883/2288", 0.0, False),
        ("320x180", "2883/2288", 0.015, False),
        ("320x180", "2883/2288", 0.025, False),
        ("320x180", "2883/2288", 0.04, True),
        ("720x576", "16/15", 0.04, False),
    ],
)
def test_crop_preserves_source_display_aspect(
    tmp_path: Path, size: str, sar: str, strength: float, rotate: bool, path: str,
) -> None:
    source = _source(tmp_path, size, sar)
    transforms = [TransformConfig(id="video.crop_resize", params={"max_strength": strength})]
    if rotate:
        transforms.append(TransformConfig(id="video.rotate", params={"degrees": 0.2}))
    output = tmp_path / "output.mp4"
    _encode(source, output, transforms, path)
    original, processed = _stream(source), _stream(output)
    original_dar = Fraction(str(original["display_aspect_ratio"]).replace(":", "/"))
    processed_dar = Fraction(str(processed["display_aspect_ratio"]).replace(":", "/"))
    assert float(processed_dar / original_dar) == pytest.approx(1, rel=0.0001)
    assert processed["nb_read_frames"] == original["nb_read_frames"] == "12"
    assert int(processed["width"]) % 2 == int(processed["height"]) % 2 == 0


@pytest.mark.parametrize("path", ["whole", "segment", "fused"])
@pytest.mark.parametrize("mode", ["crop", "pad_black", "pad_blur"])
@pytest.mark.parametrize("sar", ["1/1", "2883/2288"])
def test_crop_preserves_platform_canvas_dimensions(
    tmp_path: Path, mode: str, sar: str, path: str,
) -> None:
    source = _source(tmp_path, "320x180", sar)
    output = tmp_path / "platform.mp4"
    _encode(source, output, [
        TransformConfig(id="video.fit_aspect", params={
            "target_aspect": "16:9", "target_width": 320, "target_height": 180, "mode": mode,
        }),
        TransformConfig(id="video.crop_resize", params={"max_strength": 0.04}),
    ], path)
    stream = _stream(output)
    assert (stream["width"], stream["height"]) == (320, 180)
    assert Fraction(str(stream["display_aspect_ratio"]).replace(":", "/")) == Fraction(16, 9)
    assert stream["nb_read_frames"] == "12"
