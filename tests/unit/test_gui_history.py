"""HistoryScreen + RunWorker history integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from video_uniquifier.gui.screens.history import HistoryScreen
from video_uniquifier.gui.state import AppState, HistoryEntry


@pytest.fixture(scope="module")
def app(qapp) -> QApplication:
    return qapp


def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppState:
    monkeypatch.setattr("video_uniquifier.gui.state.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("video_uniquifier.gui.state.STATE_PATH", tmp_path / "s.json")
    monkeypatch.setattr("video_uniquifier.gui.state.HISTORY_PATH", tmp_path / "h.json")
    return AppState()


def _entry(i: int) -> HistoryEntry:
    return HistoryEntry(
        timestamp=f"2026-05-{i:02d}T12:00:00",
        source_path=f"/tmp/{i}.mp4",
        profile_name="cid_aware",
        encoder_name="libx264",
        output_path=f"/tmp/o{i}.mp4",
        qa_html_path=None,
        plan_hash=f"hash{i:04d}",
        status="done",
    )


def test_history_screen_renders_entries(qtbot, app: QApplication, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    state = _isolate_state(tmp_path, monkeypatch)
    state.push_history(_entry(1))
    state.push_history(_entry(2))
    screen = HistoryScreen(state)
    qtbot.addWidget(screen)
    assert screen.table.rowCount() == 2


def test_history_screen_filter(qtbot, app: QApplication, tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    state = _isolate_state(tmp_path, monkeypatch)
    state.push_history(_entry(1))
    state.push_history(_entry(2))
    screen = HistoryScreen(state)
    qtbot.addWidget(screen)
    screen.filter_edit.setText("nonexistent_term")
    assert screen.table.rowCount() == 0
    screen.filter_edit.setText("")
    assert screen.table.rowCount() == 2


def test_history_screen_auto_refresh_on_push(qtbot, app: QApplication, tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    state = _isolate_state(tmp_path, monkeypatch)
    screen = HistoryScreen(state)
    qtbot.addWidget(screen)
    assert screen.table.rowCount() == 0
    state.push_history(_entry(1))
    assert screen.table.rowCount() == 1
