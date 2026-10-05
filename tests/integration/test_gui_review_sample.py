"""Real media evidence for lossless reference cuts and native comparison transport."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from video_uniquifier.core.models import Profile

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("close_immediately", [False, True])
def test_missing_media_error_and_early_close_are_safe(qtbot, tmp_path, close_immediately):
    from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
    dialog = VideoCompareDialog(tmp_path / "missing.mp4")
    qtbot.addWidget(dialog)
    if not close_immediately:
        qtbot.waitUntil(lambda: dialog._has_error, timeout=5000)
        assert "Could not play" in dialog.message.text()
    assert dialog.close()
    qtbot.wait(100)
    assert dialog._closed and not dialog.timer.isActive() and not dialog.wipe_timer.isActive()


def test_filmstrip_decodes_five_bounded_png_frames(tiny_clip):
    from PyQt6.QtGui import QImage

    from video_uniquifier.core._review_images import _review_thumbnails
    from video_uniquifier.core.runner import CancelToken
    frames = list(_review_thumbnails(tiny_clip, 2, CancelToken()))
    assert len(frames) == 5
    assert frames[0][0] == 0 and frames[-1][0] == pytest.approx(1.9)
    for _stamp, png in frames:
        image = QImage.fromData(png, "PNG")
        assert image.width() == 160 and image.height() == 90


def test_real_media_wipe_decodes_and_refreshes_after_seeking(qtbot, tiny_clip):
    from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
    dialog = VideoCompareDialog(tiny_clip, tiny_clip)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.view_combo.setCurrentIndex(dialog.view_combo.findData("wipe"))
    qtbot.waitUntil(lambda: all(not image.isNull() for image in dialog.wipe.images), timeout=20000)
    before = dialog.wipe.images[1].copy()
    dialog.seek(1200)
    qtbot.waitUntil(lambda: dialog._frame_times[1] >= 1100000, timeout=5000)
    qtbot.waitUntil(lambda: dialog.wipe.images[1] != before, timeout=5000)
    dialog.zoom_combo.setCurrentIndex(dialog.zoom_combo.findData(2.0))
    assert dialog.wipe.zoom == 2
    assert dialog.image_stack.currentWidget() is dialog.wipe


def _hashes(path: Path, *, start: float = 0, duration: float = 1) -> list[str]:
    output = subprocess.check_output([
        "ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path),
        "-t", str(duration), "-map", "0:v:0", "-f", "framemd5", "-",
    ], timeout=30).decode()
    return [line.rsplit(",", 1)[-1].strip() for line in output.splitlines()
            if line and not line.startswith("#")]


def test_selected_reference_is_frame_exact_and_lossless(tiny_clip, tmp_path, monkeypatch):
    from video_uniquifier.core import _review_sample
    monkeypatch.setattr(_review_sample, "build_plan", MagicMock())
    _review_sample._prepare_review_sample(
        tiny_clip, Profile(name="reference", transforms=[]), tmp_path / "review",
        start_sec=0.5, duration_sec=1,
    )
    reference = tmp_path / "review" / "source.mkv"
    assert _hashes(tiny_clip, start=0.5) == _hashes(reference)
    assert tiny_clip != reference


def test_real_media_seek_play_and_frame_step(qtbot, tiny_clip):
    from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
    dialog = VideoCompareDialog(tiny_clip, tiny_clip)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: all(not size.isEmpty() for size in dialog._sizes), timeout=20000)
    assert dialog._frame_times == [0, 0]
    assert dialog._limit() >= 1900
    dialog.seek(500)
    qtbot.waitUntil(lambda: dialog._frame_times[1] >= 450000, timeout=5000)
    before = dialog._frame_times[1]
    dialog.step_frame(1)
    qtbot.waitUntil(lambda: dialog._frame_times[1] > before, timeout=5000)
    assert 20000 <= dialog._frame_times[1] - before <= 60000
    after = dialog._frame_times[1]
    dialog.step_frame(-1)
    qtbot.waitUntil(lambda: dialog._frame_times[1] < after, timeout=5000)
    assert dialog._frame_times[1] == before
    dialog.toggle_play()
    qtbot.waitUntil(lambda: dialog._position >= 750, timeout=5000)
    assert abs(dialog.players[0].position() - dialog.players[1].position()) <= 150
    dialog.pause()
    assert all(output.isMuted() for output in dialog.outputs)
    dialog.close()


@pytest.mark.parametrize("origin", [0, 5])
def test_frame_lookup_preserves_vfr_intervals_and_normalizes_origin(tiny_clip, tmp_path, origin):
    from video_uniquifier.core._review_frames import _review_frame_window
    from video_uniquifier.core.runner import CancelToken
    target = tmp_path / "vfr.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(tiny_clip), "-an", "-vf",
        r"select=not(eq(mod(n\,5)\,1))", "-fps_mode", "vfr",
        "-c:v", "libx264", "-output_ts_offset", str(origin), str(target),
    ], check=True, timeout=30, capture_output=True)
    frames = _review_frame_window(target, 0.5, CancelToken())
    assert frames[0] == pytest.approx(0, abs=0.001)
    assert frames[-1] < 2
    intervals = {round(right - left, 3) for left, right in zip(frames, frames[1:], strict=False)}
    assert len(intervals) >= 2


def test_frame_lookup_reaches_the_target_inside_a_long_gop(tmp_path):
    from video_uniquifier.core._review_frames import _review_frame_window
    from video_uniquifier.core.runner import CancelToken
    source = tmp_path / "long-gop.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=160x90:rate=5:duration=16", "-c:v", "libx264",
        "-g", "150", "-keyint_min", "150", "-sc_threshold", "0", str(source),
    ], check=True, capture_output=True, timeout=30)
    frames = _review_frame_window(source, 14, CancelToken())
    assert 13.8 in frames and 14 in frames and 14.2 in frames
