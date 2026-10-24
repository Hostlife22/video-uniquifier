"""Actionable empty states and the import/preview/export overview."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QFileDialog

from video_uniquifier.gui.i18n import install_translator
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
from video_uniquifier.gui.widgets.studio_preview import StudioPreview
from video_uniquifier.gui.widgets.workflow_steps import WorkflowSteps
from video_uniquifier.gui.workers.probe_worker import ProbeWorker


@pytest.fixture(autouse=True)
def quiet_desktop(qapp, monkeypatch):
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    monkeypatch.setattr(ProbeWorker, "start", lambda self: None)
    yield
    install_translator(qapp, "en_US")


@pytest.mark.parametrize("stage, complete, expected", [
    (-1, False, ["current", "upcoming", "upcoming"]),
    (1, False, ["done", "current", "upcoming"]),
    (10, False, ["done", "done", "current"]),
    (2, True, ["done", "done", "done"]),
])
def test_steps_reflect_state_and_explain_it_accessibly(qtbot, stage, complete, expected):
    steps = WorkflowSteps()
    qtbot.addWidget(steps)
    steps.set_stage(stage, complete=complete)
    assert [item.property("state") for item, _, _ in steps._items] == expected
    for index, (item, title, hint) in enumerate(steps._items):
        assert item.accessibleName() == f"{index + 1}. {title.text()}: {hint.text()}"


def test_guidance_translates_without_resetting_the_current_step(qapp, qtbot):
    steps = WorkflowSteps()
    preview = StudioPreview()
    qtbot.addWidget(steps)
    qtbot.addWidget(preview)
    steps.set_stage(1)
    install_translator(qapp, "zh_CN")
    qapp.processEvents()
    assert steps._items[1][1].text() == "调整与预览"
    assert steps._items[1][2].text() == "当前步骤"
    assert preview.import_button.text() == "选择视频…"
    assert preview.empty_title.text() == "从一个视频开始"
    preview.shutdown()


def test_compact_steps_keep_titles_and_accessible_status(qtbot):
    steps = WorkflowSteps()
    qtbot.addWidget(steps)
    steps.set_stage(1)
    steps.show()
    steps.set_compact(True)
    for item, title, hint in steps._items:
        assert title.isVisible()
        assert hint.isHidden()
        assert hint.text() in item.accessibleName()
    steps.set_compact(False)
    assert all(hint.isVisible() for _, _, hint in steps._items)


@pytest.mark.parametrize("size", [(980, 640), (1280, 860)])
def test_empty_workspace_import_action_fits_and_reuses_the_picker(
    gui_window_factory, qtbot, monkeypatch, tmp_path, size,
):
    window = gui_window_factory()
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    screen = window.stack.widget(0)
    preview = screen.preview
    assert preview.mode_bar.isHidden()
    assert preview.transport_bar.isHidden()
    assert preview.position.isHidden()
    controls = (preview.empty_title, preview.empty_hint, preview.import_button)
    for control in controls:
        assert preview.empty.rect().contains(control.geometry())
    assert preview.empty_title.geometry().bottom() < preview.empty_hint.y()
    assert preview.empty_hint.geometry().bottom() < preview.import_button.y()
    path = tmp_path / "chosen.mp4"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: (str(path), ""))
    qtbot.mouseClick(preview.import_button, Qt.MouseButton.LeftButton)
    assert screen.state.input_path == path
    assert screen.workflow_steps._items[1][0].property("state") == "current"
    screen._on_done(str(tmp_path / "previous.mp4"), "")
    assert all(item.property("state") == "done" for item, _, _ in screen.workflow_steps._items)
    screen.input_picker.set_path(tmp_path / "next.mp4")
    assert screen.workflow_steps._items[2][0].property("state") == "upcoming"


def test_busy_processing_disables_import_and_advances_the_overview(gui_window_factory):
    window = gui_window_factory()
    screen = window.stack.widget(0)
    screen.run_worker = object()
    try:
        screen._refresh_run_button()
        assert not screen.preview.import_button.isEnabled()
        assert screen.workflow_steps._items[2][0].property("state") == "current"
    finally:
        screen.run_worker = None
        screen._refresh_run_button()
    assert screen.preview.import_button.isEnabled()


@pytest.mark.parametrize("kind, busy, accepted", [
    ("file", False, True), ("folder", False, False),
    ("missing", False, False), ("remote", False, False), ("file", True, False),
])
def test_preview_drop_accepts_only_available_local_files(qtbot, tmp_path, kind, busy, accepted):
    preview = StudioPreview()
    qtbot.addWidget(preview)
    video = tmp_path / "source.mp4"
    video.touch()
    paths = {"file": video, "folder": tmp_path, "missing": tmp_path / "missing.mp4"}
    url = QUrl("https://example.com/video.mp4") if kind == "remote" else (
        QUrl.fromLocalFile(str(paths[kind]))
    )
    data = QMimeData()
    data.setUrls([url])
    received: list[Path] = []
    preview.source_dropped.connect(received.append)
    preview.import_button.setEnabled(not busy)
    drag = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, data,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, data,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    preview.dragEnterEvent(drag)
    preview.dropEvent(drop)
    assert drag.isAccepted() == accepted
    assert drop.isAccepted() == accepted
    assert received == ([video] if accepted else [])
    preview.shutdown()
