"""QA must retain hashes, not movie-sized decoded frame lists."""
import io
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.qa import cid_predict, phash


def test_long_predict_caps_prefix_and_reports_unmeasured_tail(monkeypatch):
    monkeypatch.setattr(phash, "_probe_duration", lambda _path: 10823.99)
    calls = []

    def hashes(path, start, span, n):
        assert start == 0.0 and span == 600.0
        calls.append((path, n))
        return [0] * n

    def forbidden(*args, **kwargs):
        pytest.fail("long-form prediction retained decoded image lists")

    monkeypatch.setattr(phash, "_sample_hashes_range", hashes, raising=False)
    monkeypatch.setattr(phash, "sample_frames", forbidden)
    monkeypatch.setattr(cid_predict, "_full_fingerprint", lambda _path: [])
    result = cid_predict.predict(Path("input"), Path("output"))
    assert [n for _, n in calls] == [600, 600]
    assert len(result.chunks) == 150
    assert all(chunk.visual_similarity == 1 for chunk in result.chunks)
    assert result.chunks[-1].end_sec == 600.0
    assert any("tail unmeasured" in note for note in result.notes)


def test_frame_cache_enforces_bytes_and_evicts_oldest(monkeypatch):
    phash.clear_frame_cache()
    monkeypatch.setattr(phash, "_FRAME_CACHE_MAX_BYTES", 1024)
    frames = [Image.new("RGB", (16, 16))]
    a, b = ("a", 1, 1, 1), ("b", 1, 1, 1)
    try:
        phash._cache_frames(a, frames)
        phash._cache_frames(b, frames)
        assert list(phash._FRAME_CACHE) == [b]
        phash._cache_frames(("large", 1, 1, 1), frames * 2)
        assert list(phash._FRAME_CACHE) == [b]
    finally:
        phash.clear_frame_cache()


def test_stream_parser_matches_legacy_pixels():
    images = [Image.new("RGB", (64, 32), color) for color in ("red", "green", "blue")]
    stream = io.BytesIO()
    for image in images:
        image.save(stream, format="PNG")
    blob = stream.getvalue()
    streamed = list(phash._iter_png_frames(io.BytesIO(blob)))
    legacy = phash._split_png_stream(blob)
    assert [item.tobytes() for item in streamed] == [item.tobytes() for item in legacy]


@pytest.mark.parametrize("blob", [
    b"wrongpng", b"\x89PNG\r\n\x1a\n\0", b"\x89PNG\r\n\x1a\n\xff\xff\xff\xffIDAT",
])
def test_stream_parser_rejects_corruption_and_oversize(blob):
    with pytest.raises(PipelineError):
        list(phash._iter_png_frames(io.BytesIO(blob)))


@pytest.mark.parametrize("script, message", [
    ("import os,time; os.write(1,b'badbytes'); time.sleep(30)", "invalid QA PNG"),
    ("import sys; sys.stderr.write('decoder failed'); sys.exit(7)", "decoder failed"),
])
def test_streaming_failure_reaps_decoder(monkeypatch, script, message):
    real_popen = subprocess.Popen
    children = []

    def launch(_command, **kwargs):
        child = real_popen([sys.executable, "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(phash, "_probe_duration", lambda _path: 1000.0)
    monkeypatch.setattr(phash.subprocess, "Popen", launch)
    with pytest.raises(PipelineError, match=message):
        phash._sample_hashes(Path("unused.mp4"), 601)
    assert len(children) == 1
    assert children[0].poll() is not None
