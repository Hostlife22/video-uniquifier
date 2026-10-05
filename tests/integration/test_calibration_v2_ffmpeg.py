"""Real-FFmpeg smoke coverage for the stratified calibration probe."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from video_uniquifier.core.calibration.intensity import scale_profile
from video_uniquifier.core.calibration.loop import CalibrationTarget, _cut_test_clip, calibrate
from video_uniquifier.core.orchestrator import build_plan
from video_uniquifier.core.probe import probe
from video_uniquifier.core.profile_loader import dump_profile, load_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
        reason="ffmpeg/ffprobe not available",
    ),
]


def _make_source(path: Path, frequency: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24:duration=9",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration=9",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-g",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def test_stratified_probe_is_decodable_cached_and_content_keyed(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    work = tmp_path / "work"
    _make_source(source, 440)

    first = _cut_test_clip(source, work, 3.0)
    first_stat = first.stat()
    first_meta = probe(first)
    assert first_meta.video
    assert first_meta.audio
    # AAC priming and stream-copy keyframe boundaries add a small container
    # tail; they must not turn the three-second budget into three full clips.
    assert 2.5 <= first_meta.duration_sec <= 3.5

    cached = _cut_test_clip(source, work, 3.0)
    assert cached == first
    assert cached.stat().st_mtime_ns == first_stat.st_mtime_ns

    # Same path and duration but changed head/tail content must not reuse the
    # previous representative probe.
    _make_source(source, 880)
    replaced = _cut_test_clip(source, work, 3.0)
    assert replaced != first
    assert replaced.is_file()


@pytest.mark.parametrize("profile_name", ["soft", "cid_aware", "cid_aggressive"])
def test_actual_profile_search_persistence_and_scored_resume(
    tmp_path: Path, isolated_cache: Path, profile_name: str,
) -> None:
    source = tmp_path / "source.mp4"
    _make_source(source, 440)
    path = Path(__file__).parents[2] / "src/video_uniquifier/profiles" / f"{profile_name}.yaml"
    profile = load_profile(path)
    target = CalibrationTarget(
        test_clip_sec=9., max_iterations=4, min_factor=.7, max_factor=1.5,
        max_self_match=1., min_quality=0., seed=17,
    )
    result = calibrate(source, profile, target, work_dir=tmp_path / "calibration",
                       encoder_override="libx264")
    assert result.converged
    assert len(result.steps) == 4
    assert {step.quality_metric for step in result.steps} == {"vmaf"}
    effective = tmp_path / "effective.yaml"
    dump_profile(result.profile, effective)
    assert load_profile(effective) == result.profile
    resumed = calibrate(source, profile, target, work_dir=tmp_path / "calibration",
                        encoder_override="libx264")
    assert resumed.factor == result.factor
    assert resumed.final_self_match == result.final_self_match
    assert all("cache hit" in (step.note or "") for step in resumed.steps)


@pytest.mark.parametrize(
    "path", sorted((Path(__file__).parents[2] / "src/video_uniquifier/profiles").glob("*.yaml")),
    ids=lambda path: path.stem,
)
def test_all_shipped_profiles_reach_actual_plan(path, tiny_clip, isolated_cache) -> None:
    profile = scale_profile(load_profile(path), .75)
    encoder = {"h264": "libx264", "hevc": "libx265", "av1": "libaom-av1"}[profile.target_codec]
    plan = build_plan(tiny_clip, profile, encoder_override=encoder)
    assert plan.profile == profile
