"""Chinese captions refresh without rebuilding widgets or altering user data."""

from __future__ import annotations

import ast
import string
from pathlib import Path

import pytest
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.i18n import coverage_ratio, install_translator
from video_uniquifier.gui.i18n.translations import SOURCE_KEYS, TRANSLATIONS
from video_uniquifier.gui.i18n.widgets import retranslate_widgets


@pytest.fixture(autouse=True)
def source_locale(qapp):
    install_translator(qapp, "en_US")
    yield
    install_translator(qapp, "en_US")
    qapp.processEvents()


def test_chinese_covers_source_inventory_and_preserves_format_fields():
    assert coverage_ratio("zh_CN") == 1.0
    formatter = string.Formatter()
    for source in SOURCE_KEYS:
        translated = TRANSLATIONS["zh_CN"][source]
        assert translated.strip()
        assert sorted(field for _, field, _, _ in formatter.parse(source) if field) == sorted(
            field for _, field, _, _ in formatter.parse(translated) if field
        ), source


def test_chinese_covers_literal_tr_calls_and_navigation():
    from video_uniquifier.gui import i18n
    from video_uniquifier.gui.guides import GUIDES
    from video_uniquifier.gui.widgets.navigation import NAV_GROUPS, NAV_LABELS

    sources = set(NAV_GROUPS.values()) | set(NAV_LABELS.values())
    for guide in GUIDES.values():
        sources.update((*guide.steps, *guide.terms, guide.tip))
    for path in Path(i18n.__file__).parent.parent.rglob("*.py"):
        if "i18n" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                sources.add(node.args[0].value)
    assert not sources - TRANSLATIONS["zh_CN"].keys()


def test_caption_refresh_preserves_paths_editor_contents_and_combo_data(qapp, qtbot):
    from video_uniquifier.gui.widgets.file_picker import PathLabel

    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    label = QLabel("Theme:")
    button = QPushButton("&Apply notifications")
    edit = QLineEdit("Output")  # User data that also happens to be a catalogue key.
    edit.setPlaceholderText("Search file, path or notes…")
    path = PathLabel("/a/very/long/directory/with/a/video/file.mp4")
    path.resize(25, 30)
    combo = QComboBox()
    combo.addItem("Dark studio", "dark")
    combo.addItem("Light", "light")
    combo.setCurrentIndex(1)
    table = QTableWidget(1, 1)
    table.setHorizontalHeaderLabels(["Status"])
    table.setItem(0, 0, QTableWidgetItem("Completed"))
    for widget in (label, button, edit, path, combo, table):
        layout.addWidget(widget)
    changes = []
    combo.currentTextChanged.connect(changes.append)
    original_path = path.toolTip()

    install_translator(qapp, "zh_CN")
    retranslate_widgets(root)
    retranslate_widgets(root)
    assert label.text() == "主题："
    assert button.text() == "应用通知设置(&A)"
    assert combo.currentText() == "浅色"
    assert combo.currentData() == "light"
    assert combo.currentIndex() == 1
    assert changes == []
    assert edit.text() == "Output"
    assert edit.placeholderText() == "搜索文件、路径或备注…"
    assert path.toolTip() == original_path
    assert path._full_text == original_path
    assert table.horizontalHeaderItem(0).text() == "状态"
    assert table.item(0, 0).text() == "Completed"

    install_translator(qapp, "en_US")
    retranslate_widgets(root)
    assert label.text() == "Theme:"
    assert button.text() == "&Apply notifications"
    assert combo.currentText() == "Light"
    assert changes == []


def test_changed_dynamic_caption_is_not_replaced_with_its_old_value(qapp, qtbot):
    label = QLabel("Ready")
    qtbot.addWidget(label)
    install_translator(qapp, "zh_CN")
    retranslate_widgets(label)
    label.setText("/custom/output.mp4")
    install_translator(qapp, "en_US")
    retranslate_widgets(label)
    assert label.text() == "/custom/output.mp4"


def test_settings_switches_live_and_preserves_unsaved_inputs(qapp, qtbot):
    from video_uniquifier.gui.screens.settings import SettingsScreen
    from video_uniquifier.gui.state import AppState

    screen = SettingsScreen(AppState())
    qtbot.addWidget(screen)
    screen.show()
    screen.webhook_url_edit.setText("https://example.com/my-hook")
    screen.notify_failed_check.setChecked(False)
    screen.language_combo.setCurrentIndex(screen.language_combo.findData("zh_CN"))
    qapp.processEvents()
    assert screen.page_title.text() == "设置"
    assert screen.help_button.text() == "使用说明"
    assert "外观" in [w.title() for w in screen.findChildren(QGroupBox)]
    assert screen.theme_combo.itemText(0) == "深色工作室"
    assert screen.save_btn.text() == "&保存"
    assert screen.notif_save_btn.text() == "应用通知设置(&A)"
    assert screen.notify_failed_check.text() == "任务失败时"
    assert screen.status_label.text() == "界面语言已切换为 zh_CN。"
    assert screen.webhook_url_edit.text() == "https://example.com/my-hook"
    assert not screen.notify_failed_check.isChecked()

    screen.language_combo.setCurrentIndex(screen.language_combo.findData("en_US"))
    qapp.processEvents()
    assert screen.page_title.text() == "Settings"
    assert screen.theme_combo.itemText(0) == "Dark studio"
    assert screen.notif_save_btn.text() == "&Apply notifications"
    assert screen.webhook_url_edit.text() == "https://example.com/my-hook"
    assert not screen.notify_failed_check.isChecked()


@pytest.mark.parametrize("boot_locale", ["en_US", "zh_CN"])
def test_every_page_uses_chinese_after_boot_or_language_switch(
    qapp, monkeypatch, gui_window_factory, boot_locale,
):
    from video_uniquifier.gui.app_pyqt import SIDEBAR_ITEMS
    from video_uniquifier.gui.state import AppState
    from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector
    from video_uniquifier.gui.widgets.navigation import NAV_GROUPS, NAV_LABELS

    monkeypatch.setattr(EncoderSelector, "_start_detection", lambda self: None)
    AppState().set_locale(boot_locale)
    install_translator(qapp, boot_locale)
    window = gui_window_factory()
    window.resize(980, 640)
    window.show()
    settings = window.stack.widget(9)
    settings.language_combo.setCurrentIndex(settings.language_combo.findData("zh_CN"))
    qapp.processEvents()
    from PyQt6.QtCore import QCoreApplication

    for group in NAV_GROUPS.values():
        assert QCoreApplication.translate("Navigation", group) == TRANSLATIONS["zh_CN"][group]
    for index, (source, _) in enumerate(SIDEBAR_ITEMS):
        page = window.stack.widget(index)
        window._navigate_to(source)
        qapp.processEvents()
        assert window.stack.widget(index) is page
        title = TRANSLATIONS["zh_CN"][NAV_LABELS[source]]
        assert window.sidebar_items[source].text() == title
        assert page.page_title.text() == title
        assert page.help_button.text() == "使用说明"
        page.toggle_guide()
        qapp.processEvents()
        assert page.guide_panel.heading.text() == "快速入门"
        for label in page.guide_panel.findChildren(QLabel):
            if label.wordWrap() and label.isVisible():
                assert label.height() >= label.heightForWidth(label.width())
    assert window.status_note.text().startswith("就绪  ·  本地处理")


def test_first_launch_consent_is_chinese_and_keeps_disabled_default(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from video_uniquifier.core import telemetry
    from video_uniquifier.gui.app_pyqt import _maybe_prompt_telemetry_consent

    decisions = []
    monkeypatch.setattr(telemetry, "has_consent_marker", lambda: False)
    monkeypatch.setattr(telemetry, "write_consent_marker", decisions.append)

    def inspect_dialog(box):
        # QMessageBox ignores its window title on macOS.
        assert box.text() == "是否通过本地使用统计帮助改进 video-uniquifier？"
        assert "当前版本不会通过网络发送数据" in box.informativeText()
        assert box.defaultButton().text() == "保持关闭(&K)"
        return 0

    monkeypatch.setattr(QMessageBox, "exec", inspect_dialog)
    install_translator(qapp, "zh_CN")
    _maybe_prompt_telemetry_consent()
    assert decisions == [False]
