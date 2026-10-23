from __future__ import annotations

import json

import pytest

from tests.conftest import needs_ffmpeg
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.processor import process_video

pytestmark = [pytest.mark.integration, needs_ffmpeg]


def test_delivery_reuses_native_graph_and_publishes_verified_artifacts(tiny_clip, tmp_path):
    rules = ReelsRules.model_validate({
        "video": {"width": 720, "height": 1280}, "scenes": {"detect_enabled": False},
        "packaging": {"safe_area_preview_enabled": False},
    })
    events = []
    result = process_video(tiny_clip, rules, tmp_path / "jobs", job_id="baseline",
                           on_status=lambda status, progress: events.append((status, progress)))
    report = json.loads((result / "report.json").read_text())
    assert report["quality_check"]["status"] == "passed"
    assert report["output"]["video"][0]["width"] == 720
    assert report["output"]["video"][0]["height"] == 1280
    assert report["output"]["audio"][0]["channels"] == 2
    assert report["selected_audio_stream_index"] == 1
    assert report["audio_normalization"]["status"] == "measured"
    assert report["video_encode_passes"] == 1
    assert report["native_profile"]["transforms"][0]["id"] == "video.fit_aspect"
    assert report["source"]["sha256"] != report["output"]["sha256"]
    assert (result / "output.mp4").is_file()
    assert not (result / "output.tmp.mp4").exists()
    assert events[-1] == ("success", 1.0)
