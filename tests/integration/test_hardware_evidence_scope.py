"""Large inputs must retain structured metadata without dumping every frame."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.hardware_qualification_report import _probe
from tools.media_diagnostics import decoded_timeline


@pytest.mark.integration
def test_hardware_probe_is_bounded_and_keeps_metadata(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe unavailable")
    source = tmp_path / "many-frames.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=64x64:rate=60:duration=20", "-c:v", "libx264",
        "-preset", "ultrafast", str(source),
    ], check=True, capture_output=True, timeout=30)
    report = _probe(source)
    assert "probe" in report
    assert report["probe"]["streams"][0]["codec_name"] == "h264"
    assert 0 < len(report["probe"]["frames"]) < 100
    assert report["scope"]["full_timeline_verified"] is False
    assert report["scope"]["packet_prefix"] == 64


@pytest.mark.integration
def test_timeline_checks_secondary_video_stream(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe unavailable")
    source = tmp_path / "two-video-streams.mkv"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=64x64:rate=12:duration=1", "-map", "0:v", "-map", "0:v",
        "-c:v", "ffv1", str(source),
    ], check=True, capture_output=True, timeout=30)
    streams = decoded_timeline(source)["streams"]
    assert len(streams) == 2
    assert [stream["frames"] for stream in streams] == [12, 12]
    assert {stream["index"] for stream in streams} == {0, 1}
