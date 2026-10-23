"""Desktop workflow regressions, including adapter errors and sample isolation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QFileDialog

from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.runtime import ReelsError
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.screens.reels import ReelsScreen
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.reels_options import ReelsOptions
from video_uniquifier.gui.workers import reels_worker
from video_uniquifier.gui.workers.reels_worker import ReelsWorker


@pytest.fixture(autouse=True)
def quiet_desktop(qapp, monkeypatch):
    previous = active_locale()
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    yield
    install_translator(qapp, previous)


@pytest.fixture
def screen(qtbot):
    widget = ReelsScreen(AppState())
    qtbot.addWidget(widget)
    yield widget
    assert widget.shutdown_workers()


def test_defaults_roundtrip_and_explicit_options(qtbot):
    options = ReelsOptions()
    qtbot.addWidget(options)
    rules, assets = options.configuration()
    assert rules == ReelsRules()
    assert assets == {}
    options.resolution.setCurrentIndex(1)
    options.crf.setValue(18)
    options.fps.setCurrentIndex(1)
    options.geometry_mode.setCurrentIndex(2)
    options.normalize.setChecked(False)
    options.trim_start.setValue(1.5)
    options.trim_end.setValue(2)
    rules, _ = options.configuration()
    assert (rules.video.width, rules.video.height) == (720, 1280)
    assert rules.video.crf == 18 and rules.video.fps_mode == "cfr30"
    assert rules.video.geometry.allow_center_crop
    assert not rules.audio.loudnorm.enabled
    assert rules.scenes.trim_start_sec == 1.5 and rules.scenes.trim_end_sec == 2


def test_branding_requires_files_and_preserves_advanced_fields(qtbot, tmp_path):
    rules = ReelsRules()
    rules.scenes.threshold = 31
    options = ReelsOptions()
    qtbot.addWidget(options)
    options.set_rules(rules)
    options.title_group.setChecked(True)
    options.title_text.setPlainText("第一集")
    with pytest.raises(ValueError, match="existing local"):
        options.configuration()
    font = tmp_path / "title.ttf"
    font.write_bytes(b"mock font validated by the core renderer")
    options.font_picker.path.setText(str(font))
    options.title_start.setValue(2)
    options.title_end.setValue(1)
    with pytest.raises(ValueError):
        options.configuration()
    options.title_end.setValue(3)
    configured, assets = options.configuration()
    assert assets == {"title-font.ttf": font}
    assert configured.packaging.enabled and configured.packaging.title.text == "第一集"
    assert configured.scenes.threshold == 31
    options.title_group.setChecked(False)
    configured, assets = options.configuration()
    assert not configured.packaging.enabled and not assets


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_reels_entry_and_all_steps_fit_small_windows(
    gui_window_factory, qtbot, qapp, size, theme,
):
    install_translator(qapp, "zh_CN")
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.resize(*size)
    window.show()
    window.sidebar.setCurrentItem(window.sidebar_items["Reels"])
    page = window.stack.currentWidget()
    assert isinstance(page, ReelsScreen)
    assert window.sidebar.currentItem() is window.sidebar_items["Reels"]
    assert page.navigation.buttons[1].text() == "02  处理参数"
    for index in range(4):
        page.navigation.buttons[index].click()
        qapp.processEvents()
        assert page.pages.currentIndex() == index
        assert page.pages.currentWidget().isVisible()
        assert sum(page.pages.widget(i).isVisible() for i in range(4)) == 1
        assert (window.width(), window.height()) == size
        assert page.page_scroll.widget().width() <= page.page_scroll.viewport().width()
        for button in (page.navigation.buttons[index], page.next_btn, page.back_btn):
            if button.isVisible():
                assert window.rect().contains(button.mapTo(window, button.rect().bottomRight()))
    page.navigation.setCurrentIndex(1)
    for index in range(3):
        page.options.setCurrentIndex(index)
        qapp.processEvents()
        scroll = page.options.currentWidget()
        assert scroll.widget().width() <= scroll.viewport().width()
    page.result_directory = Path("/example/completed")
    page.navigation.setCurrentIndex(3)
    qapp.processEvents()
    assert window.rect().contains(
        page.open_video_btn.mapTo(window, page.open_video_btn.rect().bottomRight()),
    )
    window._navigate_to("Batch")
    assert window.stack.currentIndex() == 1
    assert window.sidebar.currentItem() is window.sidebar_items["Batch"]
    window._navigate_to("Settings")
    assert window.stack.currentIndex() == 9


def test_live_language_switch_preserves_user_configuration(screen, qapp):
    screen.options.title_text.setPlainText("My programme")
    screen.options.crf.setValue(19)
    screen.navigation.setCurrentIndex(1)
    screen.show()
    install_translator(qapp, "zh_CN")
    qapp.processEvents()
    assert screen.navigation.buttons[2].text() == "03  预览检查"
    assert screen.options.tabText(0) == "视频交付"
    assert screen.options.title_text.toPlainText() == "My programme"
    assert screen.options.crf.value() == 19
    install_translator(qapp, "en_US")
    qapp.processEvents()
    assert screen.navigation.buttons[2].text() == "03  Preview check"
    assert screen.options.tabText(0) == "Video delivery"


def test_sidebar_routes_shortcuts_and_background_return_keep_screen_identity(
    gui_window_factory, qapp, tmp_path,
):
    from video_uniquifier.gui.app_pyqt import SIDEBAR_ITEMS
    from video_uniquifier.gui.widgets.navigation import NAV_ORDER

    window = gui_window_factory()
    window.show()
    assert tuple(window.sidebar.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(window.sidebar.count())) == NAV_ORDER
    assert not any(window.sidebar.item(i).isHidden() for i in range(window.sidebar.count()))
    shortcuts = {shortcut.key().toString(): shortcut for shortcut in window.findChildren(QShortcut)}
    for key, route in (("Ctrl+0", "Settings"), ("Ctrl+3", "Calibrate"),
                       ("Ctrl+Shift+R", "Reels")):
        shortcuts[key].activated.emit()
        qapp.processEvents()
        assert SIDEBAR_ITEMS[window.stack.currentIndex()][0] == route
    page = window.stack.currentWidget()
    page.worker = ReelsWorker(Path("source"), ReelsRules(), tmp_path)
    window._navigate_to("Settings")
    window._refresh_activity()
    assert not window.activity_banner.isHidden()
    window.activity_banner.requested.emit(10)
    window.sidebar.setFocus()
    window.resize(980, 640)
    qapp.processEvents()
    assert window.stack.currentWidget() is page
    page.worker = None


def test_invalid_configuration_and_invalid_yaml_are_inline(screen, monkeypatch, tmp_path):
    screen.input_picker.current_path = lambda: tmp_path / "input.mp4"
    screen.options.title_group.setChecked(True)
    screen._start("sample")
    assert screen.worker is None
    assert screen.navigation.currentIndex() == 1
    assert screen.feedback.property("error")
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("video: [\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(invalid), ""))
    screen._import_rules()
    assert screen.feedback.property("error")


def test_changed_settings_invalidate_sample_but_keep_completed_artifacts(
    screen, tmp_path, monkeypatch,
):
    screen.sample_directory = tmp_path / "sample"
    screen._sample_fingerprint = "old"
    screen.result_directory = tmp_path / "completed"
    screen.result_directory.mkdir()
    output = screen.result_directory / "output.mp4"
    output.touch()
    screen.options.crf.setValue(20)
    assert screen.sample_directory is None and screen._sample_fingerprint is None
    assert not screen.safe_btn.isEnabled()
    screen.output_folder.setText(str(tmp_path / "future"))
    opened = []
    monkeypatch.setattr("video_uniquifier.gui.screens.reels.QDesktopServices.openUrl",
                        lambda url: opened.append(Path(url.toLocalFile())))
    screen._open_artifact("output.mp4")
    assert opened == [output]


def test_actionable_failure_and_cancellation_keep_details(screen):
    screen._failed("hdr_requires_tonemap", "technical diagnostics")
    assert screen.navigation.currentIndex() == 3
    assert "HDR to SDR" in screen.feedback.text()
    assert "technical diagnostics" in screen.details_text.toPlainText()
    assert screen.details.toggle.isChecked()
    worker = ReelsWorker(Path("source"), ReelsRules(), Path("output"))
    screen.worker = worker
    screen._cancel()
    screen.navigation.setCurrentIndex(0)
    assert worker.cancel_token.is_cancelled() and not screen.cancel_btn.isEnabled()
    screen._cancelled()
    assert "cancelled" in screen.feedback.text()
    screen._worker_finished()
    assert screen.worker is None


def test_sample_worker_caps_timeline_and_stages_assets_without_mutating_rules(
    tmp_path, monkeypatch,
):
    rules = ReelsRules()
    rules.scenes.trim_start_sec = 2
    rules.scenes.trim_end_sec = 3
    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    rules.packaging.enabled = rules.packaging.title.enabled = True
    rules.packaging.title.text = "Title"
    rules.packaging.title.font_path = "title-font.ttf"
    rules.packaging.title.start_sec = 12
    original = rules.model_dump_json()
    monkeypatch.setattr(reels_worker, "inspect_source",
                        lambda *a: SimpleNamespace(duration_sec=30))
    result = tmp_path / "result"
    result.mkdir()
    (result / "report.json").write_text("{}")
    captured = []

    def process(source, effective, root, **kwargs):
        assert (kwargs["asset_root"] / "title-font.ttf").read_bytes() == b"font"
        captured.append(effective)
        kwargs["on_status"]("processing", .5)
        return result

    monkeypatch.setattr(reels_worker, "process_video", process)
    worker = ReelsWorker(Path("input.mp4"), rules, tmp_path, mode="sample",
                         assets={"title-font.ttf": font})
    completed, problems, progress = [], [], []
    worker.finished_ok.connect(completed.append)
    worker.problem.connect(lambda *args: problems.append(args))
    worker.progress.connect(lambda *args: progress.append(args))
    worker.run()
    assert not problems
    assert captured[0].scenes.trim_end_sec == 18
    assert not captured[0].packaging.title.enabled
    assert rules.model_dump_json() == original
    assert completed[0]["warnings"] and progress == [(.5, "processing")]


@pytest.mark.parametrize("failure", ["cancelled", "hdr_requires_tonemap", "unexpected"])
def test_worker_reports_failures_and_cancellation_separately(tmp_path, monkeypatch, failure):
    def process(*args, **kwargs):
        if failure == "unexpected":
            raise OSError("encoder missing")
        raise ReelsError(failure, "reason")

    monkeypatch.setattr(reels_worker, "process_video", process)
    worker = ReelsWorker(Path("input"), ReelsRules(), tmp_path)
    problems, cancelled, failed = [], [], []
    worker.problem.connect(lambda *args: problems.append(args))
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.failed.connect(failed.append)
    worker.run()
    if failure == "cancelled":
        assert cancelled and not problems and not failed
    else:
        assert not cancelled and failed
        assert problems[0][0] == ("processing_failed" if failure == "unexpected" else failure)


@pytest.mark.parametrize("asset_name", ["../escape.png", "missing.png"])
def test_worker_rejects_invalid_assets(tmp_path, asset_name):
    worker = ReelsWorker(Path("input"), ReelsRules(), tmp_path,
                         assets={asset_name: tmp_path / "missing"})
    problems = []
    worker.problem.connect(lambda code, message: problems.append(code))
    worker.run()
    assert problems == ["asset_path"]


@pytest.mark.integration
def test_desktop_real_preflight_sample_and_full_export(screen, tiny_clip, tmp_path, qtbot):
    """Exercise real QThreads, core, ffmpeg, QA and GUI result handoff."""
    screen.show()
    screen.input_picker.set_path(tiny_clip)
    qtbot.waitUntil(lambda: screen.probe_worker is None, timeout=15000)
    assert screen.source_meta is not None
    screen.options.resolution.setCurrentIndex(1)
    screen.options.detect_scenes.setChecked(False)
    screen.output_folder.setText(str(tmp_path / "exports"))
    for mode in ("preflight", "sample", "export"):
        screen._start(mode)
        assert screen.worker is not None
        assert not screen.options.isEnabled()
        qtbot.waitUntil(lambda: screen.worker is None, timeout=90000)
        assert not screen.feedback.property("error"), screen.details_text.toPlainText()
        assert screen.options.isEnabled()
        if mode == "preflight":
            assert screen._preflight_fingerprint
        if mode == "sample":
            assert screen.sample_directory
            assert (screen.sample_directory / "safe-area.png").is_file()
            screen.safe_btn.click()
            assert screen.review_tabs.currentIndex() == 1
    result = screen.result_directory
    assert result is not None and (result / "output.mp4").is_file()
    report = json.loads((result / "report.json").read_text())
    assert report["quality_check"]["status"] == "passed"
    assert report["output"]["video"][0]["width"] == 720
    assert abs(report["output"]["duration_sec"] - 2) < .15
    assert screen.progress_bar.value() == 1000
    assert screen.open_video_btn.isVisible()
    assert screen.scene_table.isHidden()
    assert screen.state.history[0].output_path == str(result / "output.mp4")

    # A real second encode is cancelled as soon as the core enters processing.
    screen._start("export")
    screen.worker.progress.connect(
        lambda fraction, phase: screen._cancel() if phase == "processing" else None,
    )
    qtbot.waitUntil(lambda: screen.worker is None, timeout=30000)
    assert "cancelled" in screen.feedback.text()
    assert screen.result_directory is None
    failures = list((tmp_path / "exports" / "failures").glob("*.json"))
    assert len(failures) == 1
    assert json.loads(failures[0].read_text())["status"] == "cancelled"
    assert len(list((tmp_path / "exports" / "results").iterdir())) == 1


def test_preflight_validates_assets_and_native_plan(tmp_path, monkeypatch):
    meta = SimpleNamespace(duration_sec=30)
    monkeypatch.setattr(reels_worker, "inspect_source", lambda *a: meta)
    monkeypatch.setattr(reels_worker, "validate_native_profile", lambda *a: "native")
    monkeypatch.setattr(reels_worker, "prepare_plan", lambda *a: ("plan", ["finding"]))
    monkeypatch.setattr(reels_worker, "render_layers", lambda *a: ([], [], ["warning"]))
    worker = ReelsWorker(Path("input"), ReelsRules(), tmp_path, mode="preflight")
    completed = []
    worker.finished_ok.connect(completed.append)
    worker.run()
    assert completed[0]["source"] is meta
    assert completed[0]["findings"] == ["finding"]
    assert completed[0]["warnings"] == ["warning"]


def test_worker_rejects_oversized_asset(tmp_path):
    path = tmp_path / "large.png"
    with path.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    worker = ReelsWorker(Path("input"), ReelsRules(), tmp_path, assets={"logo.png": path})
    problems = []
    worker.problem.connect(lambda code, message: problems.append(code))
    worker.run()
    assert problems == ["asset_size"]
