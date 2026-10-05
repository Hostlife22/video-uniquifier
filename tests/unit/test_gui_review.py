"""Review transport, sample isolation and stage ETA regressions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoFrameFormat

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.models import HDRInfo, Profile, SourceMeta, VideoStream
from video_uniquifier.core.runner import RunEvent
from video_uniquifier.gui.screens.run import RunScreen
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets import processing_status
from video_uniquifier.gui.widgets.processing_status import ProcessingStatus
from video_uniquifier.gui.widgets.video_compare import VideoCompareDialog
from video_uniquifier.gui.workers.encoder_detect_worker import EncoderDetectWorker
from video_uniquifier.gui.workers.probe_worker import ProbeWorker
from video_uniquifier.gui.workers.run_worker import RunWorker
from video_uniquifier.gui.workers.sample_worker import SampleWorker


@pytest.fixture(autouse=True)
def desktop(qapp, monkeypatch):
    monkeypatch.setattr(EncoderDetectWorker, "start", lambda self: None)
    monkeypatch.setattr(ProbeWorker, "start", lambda self: None)
    # Placeholder paths exercise transport state without asynchronous codec I/O.
    # Actual playback and failures belong to the real-media integration tests.
    monkeypatch.setattr(QMediaPlayer, "setSource", lambda self, _source: None)


def _source(path: Path, duration: float = 9.0, *, hdr: bool = False) -> SourceMeta:
    return SourceMeta(
        path=path, container="mp4", duration_sec=duration, size_bytes=100,
        video=[VideoStream(
            index=0, codec="h264", width=320, height=180, fps=24,
            duration_sec=duration, pix_fmt="yuv420p", color=HDRInfo(is_hdr=hdr),
        )],
    )


def test_eta_resets_at_each_phase_and_does_not_predict_unknown_work(qtbot, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(processing_status.time, "monotonic", lambda: clock[0])
    status = ProcessingStatus(AppState())
    qtbot.addWidget(status)
    status.start()
    status.set_phase("video", 0.1)
    clock[0] += 10
    status.set_phase("video", 0.5)
    assert status.remaining_seconds() == pytest.approx(10)
    status.set_phase("quality:vmaf", None)
    assert status.remaining_seconds() is None
    assert "Estimating" in status.time_label.text()
    status.set_phase("quality:ssim", 0.5)
    assert status.remaining_seconds() is None
    status.finish(success=True)


def test_pauses_and_stalls_do_not_produce_a_false_eta(qtbot, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(processing_status.time, "monotonic", lambda: clock[0])
    status = ProcessingStatus(AppState())
    qtbot.addWidget(status)
    status.start()
    status.set_phase("video", 0.1)
    clock[0] += 10
    status.set_phase("video", 0.5)
    status.set_paused(True)
    assert status.remaining_seconds() is None
    before = status.time_label.text()
    clock[0] += 120
    status.refresh()
    assert status.time_label.text() == before
    status.set_paused(False)
    assert status.remaining_seconds() == pytest.approx(10)
    clock[0] += 9
    assert status.remaining_seconds() is None
    status.finish(success=False)


def test_retry_progress_and_invalid_fractions_reset_estimates(qtbot, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(processing_status.time, "monotonic", lambda: clock[0])
    status = ProcessingStatus(AppState())
    qtbot.addWidget(status)
    status.start()
    status.set_phase("video", 0.1)
    clock[0] += 10
    status.set_phase("video", 0.5)
    status.set_phase("video", 0.05)
    assert status.remaining_seconds() is None
    status.set_phase("video", float("nan"))
    assert status.fraction is None
    assert status.remaining_seconds() is None
    status.finish(success=False)


def test_worker_maps_media_and_qa_stages_without_changing_video_progress():
    plan = MagicMock()
    plan.source.duration_sec = 2
    worker = RunWorker(plan, MagicMock(), run_qa=False)
    stages = []
    progress = []
    worker.stage_progress.connect(lambda phase, fraction: stages.append((phase, fraction)))
    worker.progress.connect(lambda fraction, _label: progress.append(fraction))
    worker._on_event(RunEvent(kind="progress", payload={
        "phase": "segment", "segment": 0, "out_time_us": "1000000",
    }))
    assert stages[-1] == ("video", 0.5)
    assert progress[-1] == 0.5
    worker._on_event(RunEvent(kind="log", payload={"phase": "segment"}))
    assert stages[-1] == ("video", 0.5)
    worker._on_event(RunEvent(kind="progress", payload={"phase": "concat"}))
    assert stages[-1] == ("save", None)
    worker._on_event(RunEvent(kind="log", payload={"phase": "validation"}))
    assert stages[-1] == ("quality:decode", None)


def test_cancel_during_qa_emits_cancelled_instead_of_a_completed_result(monkeypatch):
    import video_uniquifier.gui.workers.run_worker as module
    plan = MagicMock()
    plan.source.duration_sec = 2
    worker = RunWorker(plan, MagicMock())
    monkeypatch.setattr(module, "run_full", lambda *args, **kwargs: MagicMock())

    def qa(_summary):
        worker.request_cancel()
        raise PipelineError("cancelled")

    monkeypatch.setattr(worker, "_build_qa", qa)
    cancelled, completed, failed = [], [], []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.finished_ok.connect(lambda *paths: completed.append(paths))
    worker.failed.connect(failed.append)
    worker.run()
    assert cancelled == [True]
    assert not completed and not failed


def test_sample_uses_selected_settings_without_changing_full_paths(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(SampleWorker, "start", lambda self: None)
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    source = tmp_path / "source.mp4"
    screen.input_picker.set_path(source)
    full_output = screen.state.output_path
    screen._on_probed(_source(source))
    screen.sample_start.setValue(8)
    screen.sample_length.setCurrentIndex(screen.sample_length.findData(20))
    screen._on_sample()
    assert screen._sample_worker is not None
    assert screen._sample_worker.source == source
    assert screen._sample_worker.start_sec == 8
    assert screen._sample_worker.duration_sec == 1
    assert screen._sample_worker.profile == Path(screen.profile_combo.currentData())
    assert screen.state.input_path == source
    assert screen.state.output_path == full_output
    assert not screen.run_btn.isEnabled()
    assert not screen.sample_btn.isEnabled()
    assert not screen.auto_tune_btn.isEnabled()


def test_sample_cancellation_preserves_full_destination_and_allows_retry(
    qtbot, tmp_path, monkeypatch,
):
    monkeypatch.setattr(SampleWorker, "start", lambda self: None)
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    source = tmp_path / "source.mp4"
    screen.input_picker.set_path(source)
    full_output = screen.state.output_path
    screen._on_probed(_source(source))
    screen._on_sample()
    worker = screen._sample_worker
    screen._on_cancel()
    assert worker.cancel_token.is_cancelled()
    screen._on_sample_cancelled()
    assert screen.state.output_path == full_output
    assert screen.sample_btn.isEnabled()
    assert screen.run_btn.isEnabled()


def test_stale_probe_cannot_enable_sample_for_a_different_input(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    screen.input_picker.set_path(tmp_path / "new.mp4")
    screen._on_probed(_source(tmp_path / "old.mp4"))
    assert screen._source_meta is None
    assert not screen.sample_btn.isEnabled()


def test_hdr_sample_button_explains_the_limitation(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    source = tmp_path / "hdr.mp4"
    screen.input_picker.set_path(source)
    screen._on_probed(_source(source, hdr=True))
    assert not screen.sample_btn.isEnabled()
    assert "HDR" in screen.sample_hint.text()
    assert screen.run_btn.isEnabled()


def test_frame_step_discards_a_cache_from_a_different_position(qtbot, tmp_path):
    dialog = VideoCompareDialog(tmp_path / "source.mp4")
    qtbot.addWidget(dialog)
    dialog._frame_window = (0, 0.04, 0.08)
    dialog._step_position = 60
    dialog._step_direction = -1
    assert not dialog._step_from_window()


def test_audio_progress_does_not_assume_a_fixed_number_of_passes():
    plan = MagicMock()
    plan.source.duration_sec = 2
    worker = RunWorker(plan, MagicMock(), run_qa=False)
    stages = []
    worker.stage_progress.connect(lambda phase, fraction: stages.append((phase, fraction)))
    for stamp in (1000000, 1500000, 100000, 1000000):
        worker._on_event(RunEvent(kind="progress", payload={
            "phase": "main_audio", "out_time_us": str(stamp),
        }))
    assert stages[-1] == ("audio:pass2", 0.5)


def test_completed_comparison_keeps_the_actual_pair_when_inputs_change(qtbot, tmp_path):
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    source, output = tmp_path / "old.mp4", tmp_path / "completed.mp4"
    screen._review_source = source
    screen._on_done(str(output), "")
    screen.input_picker.set_path(tmp_path / "new.mp4")
    assert screen._review_pair == (source, output)


def test_transport_maps_duration_and_mutes_the_unselected_track(qtbot, tmp_path):
    dialog = VideoCompareDialog(tmp_path / "source.mp4", tmp_path / "result.mp4")
    qtbot.addWidget(dialog)
    dialog._durations = [2000, 1000]
    dialog.sync_combo.setCurrentIndex(dialog.sync_combo.findData("duration"))
    assert dialog._reference_position(500) == 1000
    assert dialog._limit() == 1000
    dialog._playing = True
    dialog._audio_changed()
    assert dialog.outputs[0].isMuted() and not dialog.outputs[1].isMuted()
    dialog.audio_combo.setCurrentIndex(0)
    assert not dialog.outputs[0].isMuted() and dialog.outputs[1].isMuted()
    dialog.pause()
    assert all(output.isMuted() for output in dialog.outputs)


def test_time_sync_uses_the_common_range_and_pixel_zoom_respects_screen_dpr(qtbot, tmp_path):
    dialog = VideoCompareDialog(tmp_path / "source.mp4", tmp_path / "result.mp4")
    qtbot.addWidget(dialog)
    dialog._durations = [2000, 1000]
    assert dialog._limit() == 1000
    assert dialog._reference_position(500) == 500
    frame = QVideoFrame(QVideoFrameFormat(
        QSize(320, 180), QVideoFrameFormat.PixelFormat.Format_RGBA8888,
    ))
    frame.setStartTime(500000)
    dialog._frame(1, frame)
    dialog.zoom_combo.setCurrentIndex(dialog.zoom_combo.findData("pixels"))
    assert dialog.videos[1].width() == round(320 / dialog.videos[1].devicePixelRatioF())
    assert dialog.videos[1].height() == round(180 / dialog.videos[1].devicePixelRatioF())
    assert not dialog.areas[1].widgetResizable()
    dialog.view_combo.setCurrentIndex(dialog.view_combo.findData("source"))
    assert dialog.panels[1].isHidden()
    dialog.close()
    assert all(player.source().isEmpty() for player in dialog.players)


@pytest.mark.parametrize("start,length", [(-1, 10), (float("nan"), 10), (0, 21), (0, 0)])
def test_review_sample_rejects_unbounded_or_invalid_requests(tmp_path, start, length):
    from video_uniquifier.core._review_sample import _prepare_review_sample
    with pytest.raises(PipelineError):
        _prepare_review_sample(
            tmp_path / "source.mp4", Profile(name="t", transforms=[]), tmp_path,
            start_sec=start, duration_sec=length,
        )


def test_hdr_reference_is_not_silently_stripped(tmp_path, monkeypatch):
    from video_uniquifier.core import _review_sample
    source = tmp_path / "hdr.mp4"
    monkeypatch.setattr(_review_sample, "probe_file", lambda _path: _source(source, hdr=True))
    encode = MagicMock()
    monkeypatch.setattr(_review_sample, "run", encode)
    with pytest.raises(PipelineError, match="HDR"):
        _review_sample._prepare_review_sample(
            source, Profile(name="t", transforms=[]), tmp_path,
            start_sec=0, duration_sec=10,
        )
    encode.assert_not_called()
