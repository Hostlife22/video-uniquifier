"""Beginner help stays readable and usable without changing the working session."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from video_uniquifier.gui.app_pyqt import SIDEBAR_ITEMS
from video_uniquifier.gui.guides import GUIDES
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.i18n.translations import SOURCE_KEYS, TRANSLATIONS
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector


@pytest.fixture(autouse=True)
def quiet_help_session(qapp, monkeypatch):
    previous = active_locale()
    install_translator(qapp, "en_US")
    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    yield
    install_translator(qapp, previous)


@pytest.mark.parametrize("locale", ["en_US", "ru_RU"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_page_has_readable_optional_help_at_minimum_window_size(
    qtbot, qapp, gui_window_factory, locale, theme,
):
    install_translator(qapp, locale)
    window = gui_window_factory()
    window.state.set_theme(theme)
    window.resize(980, 640)
    window.show()
    for index, _item in enumerate(SIDEBAR_ITEMS):
        window.sidebar.setCurrentRow(index)
        qapp.processEvents()
        screen = window.stack.currentWidget()
        assert isinstance(screen, ScreenBase)
        button, guide = screen.help_button, screen.guide_panel
        assert button is not None and guide is not None
        assert guide.isHidden()
        assert not button.isChecked()
        assert button.accessibleDescription()
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert guide.isVisible() and button.isChecked()
        assert window.isEnabled() and screen.page_scroll.isEnabled()
        assert guide.width() <= screen.page_scroll.viewport().width()
        for label in guide.findChildren(QLabel):
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width())
        screen.page_scroll.ensureWidgetVisible(guide.close_button)
        qtbot.mouseClick(guide.close_button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert guide.isHidden() and not button.isChecked()
        assert button.hasFocus()


def test_f1_opens_current_page_help_from_navigation_and_leaves_other_pages_alone(
    qtbot, qapp, gui_window_factory,
):
    window = gui_window_factory()
    window.show()
    window.activateWindow()
    window.sidebar.setFocus()
    qapp.processEvents()
    first = window.stack.currentWidget()
    qtbot.keyClick(window.sidebar, Qt.Key.Key_F1)
    assert first.guide_panel.isVisible()
    window.sidebar.setCurrentRow(9)
    settings = window.stack.currentWidget()
    qtbot.keyClick(window.sidebar, Qt.Key.Key_F1)
    assert settings.guide_panel.isVisible()
    assert first.help_button.isChecked()
    qtbot.keyClick(window.sidebar, Qt.Key.Key_F1)
    assert settings.guide_panel.isHidden()
    window.sidebar.setCurrentRow(0)
    assert first.guide_panel.isVisible()
    qtbot.keyClick(window.sidebar, Qt.Key.Key_F1)
    assert first.guide_panel.isHidden()


def test_live_language_change_translates_open_help_without_changing_inputs(
    qtbot, qapp, gui_window_factory, tmp_path,
):
    window = gui_window_factory()
    window.show()
    screen = window.stack.currentWidget()
    screen.output_picker.set_path(tmp_path / "result.mp4")
    profile = screen.profile_combo.currentData()
    enabled = screen.run_btn.isEnabled()
    screen.toggle_guide()
    install_translator(qapp, "ru_RU")
    qapp.processEvents()
    assert screen.help_button.text() == "Как пользоваться"
    assert screen.guide_panel.heading.text() == "Быстрый старт"
    assert screen.guide_panel.close_button.text() == "Скрыть подсказку"
    assert screen.guide_panel.isVisible()
    assert "Подсказка открыта" in screen.help_button.accessibleDescription()
    assert screen.output_picker.current_path() == tmp_path / "result.mp4"
    assert screen.profile_combo.currentData() == profile
    assert screen.run_btn.isEnabled() == enabled
    assert screen.run_worker is None
    assert screen._sample_worker is None
    install_translator(qapp, "en_US")
    qapp.processEvents()
    assert screen.help_button.text() == "How to use"
    assert screen.guide_panel.heading.text() == "Quick start"
    assert screen.guide_panel.isVisible()


def test_every_guide_sentence_has_a_catalogued_russian_translation():
    for guide in GUIDES.values():
        for source in (*guide.steps, *guide.terms, guide.tip):
            assert source in SOURCE_KEYS
            assert TRANSLATIONS["ru_RU"][source] != source


def test_help_with_large_text_scrolls_without_covering_primary_actions(
    qtbot, qapp, gui_window_factory,
):
    install_translator(qapp, "ru_RU")
    window = gui_window_factory()
    window.resize(980, 640)
    window.show()
    screen = window.stack.currentWidget()
    screen.toggle_guide()
    for label in screen.guide_panel.findChildren(QLabel):
        label.setStyleSheet("font-size: 20px;")
    qapp.processEvents()
    scrollbar = screen.page_scroll.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    qapp.processEvents()
    assert screen.run_btn.isVisible()
    assert window.rect().contains(screen.run_btn.mapTo(window, screen.run_btn.rect().center()))
    for label in screen.guide_panel.findChildren(QLabel):
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
    screen.toggle_guide()
    assert screen.guide_panel.isHidden()
    screen.toggle_guide()
    qapp.processEvents()
    assert scrollbar.value() == 0
