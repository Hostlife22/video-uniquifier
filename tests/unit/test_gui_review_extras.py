"""Regression coverage for filmstrip selection, comparison, export and task navigation."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QEvent, QPoint, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPixmap, QValidator
from PyQt6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoFrameFormat
from PyQt6.QtWidgets import QApplication, QFileDialog

from video_uniquifier.core._review_export import _save_review_sample
from video_uniquifier.core._review_images import _review_thumbnails
from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.models import HDRInfo, SourceMeta, VideoStream
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.screens.run import PROFILES_DIR, RunScreen
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import qss_for
from video_uniquifier.gui.widgets.activity_banner import ActivityBanner
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.profile_cards import ProfileCards
from video_uniquifier.gui.widgets.sample_timeline import SampleTimeline, TimecodeSpinBox, timecode
from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
from video_uniquifier.gui.widgets.wipe_compare import WipeCompare
from video_uniquifier.gui.workers.probe_worker import ProbeWorker
from video_uniquifier.gui.workers.review_assets_worker import SaveSampleWorker, ThumbnailWorker


@pytest.fixture(autouse=True)
def desktop(qapp, monkeypatch):
    locale = active_locale()
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    monkeypatch.setattr(ProbeWorker, "start", lambda self: None)
    monkeypatch.setattr(ThumbnailWorker, "start", lambda self: None)
    monkeypatch.setattr(QMediaPlayer, "setSource", lambda self, _source: None)
    yield
    install_translator(qapp, locale)


def _source(path: Path, duration: float = 90) -> SourceMeta:
    return SourceMeta(path=path, container="mp4", size_bytes=100, duration_sec=duration,
                      video=[VideoStream(index=0, codec="h264", width=320, height=180,
                                         fps=24, duration_sec=duration, pix_fmt="yuv420p",
                                         color=HDRInfo(is_hdr=False))])


@pytest.mark.parametrize("alias", ["original", "sample", "symlink", "hardlink"])
def test_export_rejects_every_alias_of_the_original_and_temporary_sample(tmp_path, alias):
    original, sample = tmp_path / "original.mp4", tmp_path / "sample.mp4"
    original.write_bytes(b"original")
    sample.write_bytes(b"sample")
    destination = tmp_path / "alias.mp4"
    if alias == "symlink":
        destination.symlink_to(original)
    elif alias == "hardlink":
        os.link(original, destination)
    else:
        destination = original if alias == "original" else sample
    with pytest.raises(PipelineError, match="preserve"):
        _save_review_sample(sample, destination, protected=(original,), token=CancelToken(),
                            progress=lambda _: None)
    assert original.read_bytes() == b"original"
    assert sample.read_bytes() == b"sample"


def test_export_commits_only_after_copy_and_preserves_the_saved_file(tmp_path):
    sample, destination = tmp_path / "sample.mp4", tmp_path / "saved.mp4"
    payload = b"new" * 800000
    sample.write_bytes(payload)
    destination.write_bytes(b"previous")
    fractions = []

    def observe(fraction):
        fractions.append(fraction)
        assert destination.read_bytes() == b"previous"

    assert _save_review_sample(sample, destination, protected=(), token=CancelToken(),
                               progress=observe) == destination
    sample.unlink()
    assert destination.read_bytes() == payload
    assert fractions == sorted(fractions) and fractions[-1] == 1
    assert sorted(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("failure", ["cancel", "callback_error"])
def test_export_interruption_keeps_existing_destination_and_removes_partial_copy(tmp_path, failure):
    sample, destination = tmp_path / "sample.mp4", tmp_path / "saved.mp4"
    sample.write_bytes(b"a" * 2000000)
    destination.write_bytes(b"previous")
    token = CancelToken()

    def interrupt(_fraction):
        if failure == "cancel":
            token.cancel()
        else:
            raise OSError("disk error")

    with pytest.raises((PipelineError, OSError)):
        _save_review_sample(sample, destination, protected=(), token=token, progress=interrupt)
    assert destination.read_bytes() == b"previous"
    assert set(tmp_path.iterdir()) == {sample, destination}


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan")])
def test_invalid_thumbnail_duration_never_starts_decoder(tmp_path, monkeypatch, duration):
    decoder = MagicMock()
    monkeypatch.setattr("video_uniquifier.core._review_images.subprocess.Popen", decoder)
    with pytest.raises(PipelineError):
        list(_review_thumbnails(tmp_path / "video", duration, CancelToken()))
    decoder.assert_not_called()


def test_cancelled_thumbnail_worker_never_starts_decoder(tmp_path, monkeypatch):
    decoder = MagicMock()
    monkeypatch.setattr("video_uniquifier.core._review_images.subprocess.Popen", decoder)
    token = CancelToken()
    token.cancel()
    with pytest.raises(PipelineError):
        list(_review_thumbnails(tmp_path / "video", 5, token))
    decoder.assert_not_called()


def test_thumbnail_cancel_kills_running_decoder_and_collects_its_output(tmp_path, monkeypatch):
    from video_uniquifier.core import _review_images
    token = CancelToken()
    process = MagicMock()
    process.__enter__.return_value = process
    process.communicate.return_value = (b"", b"")

    def launch(*_args, **_kwargs):
        token.cancel()
        return process

    monkeypatch.setattr(_review_images.subprocess, "Popen", launch)
    with pytest.raises(PipelineError, match="cancelled"):
        list(_review_thumbnails(tmp_path / "source", 10, token))
    process.kill.assert_called_once()
    process.communicate.assert_called_once_with(timeout=2)


def test_timecode_accepts_fractional_seconds_and_unbounded_hours(qtbot):
    spin = TimecodeSpinBox()
    qtbot.addWidget(spin)
    spin.setRange(0, 500000)
    spin.setDecimals(2)
    assert spin.valueFromText("100:02:03.45") == 360123.45
    assert spin.valueFromText("00:01:02,5") == 62.5
    spin.setValue(360123.45)
    assert spin.text() == "100:02:03.45"
    assert timecode(59.999) == "00:01:00.00"
    assert spin.validate("00:60:00", 8)[0] != QValidator.State.Acceptable
    assert spin.validate("bad", 3)[0] == QValidator.State.Invalid
    assert spin.validate("100:", 4)[0] == QValidator.State.Intermediate


def test_timeline_click_and_keyboard_update_timecode_and_selection(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    path = tmp_path / "source.mp4"
    screen.input_picker.set_path(path)
    screen._on_probed(_source(path))
    screen.sample_controls.set_expanded(True)
    screen.resize(1000, 1000)
    screen.show()
    timeline = screen.sample_timeline
    qtbot.mouseClick(timeline, Qt.MouseButton.LeftButton,
                     pos=QPoint(timeline.width() // 2, timeline.height() // 2))
    assert screen.sample_start.value() == pytest.approx(45, abs=0.2)
    before = screen.sample_start.value()
    qtbot.keyClick(timeline, Qt.Key.Key_Right)
    assert screen.sample_start.value() == pytest.approx(before + 1)
    screen.sample_start.setValue(80.25)
    assert timeline.value() == 80250
    screen.sample_length.setCurrentIndex(0)
    assert timeline.length_sec == 10
    screen._select_sample_time(tmp_path / "previous.mp4", 20)
    assert screen.sample_start.value() == 80.25


@pytest.mark.parametrize("custom_name", ["custom.yaml", "soft.yaml"])
def test_profile_cards_and_custom_profile_remain_in_sync(qtbot, tmp_path, custom_name):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    assert screen.profile_cards.buttons["soft"].isChecked()
    screen.profile_cards.buttons["medium"].click()
    assert screen.state.profile_path == PROFILES_DIR / "medium.yaml"
    assert screen.profile_cards.buttons["medium"].isChecked()
    custom = tmp_path / custom_name
    screen.profile_combo.addItem("custom", str(custom))
    screen.profile_combo.setCurrentIndex(screen.profile_combo.count() - 1)
    assert not any(button.isChecked() for button in screen.profile_cards.buttons.values())
    screen._save_worker = MagicMock()
    screen._refresh_run_button()
    assert not screen.profile_cards.isEnabled()
    assert "Saving sample" in screen.readiness_hint.text()
    screen._save_worker = None


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("larger_font", [False, True])
def test_profile_card_descriptions_fit_small_russian_window(qtbot, qapp, theme, larger_font):
    install_translator(qapp, "ru_RU")
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    screen.setStyleSheet(qss_for(theme))
    if larger_font:
        for labels in screen.profile_cards.labels.values():
            for label in labels:
                label.setStyleSheet("font-size: 16px;")
    screen.resize(740, 640)
    screen.show()
    qapp.processEvents()
    for key, button in screen.profile_cards.buttons.items():
        for label in screen.profile_cards.labels[key]:
            assert not label.isHidden() and label.height() > 0
            assert button.rect().contains(label.geometry())
            assert label.height() >= label.heightForWidth(label.width())


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("font_size", [16, 20, 24])
def test_profile_cards_reflow_when_font_changes_in_an_open_window(
    qtbot, qapp, theme, font_size,
):
    install_translator(qapp, "ru_RU")
    cards = ProfileCards()
    qtbot.addWidget(cards)
    cards.setStyleSheet(qss_for(theme))
    cards.resize(660, 192)
    cards.show()
    qapp.processEvents()
    for labels in cards.labels.values():
        for label in labels:
            label.setStyleSheet(f"font-size: {font_size}px;")

    def text_fits():
        return all(
            button.rect().contains(label.geometry())
            and label.height() >= label.heightForWidth(label.width())
            for key, button in cards.buttons.items()
            for label in cards.labels[key]
        )

    qtbot.waitUntil(text_fits, timeout=3000)
    expanded = [sum(label.height() for label in labels) for labels in cards.labels.values()]
    for labels in cards.labels.values():
        for label in labels:
            label.setStyleSheet("font-size: 12px;")
    qtbot.waitUntil(
        lambda: all(sum(label.height() for label in labels) < previous
                    for labels, previous in zip(
            cards.labels.values(), expanded, strict=True,
        )),
        timeout=3000,
    )
    qtbot.waitUntil(text_fits, timeout=3000)
    qtbot.wait(25)
    assert not cards._fit_timer.isActive()


def test_old_thumbnail_results_are_discarded_and_latest_request_is_queued(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    first.touch()
    second.touch()
    screen.input_picker.set_path(first)
    screen._on_probed(_source(first))
    old = screen._thumbnail_worker
    screen.input_picker.set_path(second)
    screen._on_probed(_source(second))
    assert old.cancel_token.is_cancelled()
    assert screen._thumbnail_pending.path == second
    image = QImage(160, 90, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    pixmap = QPixmap.fromImage(image)
    screen.sample_timeline.add_frame(0, pixmap)
    screen._on_thumbnail(first, 0, b"stale")
    assert screen.source_thumbnail.pixmap().isNull()
    screen._thumbnails_finished()
    assert screen._thumbnail_worker.source == second
    assert screen._thumbnail_pending is None


def test_wipe_renders_both_images_and_supports_keyboard_divider_and_shared_pan(qtbot):
    wipe = WipeCompare()
    qtbot.addWidget(wipe)
    wipe.resize(600, 360)
    images = [QImage(600, 360, QImage.Format.Format_RGB32) for _ in range(2)]
    images[0].fill(QColor("red"))
    images[1].fill(QColor("blue"))
    wipe.set_images(*images)
    wipe.show()
    rendered = wipe.grab().toImage()
    assert rendered.pixelColor(80, 120) == QColor("red")
    assert rendered.pixelColor(500, 120) == QColor("blue")
    qtbot.keyClick(wipe, Qt.Key.Key_Left)
    assert wipe.divider == pytest.approx(0.48)
    qtbot.keyClick(wipe, Qt.Key.Key_Home)
    assert wipe.divider == 0
    qtbot.keyClick(wipe, Qt.Key.Key_End)
    assert wipe.divider == 1
    wipe.set_zoom(2)
    qtbot.mousePress(wipe, Qt.MouseButton.LeftButton, pos=QPoint(100, 120))
    qtbot.mouseMove(wipe, QPoint(140, 160))
    qtbot.mouseRelease(wipe, Qt.MouseButton.LeftButton, pos=QPoint(140, 160))
    assert wipe.offset.x() == 40 and wipe.offset.y() == 40
    wipe.set_theme("light")
    assert wipe.theme == "light"
    wipe.set_zoom(None)
    assert wipe.offset.isNull()


def test_wipe_conversion_applies_presentation_rotation_and_mirroring():
    image = QImage(4, 2, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    image.setPixelColor(0, 0, QColor("red"))
    frame = MagicMock()
    frame.toImage.return_value = image
    frame.rotationAngle.return_value = QVideoFrame.RotationAngle.Rotation90
    frame.mirrored.return_value = True
    rotated = VideoCompareDialog._inspection_image(frame)
    assert rotated.size() == QSize(2, 4)
    assert rotated.pixelColor(0, 0) == QColor("red")


def test_shared_native_pan_maps_scroll_fraction_in_both_directions(qtbot, tmp_path):
    dialog = VideoCompareDialog(tmp_path / "a.mp4", tmp_path / "b.mp4")
    qtbot.addWidget(dialog)
    first, second = [area.horizontalScrollBar() for area in dialog.areas]
    first.setRange(0, 100)
    second.setRange(0, 200)
    first.setValue(25)
    assert second.value() == 50
    second.setValue(150)
    assert first.value() == 75


def test_close_detaches_panning_filters_before_child_widget_teardown(qtbot, tmp_path, monkeypatch):
    dialog = VideoCompareDialog(tmp_path / "a.mp4", tmp_path / "b.mp4")
    qtbot.addWidget(dialog)
    observed = []

    def record(widget, event):
        if event.type() == QEvent.Type.User:
            observed.append(widget)
        return False

    monkeypatch.setattr(dialog, "eventFilter", record)
    watched = [*dialog.videos, *(area.viewport() for area in dialog.areas)]
    for widget in watched:
        QApplication.sendEvent(widget, QEvent(QEvent.Type.User))
    assert observed == watched
    observed.clear()
    dialog.close()
    for widget in watched:
        QApplication.sendEvent(widget, QEvent(QEvent.Type.User))
    assert observed == []


def test_hdr_frames_disable_raster_wipe_without_disabling_native_panels(qtbot, tmp_path):
    dialog = VideoCompareDialog(tmp_path / "a.mp4", tmp_path / "b.mp4")
    qtbot.addWidget(dialog)
    dialog.view_combo.setCurrentIndex(dialog.view_combo.findData("wipe"))
    format_ = QVideoFrameFormat(QSize(16, 16), QVideoFrameFormat.PixelFormat.Format_RGBA8888)
    format_.setColorTransfer(QVideoFrameFormat.ColorTransfer.ColorTransfer_ST2084)
    dialog._frame(0, QVideoFrame(format_))
    assert dialog.view_combo.currentData() == "both"
    assert not dialog.view_combo.model().item(dialog.view_combo.findData("wipe")).isEnabled()
    assert dialog.view_combo.model().item(0).isEnabled()


@pytest.mark.parametrize("protected_name", ["a.mp4", "ref.mkv"])
def test_saved_sample_uses_original_pinned_at_processing_start(
    qtbot, tmp_path, monkeypatch, protected_name,
):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    original, reference, sample = [tmp_path / name for name in ("a.mp4", "ref.mkv", "test.mp4")]
    original.write_bytes(b"original")
    reference.write_bytes(b"reference")
    sample.write_bytes(b"candidate")
    screen._sample_mode = True
    screen._sample_input_path = original
    screen._review_pair = (reference, sample)
    screen.state.set_input_path(tmp_path / "new.mp4")
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *args: (str(tmp_path / protected_name), ""))
    screen._save_sample()
    qtbot.waitUntil(lambda: screen._save_worker is None, timeout=5000)
    assert original.read_bytes() == b"original"
    assert reference.read_bytes() == b"reference"
    assert "Could not save" in screen.status_label.text()
    destination = tmp_path / "saved"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), ""))
    screen._save_sample()
    qtbot.waitUntil(lambda: screen._save_worker is None, timeout=5000)
    assert destination.with_suffix(".mp4").read_bytes() == b"candidate"
    assert "Sample saved" in screen.status_label.text()


def test_sample_export_cancel_signal_keeps_temporary_result(qtbot, tmp_path):
    sample = tmp_path / "sample.mp4"
    sample.write_bytes(b"candidate")
    worker = SaveSampleWorker(sample, tmp_path / "saved.mp4", ())
    worker.request_cancel()
    cancelled, errors = [], []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.failed.connect(errors.append)
    worker.run()
    assert cancelled and not errors
    assert sample.read_bytes() == b"candidate"
    assert not (tmp_path / "saved.mp4").exists()


def test_banner_tracks_multiple_tasks_and_preserves_selected_task(qtbot):
    banner = ActivityBanner()
    qtbot.addWidget(banner)
    banner.set_tasks([(0, "Run", "Video 25%", 0.25), (1, "Batch", "Processing", None)])
    assert banner.progress.value() == 250
    banner.tasks.setCurrentIndex(1)
    assert banner.progress.maximum() == 0
    banner.set_tasks([(0, "Run", "Video 50%", 0.5), (1, "Batch", "Processing", 0.4)])
    assert banner.tasks.currentData() == 1 and banner.progress.value() == 400
    with qtbot.waitSignal(banner.requested) as signal:
        banner.return_btn.click()
    assert signal.args == [1]
    banner.set_tasks([])
    assert banner.isHidden()


def test_progress_polling_preserves_task_dropdown_navigation(qtbot):
    banner = ActivityBanner()
    qtbot.addWidget(banner)
    banner.set_tasks([(0, "Run", "Video 25%", 0.25), (1, "Batch", "Processing", None)])
    banner.tasks.view().setCurrentIndex(banner.tasks.model().index(1, 0))
    assert banner.tasks.currentData() == 0
    banner.set_tasks([(0, "Run", "Video 50%", 0.5), (1, "Batch", "Processing", 0.4)])
    assert banner.tasks.view().currentIndex().row() == 1
    assert banner.progress.value() == 500


def test_global_banner_survives_navigation_and_hides_after_completion(gui_window_factory):
    window = gui_window_factory()
    screen = window.stack.widget(0)
    screen._sample_worker = MagicMock()
    screen.status_label.setText("Video 42%")
    screen.progress_bar.setRange(0, 1000)
    screen.progress_bar.setValue(420)
    window.sidebar.setCurrentRow(9)
    window._refresh_activity()
    assert not window.activity_banner.isHidden()
    assert window.activity_banner.progress.value() == 420
    window.activity_banner.return_btn.click()
    assert window.stack.currentIndex() == 0
    screen._sample_worker = None
    screen._tune_worker = MagicMock()
    screen.processing_status.set_phase("video", 0.8)
    screen.processing_status.time_label.setText("stale elapsed")
    window._refresh_activity()
    assert window.activity_banner.progress.maximum() == 0
    assert "stale" not in window.activity_banner.details.text()
    screen._tune_worker = None
    window._refresh_activity()
    assert window.activity_banner.isHidden()


def test_new_controls_translate_during_an_existing_session(qtbot, qapp):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    install_translator(qapp, "ru_RU")
    qapp.processEvents()
    assert screen.profile_cards.labels["medium"][0].text() == "Сбалансированная"
    assert screen.save_sample_btn.text() == "Сохранить фрагмент…"
    assert screen.sample_start_label.text() == "Начало"
    assert screen.sample_length.itemText(0) == "10 сек."
    assert screen.sample_timeline.accessibleName() == "Шкала выбора фрагмента"


def test_stopping_screen_cancels_thumbnail_worker_and_discards_pending_request(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    source = tmp_path / "a.mp4"
    source.touch()
    screen.input_picker.set_path(source)
    screen._on_probed(_source(source))
    screen._thumbnail_pending = _source(source)
    screen._shutting_down = True
    screen._thumbnails_finished()
    assert screen._thumbnail_worker is None


def test_slider_placeholder_and_light_theme_render_without_media(qtbot):
    state = AppState()
    timeline = SampleTimeline(state)
    qtbot.addWidget(timeline)
    timeline.resize(600, 112)
    timeline.show()
    assert not timeline.grab().isNull()
    state.set_theme("light")
    assert not timeline.grab().isNull()
