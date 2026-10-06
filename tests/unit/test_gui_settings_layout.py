"""Settings layout and readable saved-state feedback."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication, QFormLayout, QGroupBox, QLabel

from video_uniquifier.core import telemetry
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.screens.settings import SettingsScreen
from video_uniquifier.gui.state import AppState


@pytest.fixture
def settings(qtbot, qapp, monkeypatch, tmp_path):
    previous = active_locale()
    install_translator(qapp, "en_US")
    folder = tmp_path / ("long-folder-name-" * 10) / "events"
    monkeypatch.setattr(telemetry, "default_events_dir", lambda: folder)
    monkeypatch.setattr(telemetry, "event_count", lambda _root: 3)
    monkeypatch.setattr(telemetry, "write_consent_marker", lambda _enabled: None)
    screen = SettingsScreen(AppState())
    qtbot.addWidget(screen)
    screen.resize(760, 700)
    screen.show()
    yield screen, folder
    install_translator(qapp, previous)


def test_telemetry_status_describes_saved_choice_and_keeps_path_separate(settings):
    screen, folder = settings
    screen.telemetry_details.set_expanded(True)
    QApplication.processEvents()
    assert screen.telemetry_status_label.text() == "Recording is off · Saved events: 3"
    assert screen.telemetry_folder_label.toolTip() == str(folder)
    assert str(folder) not in screen.telemetry_status_label.text()
    assert not screen.telemetry_details.findChildren(QGroupBox)[0].title()
    screen.telemetry_enabled_check.setChecked(True)
    assert screen.telemetry_status_label.text().startswith("Recording is off")
    screen.telemetry_apply_btn.click()
    assert screen.telemetry_status_label.text() == "Recording is on · Saved events: 3"
    assert AppState().telemetry.enabled


def test_settings_labels_center_on_fields_in_expanded_sections(settings):
    screen, _folder = settings
    screen.notifications_details.set_expanded(True)
    screen.telemetry_details.set_expanded(True)
    QApplication.processEvents()
    checked_rows = 0
    for form in screen.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label_item is None or field_item is None:
                continue
            label, field = label_item.widget(), field_item.widget()
            if not isinstance(label, QLabel) or field is None or not field.isVisible():
                continue
            assert abs(label.geometry().center().y() - field.geometry().center().y()) <= 1
            checked_rows += 1
    assert checked_rows >= 15


def test_saved_feedback_is_in_action_bar_and_localized(settings, qapp):
    screen, _folder = settings
    screen.save_btn.click()
    QApplication.processEvents()
    assert screen.status_label.text() == "Preferences saved."
    assert screen.status_label.parentWidget() is screen.save_btn.parentWidget()
    assert screen.rect().contains(
        screen.status_label.mapTo(screen, screen.status_label.rect().center()),
    )
    install_translator(qapp, "ru_RU")
    QApplication.processEvents()
    screen.save_btn.click()
    assert screen.status_label.text() == "Настройки сохранены."
    assert screen.telemetry_status_label.text() == "Запись выключена · Сохранено событий: 3"


def test_telemetry_read_error_is_readable_and_details_remain_available(settings, monkeypatch):
    screen, _folder = settings

    def fail_count(_root):
        raise OSError("Cannot read events")

    monkeypatch.setattr(telemetry, "event_count", fail_count)
    screen._refresh_telemetry_status()
    assert screen.telemetry_status_label.text() == "Status unavailable"
    assert screen.telemetry_status_label.toolTip() == "Cannot read events"
