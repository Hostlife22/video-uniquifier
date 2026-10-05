"""Offset MP4 duration differs between ffprobe 5.1 and later releases."""

from pathlib import Path

import pytest

from video_uniquifier.core.probe import _parse


@pytest.mark.parametrize("reported_duration", ["10.000000", "5.021333"])
def test_offset_mp4_duration_is_presentation_span(reported_duration: str) -> None:
    raw = {
        "format": {"format_name": "mov,mp4", "start_time": "4.978667",
                   "duration": reported_duration},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 160,
             "height": 90, "start_time": "5.000000", "duration": "5.000000",
             "r_frame_rate": "24/1", "avg_frame_rate": "24/1", "pix_fmt": "yuv420p"},
            {"index": 1, "codec_type": "audio", "codec_name": "aac",
             "start_time": "4.978667", "duration": "5.021333", "sample_rate": "48000",
             "channels": 1, "channel_layout": "mono"},
        ],
    }
    assert _parse(raw, Path("offset.mp4")).duration_sec == pytest.approx(5.021333)


@pytest.mark.parametrize("stream", [
    {"start_time": "5.0"},
    {"start_time": "5.0", "duration": "N/A"},
    {"start_time": "nan", "duration": "5.0"},
    {"start_time": "5.0", "duration": "inf"},
    {"start_time": "5.0", "duration": "4.0"},
])
def test_incomplete_or_disagreeing_stream_bounds_do_not_guess_duration(stream) -> None:
    raw = {
        "format": {"format_name": "mov,mp4", "start_time": "5.0", "duration": "10.0"},
        "streams": [{"index": 0, "codec_type": "video", "width": 160, "height": 90,
                     "r_frame_rate": "24/1", **stream}],
    }
    assert _parse(raw, Path("offset.mp4")).duration_sec == 10.0
