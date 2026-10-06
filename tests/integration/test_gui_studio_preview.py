"""Native embedded preview: decode, keyboard seeking, transport and media release."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QMediaPlayer

from video_uniquifier.gui.widgets.studio_preview import StudioPreview

pytestmark = pytest.mark.integration


def test_preview_real_media_transport_tracks_sample_and_hidden_pause(qtbot, tiny_clip):
    preview = StudioPreview()
    qtbot.addWidget(preview)
    preview.resize(640, 400)
    preview.show()
    preview.set_source(tiny_clip)
    qtbot.waitUntil(lambda: preview.play_button.isEnabled(), timeout=15000)
    assert preview.player.duration() > 1000
    sink = preview.sink
    assert sink is not None
    qtbot.waitUntil(lambda: sink.videoFrame().isValid(), timeout=15000)
    assert sink.videoFrame().size().width() > 0
    rendered = sink.videoFrame().toImage()
    assert not rendered.isNull()
    colors = {rendered.pixelColor(x, y).rgba()
              for x in range(0, rendered.width(), 20)
              for y in range(0, rendered.height(), 20)}
    assert len(colors) > 4
    qtbot.waitUntil(
        lambda: not preview._priming
        and preview.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
        timeout=5000,
    )
    assert preview.audio.isMuted()
    preview.seek_bar.setValue(500)
    qtbot.waitUntil(lambda: preview.player.position() >= 400, timeout=5000)
    qtbot.waitUntil(lambda: sink.videoFrame().startTime() >= 400000, timeout=5000)
    before = preview.player.position()
    preview.seek_bar.setSingleStep(100)
    qtbot.keyClick(preview.seek_bar, Qt.Key.Key_Right)
    qtbot.waitUntil(lambda: preview.player.position() > before, timeout=5000)
    samples = []
    preview.sample_selected.connect(lambda path, seconds: samples.append((path, seconds)))
    preview.select_sample.click()
    assert samples[0][0] == tiny_clip
    assert samples[0][1] == pytest.approx(preview.player.position() / 1000, abs=0.1)
    frame_before_play = sink.videoFrame().startTime()
    preview.toggle_play()
    qtbot.waitUntil(
        lambda: preview.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
    )
    qtbot.waitUntil(lambda: preview.player.position() > before + 150, timeout=5000)
    qtbot.waitUntil(lambda: sink.videoFrame().startTime() > frame_before_play, timeout=5000)
    preview.hide()
    assert preview.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    assert preview.audio.isMuted()
    preview.show()
    preview.set_result(tiny_clip)
    qtbot.waitUntil(lambda: preview.play_button.isEnabled(), timeout=15000)
    assert preview.track.currentData() == 1
    assert not preview.select_sample.isEnabled()
    preview.set_source(None)
    assert preview.player.source().isEmpty()
    assert preview.stage.currentWidget() == preview.empty
    preview.shutdown()


def test_loaded_hd_preview_keeps_transport_inside_a_small_workspace(
    gui_window_factory, qtbot, tiny_clip, tmp_path, monkeypatch,
):
    import subprocess

    from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    hd = tmp_path / "hd.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(tiny_clip), "-an", "-vf", "scale=1280:720",
        "-c:v", "libx264", "-preset", "ultrafast", str(hd),
    ], check=True, capture_output=True, timeout=30)
    window = gui_window_factory()
    window.show()
    screen = window.stack.widget(0)
    screen.input_picker.set_path(hd)
    qtbot.waitUntil(lambda: screen.preview._frame.isValid(), timeout=15000)
    window.resize(980, 640)
    qtbot.wait(100)
    bottom = screen.preview.seek_bar.rect().bottomRight()
    assert screen.workspace_top.rect().contains(
        screen.preview.seek_bar.mapTo(screen.workspace_top, bottom),
    )
    assert window.rect().contains(screen.preview.seek_bar.mapTo(window, bottom))
    assert screen.sample_btn.isEnabled()
    assert window.rect().contains(
        screen.sample_btn.mapTo(window, screen.sample_btn.rect().bottomRight()),
    )
    top, progress, log = screen.workspace_splitter.sizes()
    assert top > 0 and log > 0
    assert progress == 0 and screen.progress_scroll.isHidden()
