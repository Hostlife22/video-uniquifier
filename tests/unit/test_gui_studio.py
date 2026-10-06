"""Studio workflow regressions using native Qt selection, layout and signals."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QAbstractAnimation, QCoreApplication, QEvent, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QWidget,
)

from video_uniquifier.gui.design import Space
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.screens.batch import BatchScreen
from video_uniquifier.gui.screens.queue import QueueScreen
from video_uniquifier.gui.screens.settings import SettingsScreen
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.profile_cards import ProfileCards
from video_uniquifier.gui.widgets.splitter import StudioSplitter
from video_uniquifier.gui.widgets.studio_preview import StudioPreview
from video_uniquifier.gui.widgets.studio_table import STATUS_ROLE, StudioTable, TableTools
from video_uniquifier.gui.widgets.surfaces import Disclosure
from video_uniquifier.gui.widgets.table_selection import TableSelectionCheckBox


@pytest.fixture(autouse=True)
def quiet_desktop(qapp, monkeypatch):
    previous = active_locale()
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    yield
    install_translator(qapp, previous)


def make_table(qtbot, state=None):
    table = StudioTable(3, state or AppState(), "test.header", 1)
    table.setHorizontalHeaderLabels(["File", "Status", "Actions"])
    table.restore_header()
    qtbot.addWidget(table)
    with table.updating():
        for row, (name, status) in enumerate((("b.mp4", "pending"), ("a.mp4", "done"),
                                            ("c.mp4", "failed"))):
            path = str(Path("/example") / name)
            table.insertRow(row)
            table.setItem(row, 0, table.file_item(name, name, path))
            table.setItem(row, 1, table.status_item(status))
            table.setCellWidget(row, 2, table.row_actions(path))
    tools = TableTools(table)
    qtbot.addWidget(tools)
    return table, tools


def test_sort_and_status_update_preserve_selected_file(qtbot):
    table, _tools = make_table(qtbot)
    table.sortItems(0, Qt.SortOrder.AscendingOrder)
    table.selectRow(table.find_key("b.mp4"))
    with table.updating():
        row = table.find_key("b.mp4")
        table.setItem(row, 1, table.status_item("running"))
    table.sortItems(1, Qt.SortOrder.DescendingOrder)
    assert table.selected_keys() == ["b.mp4"]
    assert table.item(table.find_key("b.mp4"), 1).data(STATUS_ROLE) == "running"
    assert table.item(table.find_key("a.mp4"), 1).data(STATUS_ROLE) == "done"


def test_filtered_multiselect_copies_only_visible_paths(qtbot, qapp):
    table, tools = make_table(qtbot)
    table.select_visible()
    assert len(table.selected_keys()) == 3
    tools.status.setCurrentIndex(tools.status.findData("done"))
    assert table.selected_keys() == ["a.mp4"]
    table.copy_selected_paths()
    assert qapp.clipboard().text() == str(Path("/example/a.mp4"))
    tools.status.setCurrentIndex(0)
    tools.search.setText("/example/c.mp4")
    table.select_visible()
    assert table.selected_keys() == ["c.mp4"]
    assert tools.count.text() == "1 shown · 1 selected"


def test_row_action_stays_bound_to_file_after_sort(qtbot):
    table, _tools = make_table(qtbot)
    table.open_requested.disconnect()
    opened = []
    table.open_requested.connect(opened.append)
    table.sortItems(0, Qt.SortOrder.DescendingOrder)
    widget = table.cellWidget(table.find_key("a.mp4"), 2)
    button = widget.findChildren(QPushButton)[0]
    button.click()
    assert opened == [str(Path("/example/a.mp4"))]
    assert opened[0] in button.toolTip()


def test_column_sizes_order_and_sort_persist(qtbot):
    state = AppState()
    table, _ = make_table(qtbot, state)
    table.header.setStretchLastSection(False)
    table.header.resizeSection(0, 231)
    table.header.moveSection(0, 1)
    table.sortItems(1, Qt.SortOrder.AscendingOrder)
    state.save()
    restored, _ = make_table(qtbot, AppState())
    assert restored.header.sectionSize(0) == 231
    assert restored.header.visualIndex(0) == 1
    assert restored.header.sortIndicatorSection() == 1
    assert restored.header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder


def make_splitter(qtbot, state):
    splitter = StudioSplitter(Qt.Orientation.Horizontal, state, "test.split")
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.resize(720, 240)
    qtbot.addWidget(splitter)
    splitter.show()
    QApplication.processEvents()
    return splitter


def test_splitter_keyboard_resize_survives_restart(qtbot):
    state = AppState()
    splitter = make_splitter(qtbot, state)
    splitter.setSizes([470, 244])
    before = splitter.sizes()[0]
    qtbot.keyClick(splitter.handle(1), Qt.Key.Key_Right)
    assert splitter.sizes()[0] > before
    sizes = splitter.sizes()
    state.save()
    restored = make_splitter(qtbot, AppState())
    assert restored.sizes() == sizes


def test_corrupt_layout_uses_visible_default_panels(qtbot):
    state = AppState()
    state.set_layout_state("test.split", "corrupt invalid base64")
    splitter = make_splitter(qtbot, state)
    assert all(size > 0 for size in splitter.sizes())


@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_workspace_keeps_preview_inspector_and_primary_action_visible(
    gui_window_factory, size,
):
    window = gui_window_factory()
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    screen = window.stack.widget(0)
    assert screen.preview.width() >= 300
    assert screen.settings_scroll.width() >= 316
    assert screen.preview.mapTo(window, screen.preview.rect().topRight()).x() < (
        screen.settings_scroll.mapTo(window, screen.settings_scroll.rect().topLeft()).x()
    )
    assert screen.run_btn.isVisible()
    assert window.rect().contains(screen.run_btn.mapTo(window, screen.run_btn.rect().bottomRight()))
    screen.workspace_top.setSizes([350, 500])
    screen._reset_workspace()
    assert screen.workspace_top.sizes()[0] > screen.workspace_top.sizes()[1]


def test_compact_cards_show_only_selected_details(qtbot):
    cards = ProfileCards()
    qtbot.addWidget(cards)
    cards.set_selected("medium")
    assert cards.buttons["medium"].isChecked()
    assert cards.details.text()
    assert len(cards.labels["medium"]) == 2
    cards.set_selected("custom")
    assert cards.details.isHidden()
    assert not any(button.isChecked() for button in cards.buttons.values())


@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_log_is_full_width_below_result_and_collapses_to_one_row(gui_window_factory, size):
    window = gui_window_factory()
    screen = window.stack.widget(0)
    # The previous side-by-side lower panes must not override the new layout.
    old = StudioSplitter(Qt.Orientation.Horizontal, window.state, "run.bottom")
    old.addWidget(QWidget())
    old.addWidget(QWidget())
    window.state.set_layout_state("run.vertical", old.saveState().toBase64().data().decode())
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    assert screen.workspace_splitter.orientation() == Qt.Orientation.Vertical
    assert screen.progress_scroll.isHidden()
    screen._on_stage_progress("prepare", None)
    QApplication.processEvents()
    assert screen.progress_scroll.isVisible()
    assert screen.progress_scroll.width() == screen.log_details.width()
    assert screen.log_details.y() > screen.progress_scroll.y()
    collapsed_height = screen.log_details.height()
    assert collapsed_height == screen.log_details.toggle.sizeHint().height()
    screen.log.log("Decoder failure", "error")
    QApplication.processEvents()
    assert screen.log_details.height() > collapsed_height
    assert screen.log.text.isVisible()
    assert window.rect().contains(
        screen.log.text.mapTo(window, screen.log.text.rect().bottomRight()),
    )
    assert screen.progress_scroll.width() == screen.log_details.width()
    assert window.rect().contains(screen.run_btn.mapTo(window, screen.run_btn.rect().bottomRight()))
    screen.log_details.toggle.click()
    QApplication.processEvents()
    assert screen.log_details.height() == collapsed_height
    assert screen.log_details.content.isHidden()
    old.deleteLater()


@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_file_selection_precedes_preview_and_sample_action_needs_no_disclosure(
    gui_window_factory, size,
):
    window = gui_window_factory()
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    screen = window.stack.widget(0)
    source_top = screen.input_picker.mapTo(window, screen.input_picker.rect().topLeft())
    output_top = screen.output_picker.mapTo(window, screen.output_picker.rect().topLeft())
    assert source_top.y() == output_top.y()
    assert screen.input_picker.mapTo(window, screen.input_picker.rect().bottomRight()).y() < (
        screen.preview.mapTo(window, screen.preview.rect().topLeft()).y()
    )
    assert source_top.x() < output_top.x()
    assert screen.sample_btn.isVisible()
    assert screen.sample_controls.content.isHidden()
    assert screen.profile_details.content.isHidden()
    assert not screen.profile_combo.isVisible()
    assert not screen.progress_label.isVisible()
    assert window.rect().contains(
        screen.sample_btn.mapTo(window, screen.sample_btn.rect().center()),
    )
    screen.sample_controls.set_expanded(True)
    screen.settings_scroll.verticalScrollBar().setValue(10_000)
    QApplication.processEvents()
    assert window.rect().contains(
        screen.sample_btn.mapTo(window, screen.sample_btn.rect().bottomRight()),
    )


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_workspace_controls_and_disclosures_keep_their_panel_insets(
    gui_window_factory, size, theme,
):
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    screen = window.stack.widget(0)
    preview = screen.preview
    sound_right = preview.sound.mapTo(preview, preview.sound.rect().bottomRight()).x()
    timecode_bottom = preview.position.mapTo(preview, preview.position.rect().bottomRight()).y()
    assert preview.width() - 1 - sound_right >= Space.MD
    assert preview.height() - 1 - timecode_bottom >= Space.MD
    panel = screen.settings_panel
    sample = screen.sample_btn
    assert sample.mapTo(panel, sample.rect().topLeft()).x() >= Space.MD
    corner = sample.mapTo(panel, sample.rect().bottomRight())
    assert panel.width() - 1 - corner.x() >= Space.MD
    assert panel.height() - 1 - corner.y() >= Space.MD
    disclosures = (screen.profile_details, screen.sample_controls, screen.advanced)
    for disclosure in disclosures:
        disclosure.set_expanded(True)
    QApplication.processEvents()
    toggle_left = [d.toggle.mapTo(screen.settings_content, d.toggle.rect().topLeft()).x()
                   for d in disclosures]
    assert toggle_left == [Space.MD] * len(disclosures)
    for disclosure, control in (
        (screen.sample_controls, screen.sample_start),
        (screen.advanced, screen.profile_combo),
    ):
        content = disclosure.content
        assert control.mapTo(content, control.rect().topLeft()).x() >= Space.SM
        right = control.mapTo(content, control.rect().bottomRight()).x()
        assert content.width() - 1 - right >= Space.SM


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("checked, enabled", [(False, True), (True, True), (True, False)])
def test_every_page_uses_the_same_checkbox_indicator(
    gui_window_factory, theme, checked, enabled,
):
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.show()
    indicators = []
    for page in range(window.stack.count()):
        window.sidebar.setCurrentRow(page)
        for checkbox in window.stack.widget(page).findChildren(QCheckBox):
            if isinstance(checkbox, TableSelectionCheckBox) and not checkbox.isVisible():
                # Tables with hidden headers have no visible corner control to compare.
                continue
            checkbox.setChecked(checked)
            checkbox.setEnabled(enabled)
            checkbox.clearFocus()
            QApplication.processEvents()
            option = QStyleOptionButton()
            checkbox.initStyleOption(option)
            rect = checkbox.style().subElementRect(
                QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox,
            )
            indicators.append(checkbox.grab().toImage().copy(rect))
    assert len(indicators) >= 9
    assert all(indicator == indicators[0] for indicator in indicators)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_profile_table_checkbox_matches_standalone_controls(gui_window_factory, qtbot, theme):
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.show()
    checkbox = window.stack.widget(0).preview.sound
    checkbox.setChecked(True)
    QApplication.processEvents()
    option = QStyleOptionButton()
    checkbox.initStyleOption(option)
    rect = checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox)
    reference = checkbox.grab().toImage().copy(rect)
    window.sidebar.setCurrentRow(4)
    table = window.stack.widget(4).table
    QApplication.processEvents()
    index = table.model().index(0, 1)
    assert index.isValid()
    item_option = QStyleOptionViewItem()
    item_option.initFrom(table)
    item_option.widget = table
    delegate = QStyledItemDelegate(table)
    delegate.initStyleOption(item_option, index)
    item_option.rect = table.visualRect(index)
    item_rect = table.style().subElementRect(
        QStyle.SubElement.SE_ItemViewItemCheckIndicator, item_option, table,
    )
    actual = table.viewport().grab().toImage().copy(item_rect)
    assert actual.size() == reference.size()
    inset = Space.XS
    interior = actual.rect().adjusted(inset, inset, -inset, -inset)
    assert actual.copy(interior) == reference.copy(interior)
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=item_rect.center())
    assert table.item(0, 1).checkState() == Qt.CheckState.Unchecked


def test_compact_profile_selection_and_custom_controls_remain_reachable(
    gui_window_factory, qtbot, tmp_path,
):
    window = gui_window_factory()
    window.show()
    screen = window.stack.widget(0)
    qtbot.mouseClick(screen.profile_cards.buttons["medium"], Qt.MouseButton.LeftButton)
    assert Path(screen.profile_combo.currentData()).stem == "medium"
    screen.profile_details.toggle.click()
    assert not screen.profile_cards.details.isHidden()
    assert screen.profile_cards.details.text()
    custom = tmp_path / "custom.yaml"
    screen.profile_combo.addItem("custom", str(custom))
    screen.profile_combo.setCurrentIndex(screen.profile_combo.count() - 1)
    QApplication.processEvents()
    assert screen.profile_details.isHidden()
    assert screen.advanced.content.isVisible()
    assert screen.profile_combo.isVisible()
    assert screen.state.profile_path == custom


def test_completed_result_reveals_its_status_and_actions(gui_window_factory, qtbot, tmp_path):
    window = gui_window_factory()
    window.resize(1440, 900)
    window.show()
    screen = window.stack.widget(0)
    screen.processing_status.start()
    screen._on_stage_progress("quality", None)
    output = tmp_path / "completed.mp4"
    screen._on_done(str(output), "")
    qtbot.waitUntil(lambda: screen.progress_scroll.isVisible())
    QApplication.processEvents()
    viewport = screen.progress_scroll.viewport()
    for control in (screen.status_label, screen.open_output_btn, screen.compare_btn):
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().topLeft()))
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().bottomRight()))
    assert "completed.mp4" in screen.status_label.text()


def test_motion_setting_aligns_with_fields_and_persists(qtbot, qapp):
    settings = SettingsScreen(AppState())
    qtbot.addWidget(settings)
    settings.resize(870, 720)
    settings.show()
    QApplication.processEvents()
    checkbox = settings.reduced_motion_check
    assert checkbox.x() == settings.theme_combo.x() == settings.language_combo.x()
    assert checkbox.y() > settings.language_combo.y()
    qtbot.keyClick(checkbox, Qt.Key.Key_Space)
    assert settings.state.reduced_motion
    settings.state.save()
    assert AppState().reduced_motion
    install_translator(qapp, "ru_RU")
    QApplication.processEvents()
    assert settings.motion_label.text() == "Анимация:"
    assert checkbox.accessibleName() == "Уменьшить анимацию интерфейса"


def test_disclosure_animation_respects_saved_motion_preference(qtbot):
    state = AppState()
    disclosure = Disclosure("Details", state=state)
    disclosure.body.addWidget(QPushButton("Detail action"))
    qtbot.addWidget(disclosure)
    disclosure.show()
    disclosure.toggle.click()
    assert disclosure._animation.state() == QAbstractAnimation.State.Running
    qtbot.waitUntil(lambda: disclosure._animation.state() == QAbstractAnimation.State.Stopped)
    assert not disclosure._fade.isEnabled()
    disclosure.set_expanded(False)
    state.set_reduced_motion(True)
    state.save()
    assert AppState().reduced_motion
    disclosure.toggle.click()
    assert disclosure.content.isVisible()
    assert disclosure._animation.state() == QAbstractAnimation.State.Stopped


def test_disclosure_destruction_disconnects_a_surviving_animation(qtbot):
    disclosure = Disclosure("Details")
    disclosure.body.addWidget(QPushButton("Detail action"))
    disclosure.show()
    disclosure.toggle.click()
    animation = disclosure._animation
    animation.stop()
    # Keep the signal sender alive to exercise receiver destruction explicitly.
    animation.setParent(None)
    disclosure.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert sip.isdeleted(disclosure)
    animation.finished.emit()
    QApplication.processEvents()
    animation.deleteLater()


def test_unavailable_preview_keeps_workflow_usable_and_closes(qtbot, tmp_path):
    preview = StudioPreview()
    qtbot.addWidget(preview)
    preview.set_source(tmp_path / "missing.mp4")
    assert preview.stage.currentWidget() == preview.empty
    assert not preview.play_button.isEnabled()
    preview.shutdown()
    assert preview.player.source().isEmpty()


def test_batch_updates_correct_file_after_sort_and_counts_terminal_once(qtbot, tmp_path):
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        (tmp_path / name).touch()
    screen = BatchScreen(AppState())
    qtbot.addWidget(screen)
    screen.input_dir = tmp_path
    screen.output_dir = tmp_path / "out"
    screen._refresh_preview()
    screen.table.sortItems(0, Qt.SortOrder.DescendingOrder)
    screen.progress_bar.setRange(0, 3)
    screen._set_status(str(tmp_path / "a.mp4"), "done", out=str(tmp_path / "out/a.mp4"))
    screen._set_status(str(tmp_path / "a.mp4"), "done")
    assert screen.progress_bar.value() == 1
    row = screen.table.find_key(str(tmp_path / "a.mp4"))
    assert screen.table.item(row, 1).data(STATUS_ROLE) == "done"
    assert screen.table.item(row, 2).toolTip() == str(tmp_path / "out/a.mp4")
    assert screen.table.action_path(row) == str(tmp_path / "out/a.mp4")
    assert screen.table.row_key(row) == str(tmp_path / "a.mp4")


def test_batch_selected_scope_is_snapshot_and_filter_does_not_change_full_scope(qtbot, tmp_path):
    for name in ("a.mp4", "b.mp4"):
        (tmp_path / name).touch()
    screen = BatchScreen(AppState())
    qtbot.addWidget(screen)
    screen.input_dir, screen.output_dir = tmp_path, tmp_path / "out"
    screen._refresh_preview()
    screen.table_tools.search.setText("a.mp4")
    screen.table.select_visible()
    with patch.object(screen, "_start_batch") as start:
        screen._on_run_selected()
        assert start.call_args.args[0] == [tmp_path / "a.mp4"]
        screen._on_run()
        assert set(start.call_args.args[0]) == {tmp_path / "a.mp4", tmp_path / "b.mp4"}


def test_queue_ignores_stale_root_and_identical_snapshot(qtbot, tmp_path):
    screen = QueueScreen(AppState())
    qtbot.addWidget(screen)
    screen.queue_root = tmp_path
    path = str(tmp_path / "pending/a.mp4")
    rows = ((path, "pending"),)
    screen._on_files(tmp_path, rows)
    row = screen.table.find_key(path)
    widget = screen.table.cellWidget(row, 3)
    screen.table.selectRow(row)
    screen._on_files(tmp_path, rows)
    assert screen.table.cellWidget(row, 3) is widget
    assert screen.table.selected_keys() == [path]
    screen._on_files(tmp_path / "old", ())
    assert screen.table.rowCount() == 1
    screen._on_files(tmp_path, ())
    assert screen.table.rowCount() == 0


def test_table_live_language_and_theme_keep_status_filter_and_selection(qtbot, qapp):
    state = AppState()
    table, tools = make_table(qtbot, state)
    table.set_headers(["File", "Status", "Actions"])
    tools.status.setCurrentIndex(tools.status.findData("done"))
    table.select_visible()
    install_translator(qapp, "ru_RU")
    qapp.processEvents()
    row = table.find_key("a.mp4")
    assert table.horizontalHeaderItem(1).text() == "Статус"
    assert table.item(row, 1).text() == "Готово"
    assert table.selected_keys() == ["a.mp4"]
    button = table.cellWidget(row, 2).findChildren(QPushButton)[0]
    assert button.accessibleName() == "Открыть файл"
    state.set_theme("light")
    assert not button.icon().isNull()
    assert tools.status.currentData() == "done"
