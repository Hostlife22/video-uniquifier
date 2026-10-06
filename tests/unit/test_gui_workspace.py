"""Desktop workspace regressions: real Qt layout, controls and asynchronous state."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication, QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QApplication

from video_uniquifier.core.models import EncoderCandidate, Plan
from video_uniquifier.core.preflight import PreflightFinding
from video_uniquifier.gui.app_pyqt import SIDEBAR_ITEMS
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.screens.run import PROFILES_DIR, RunScreen
from video_uniquifier.gui.screens.settings import SettingsScreen
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.file_picker import FilePickerRow
from video_uniquifier.gui.widgets.kpi_pills import KpiPills
from video_uniquifier.gui.workers.probe_worker import ProbeWorker


@pytest.fixture(autouse=True)
def quiet_desktop(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Use real widgets without starting hardware probes or reading test placeholders."""
    previous_locale = active_locale()
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    monkeypatch.setattr(ProbeWorker, "start", lambda self: None)
    yield
    install_translator(qapp, previous_locale)


@pytest.fixture
def screen(qtbot) -> RunScreen:
    screen = RunScreen(AppState())
    qtbot.addWidget(screen)
    screen.show()
    return screen


def test_fresh_session_selects_soft_and_preserves_a_saved_profile(qtbot) -> None:
    fresh = RunScreen(AppState())
    qtbot.addWidget(fresh)
    assert Path(fresh.profile_combo.currentData()).stem == "soft"
    state = AppState()
    saved = PROFILES_DIR / "medium.yaml"
    state.set_profile_path(saved)
    restored = RunScreen(state)
    qtbot.addWidget(restored)
    assert Path(restored.profile_combo.currentData()) == saved


def test_input_suggests_a_distinct_output_without_overwriting_existing_file(
    screen: RunScreen, tmp_path: Path,
) -> None:
    source = tmp_path / "film.mp4"
    source.touch()
    previous = tmp_path / "film.processed.mp4"
    previous.write_bytes(b"existing result")
    screen.input_picker.set_path(source)
    assert screen.output_picker.current_path() == tmp_path / "film.processed-2.mp4"
    assert screen.run_btn.isEnabled()
    assert previous.read_bytes() == b"existing result"


def test_changing_source_updates_suggestion_but_respects_manual_destination(
    screen: RunScreen, tmp_path: Path,
) -> None:
    first, second, third = [tmp_path / f"{name}.mp4" for name in ("first", "second", "third")]
    screen.input_picker.set_path(first)
    screen.input_picker.set_path(second)
    assert screen.output_picker.current_path() == tmp_path / "second.processed.mp4"
    chosen = tmp_path / "my-result.mp4"
    screen.output_picker.set_path(chosen)
    screen.input_picker.set_path(third)
    assert screen.output_picker.current_path() == chosen


def test_source_cannot_be_selected_as_its_own_output(
    screen: RunScreen, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.mp4"
    screen.input_picker.set_path(source)
    screen.output_picker.set_path(source)
    build = MagicMock()
    monkeypatch.setattr("video_uniquifier.gui.screens.run.build_plan", build)
    screen._on_run()
    assert not screen.run_btn.isEnabled()
    assert "preserve the source" in screen.readiness_hint.text()
    build.assert_not_called()


def test_failed_preflight_stays_blocked_until_inputs_change(
    screen: RunScreen, tmp_path: Path,
) -> None:
    screen.input_picker.set_path(tmp_path / "source.mp4")
    screen.preflight_panel.set_findings([
        PreflightFinding(code="test.blocked", severity="fail", message="Encoder unavailable"),
    ])
    screen._refresh_run_button()
    assert not screen.run_btn.isEnabled()
    screen.profile_combo.setCurrentIndex(screen.profile_combo.findText("medium"))
    assert screen.run_btn.isEnabled()
    assert screen._plan_cache is None
    assert screen.preflight_panel.isHidden()


def test_preflight_from_old_settings_cannot_block_new_selection(
    screen: RunScreen, tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    screen.input_picker.set_path(source)
    old_profile = Path(screen.profile_combo.currentData())
    screen.profile_combo.setCurrentIndex(screen.profile_combo.findText("medium"))
    screen._on_preflight_ready(
        MagicMock(spec=Plan),
        [PreflightFinding(code="old.failure", severity="fail", message="Outdated result")],
        (source, old_profile, None),
    )
    assert screen.run_btn.isEnabled()
    assert not screen._preflight_blocked
    assert screen._plan_cache is None


def test_errors_reveal_the_activity_log(screen: RunScreen) -> None:
    assert screen.log_details.content.isHidden()
    screen.log.log("Could not decode input", "error")
    assert not screen.log_details.content.isHidden()
    assert "Could not decode input" in screen.log.text.toPlainText()


def test_disclosure_can_be_opened_and_closed_with_keyboard(screen: RunScreen, qtbot) -> None:
    screen.advanced.toggle.setFocus()
    qtbot.keyClick(screen.advanced.toggle, Qt.Key.Key_Space)
    assert not screen.advanced.content.isHidden()
    qtbot.keyClick(screen.advanced.toggle, Qt.Key.Key_Space)
    assert screen.advanced.content.isHidden()


def test_encoder_override_reaches_combo_data_and_restores_saved_choice(qtbot) -> None:
    state = AppState()
    state.set_encoder_name("libx264")
    selector = EncoderSelector(state)
    qtbot.addWidget(selector)
    assert selector.currentData() == "libx264"
    selected: list[object] = []
    selector.encoder_changed.connect(selected.append)
    selector._on_detected([
        EncoderCandidate(name="libx264", vendor="x264", codec="h264", works=True),
        EncoderCandidate(name="h264_nvenc", vendor="nvenc", codec="h264", works=False),
    ])
    assert selector.currentData() == "libx264"
    assert selected == ["libx264"]
    assert not selector._model.item(2).isEnabled()
    selector.setCurrentIndex(0)
    assert selector.currentData() is None


def test_edit_profile_navigates_to_the_selected_recipe(gui_window_factory) -> None:
    window = gui_window_factory()
    window.show()
    run = window.stack.widget(0)
    run.profile_combo.setCurrentIndex(run.profile_combo.findText("medium"))
    run._open_profile_editor()
    assert window.stack.currentIndex() == 4
    editor = window.stack.currentWidget()
    assert Path(editor.profile_combo.currentData()).stem == "medium"


def test_hot_language_switch_updates_main_workflow_without_blank_labels(
    qapp: QApplication, screen: RunScreen,
) -> None:
    install_translator(qapp, "ru_RU")
    qapp.processEvents()
    assert screen.page_title.text() == "Обработка видео"
    assert screen.run_btn.text() == "Начать обработку"
    assert screen.profile_label.text() == "Профиль"
    assert screen.advanced.toggle.text().endswith("Дополнительно и свои профили")
    assert QCoreApplication.translate("Unknown", "Uncatalogued label") == "Uncatalogued label"


def test_settings_store_theme_ids_instead_of_translated_labels(qtbot) -> None:
    state = AppState()
    settings = SettingsScreen(state)
    qtbot.addWidget(settings)
    settings.theme_combo.setCurrentIndex(settings.theme_combo.findData("light"))
    assert state.theme == "light"
    assert settings.default_profile_combo.currentText() == "soft"


def test_drop_rejects_directories_and_remote_urls(qtbot, tmp_path: Path) -> None:
    picker = FilePickerRow("Input video")
    qtbot.addWidget(picker)
    for url in (QUrl.fromLocalFile(str(tmp_path)), QUrl("https://example.com/video.mp4")):
        mime = QMimeData()
        mime.setUrls([url])
        event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        picker.dropEvent(event)
        assert picker.current_path() is None
        assert not event.isAccepted()


def test_completed_output_action_keeps_the_last_result_path(
    screen: RunScreen, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = tmp_path / "completed.mp4"
    completed.touch()
    screen._on_done(str(completed), "")
    assert not screen.result_actions.isHidden()
    screen.output_picker.set_path(tmp_path / "future.mp4")
    open_url = MagicMock(return_value=True)
    monkeypatch.setattr("video_uniquifier.gui.screens.run.QDesktopServices.openUrl", open_url)
    screen._on_open_output()
    assert Path(open_url.call_args.args[0].toLocalFile()) == completed


@pytest.mark.parametrize("index", range(len(SIDEBAR_ITEMS)))
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_screen_fits_a_small_window_and_primary_action_stays_visible(
    gui_window_factory, qapp: QApplication, index: int, theme: str,
) -> None:
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.resize(980, 640)
    window.show()
    window.sidebar.setCurrentRow(index)
    for _ in range(3):
        qapp.processEvents()
    assert (window.width(), window.height()) == (980, 640)
    page = window.stack.currentWidget()
    assert page.page_scroll.widget().width() <= page.page_scroll.viewport().width()
    assert window.sidebar.horizontalScrollBar().maximum() == 0
    if index == 0:
        page.page_scroll.verticalScrollBar().setValue(10_000)
        qapp.processEvents()
        button_rect = page.run_btn.rect()
        origin = page.run_btn.mapTo(window, button_rect.topLeft())
        assert window.rect().contains(origin)
        assert window.rect().contains(origin + button_rect.bottomRight())


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_queue_and_validation_fit_with_long_paths_and_larger_text(
    gui_window_factory, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, theme: str,
) -> None:
    from PyQt6.QtWidgets import QLabel

    from video_uniquifier.gui.screens import validation

    long_path = Path("/example") / ("a-long-checkout-directory-" * 12) / "validation_log.csv"
    monkeypatch.setattr(validation, "DEFAULT_CSV", long_path)
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.resize(980, 640)
    queue = window.stack.widget(7)
    for label in queue.findChildren(QLabel):
        if label.text().startswith("Buckets live"):
            label.setStyleSheet("font-size: 16px;")
    window.show()
    for index in (7, 8):
        window.sidebar.setCurrentRow(index)
        page = window.stack.currentWidget()
        for _ in range(3):
            qapp.processEvents()
        assert page.page_scroll.widget().width() <= page.page_scroll.viewport().width()
        if index == 7:
            page.tabs.setCurrentIndex(1)
        else:
            page.stack.setCurrentIndex(2)
        for _ in range(3):
            qapp.processEvents()
        assert page.page_scroll.widget().width() <= page.page_scroll.viewport().width()


def test_cleared_metrics_do_not_reappear_when_theme_changes(qtbot) -> None:
    pills = KpiPills()
    qtbot.addWidget(pills)
    pills.set_qa({"vmaf_mean": 90.0})
    pills.clear()
    pills.set_theme("light")
    assert pills._layout.count() == 0


def test_chart_theme_switch_preserves_samples(qtbot) -> None:
    from video_uniquifier.gui.theme import tokens_for
    from video_uniquifier.gui.widgets.chart_widget import ChartWidget, Series

    state = AppState()
    chart = ChartWidget(state)
    qtbot.addWidget(chart)
    chart.set_series([Series("quality", "", [(1.0, 0.9)], color_token="chart_quality")])
    state.set_theme("light")
    assert chart._series[0].points == [(1.0, 0.9)]
    assert chart._series_color(chart._series[0]) == tokens_for("light")["chart_quality"]
    if chart._chart is not None:
        color = chart._chart.backgroundBrush().color().name().upper()
        assert color == tokens_for("light")["bg_alt"]


def test_completed_result_and_expanded_metrics_fit_the_small_window(
    gui_window_factory, qapp: QApplication, tmp_path: Path,
) -> None:
    window = gui_window_factory()
    window.resize(980, 640)
    window.show()
    screen = window.stack.widget(0)
    report = tmp_path / "report.html"
    report.touch()
    report.with_suffix(".json").write_text(json.dumps({
        "phash_similarity": 0.9, "vmaf_mean": 94.0,
        "audio_fp_hamming_per_frame": 19.0, "cid_predict_self": 0.8,
    }))
    screen._on_done(str(tmp_path / "processed.mp4"), str(report))
    for _ in range(3):
        qapp.processEvents()
    top = screen.open_output_btn.mapTo(window, screen.open_output_btn.rect().topLeft())
    bottom = screen.open_output_btn.mapTo(window, screen.open_output_btn.rect().bottomRight())
    assert window.rect().contains(top) and window.rect().contains(bottom)
    screen.metrics_details.set_expanded(True)
    qapp.processEvents()
    assert screen.kpi_pills._layout.itemAtPosition(1, 0) is not None
    assert screen.page_scroll.widget().width() <= screen.page_scroll.viewport().width()
