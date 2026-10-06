"""Real corner-checkbox selection, filtering and centered footer regressions."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QItemSelectionModel, QPoint, Qt
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from video_uniquifier import __version__
from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.widgets.table_selection import (
    TableSelectionCheckBox,
    install_selection_checkbox,
)


@pytest.fixture
def table(qtbot):
    table = QTableWidget(3, 3)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    for row in range(3):
        for column in range(3):
            item = QTableWidgetItem(f"{row}:{column}")
            if column == 1:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            table.setItem(row, column, item)
    install_selection_checkbox(table)
    qtbot.addWidget(table)
    table.resize(480, 300)
    table.show()
    return table


def test_corner_toggles_rows_with_partial_feedback_without_changing_effects(table, qtbot):
    checkbox = table.findChild(TableSelectionCheckBox)
    assert checkbox.checkState() == Qt.CheckState.Unchecked
    table.selectRow(0)
    assert checkbox.checkState() == Qt.CheckState.PartiallyChecked
    # The whole header corner is clickable, including outside the indicator.
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))
    assert checkbox.checkState() == Qt.CheckState.Checked
    assert {index.row() for index in table.selectedIndexes()} == {0, 1, 2}
    assert all(table.item(row, 1).checkState() == Qt.CheckState.Checked for row in range(3))
    qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)
    assert not table.selectedIndexes()
    checkbox.setFocus()
    qtbot.keyClick(checkbox, Qt.Key.Key_Space)
    assert checkbox.checkState() == Qt.CheckState.Checked
    assert checkbox.geometry() == checkbox.parentWidget().rect()


def test_partial_cell_selection_and_nonselectable_rows(table):
    checkbox = table.findChild(TableSelectionCheckBox)
    table.selectionModel().select(table.model().index(0, 0),
                                  QItemSelectionModel.SelectionFlag.Select)
    assert checkbox.checkState() == Qt.CheckState.PartiallyChecked
    for column in range(3):
        table.item(2, column).setFlags(Qt.ItemFlag.ItemIsEnabled)
    checkbox.click()
    assert {index.row() for index in table.selectedIndexes()} == {0, 1}
    assert checkbox.checkState() == Qt.CheckState.Checked


def test_empty_and_single_selection_tables_do_not_offer_select_all(table):
    checkbox = table.findChild(TableSelectionCheckBox)
    table.setRowCount(0)
    assert not checkbox.isEnabled()
    assert checkbox.checkState() == Qt.CheckState.Unchecked
    table.insertRow(0)
    table.setItem(0, 0, QTableWidgetItem("Added file"))
    assert checkbox.isEnabled()
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    checkbox.refresh()
    assert not checkbox.isEnabled()


def test_corner_installation_ignores_private_class_names_and_cell_buttons(qtbot, monkeypatch):
    table = QTableWidget(1, 1)
    qtbot.addWidget(table)
    table.setItem(0, 0, QTableWidgetItem("File"))
    action = QPushButton("Open file")
    table.setCellWidget(0, 0, action)
    corner = table.findChild(QAbstractButton, options=Qt.FindChildOption.FindDirectChildrenOnly)
    assert corner is not None
    monkeypatch.setattr(corner, "metaObject", lambda: QAbstractButton.staticMetaObject)
    checkbox = install_selection_checkbox(table)
    table.show()
    assert checkbox.parentWidget() is corner
    assert checkbox.parentWidget() is not action
    checkbox.click()
    assert table.selectedIndexes()


def test_table_filter_selects_only_visible_rows_and_updates_corner(gui_window_factory, qapp):
    window = gui_window_factory()
    window.show()
    window.sidebar.setCurrentRow(1)
    screen = window.stack.widget(1)
    table = screen.table
    with table.updating():
        for row, name in enumerate(("alpha.mp4", "beta.mp4")):
            table.insertRow(row)
            table.setItem(row, 0, table.file_item(name, name, f"/example/{name}"))
    checkbox = table.selection_checkbox
    checkbox.click()
    assert checkbox.checkState() == Qt.CheckState.Checked
    screen.table_tools.search.setText("alpha")
    assert table.selected_keys() == ["alpha.mp4"]
    assert checkbox.checkState() == Qt.CheckState.Checked
    screen.table_tools.search.clear()
    assert checkbox.checkState() == Qt.CheckState.PartiallyChecked
    screen.table_tools.search.setText("beta")
    assert checkbox.checkState() == Qt.CheckState.Unchecked
    checkbox.click()
    assert table.selected_keys() == ["beta.mp4"]
    screen.table_tools.search.setText("no match")
    assert not checkbox.isEnabled()


@pytest.mark.parametrize("size", [(980, 640), (1360, 900)])
def test_all_page_tables_have_explicit_selection_and_footer_stays_centered(
    gui_window_factory, qapp, size,
):
    window = gui_window_factory()
    window.resize(*size)
    window.show()
    for index in range(window.stack.count()):
        window.sidebar.setCurrentRow(index)
        qapp.processEvents()
        for table in window.stack.widget(index).findChildren(QTableWidget):
            checkbox = table.findChild(TableSelectionCheckBox)
            assert checkbox is not None
            assert install_selection_checkbox(table) is checkbox
    footer = window.status_note
    assert f"v{__version__}" in footer.text()
    assert "Ready" in footer.text()
    assert footer.alignment() == Qt.AlignmentFlag.AlignCenter
    assert abs(footer.mapTo(window, footer.rect().center()).x() - window.rect().center().x()) <= 4
    assert footer.isVisible()
    previous = active_locale()
    try:
        install_translator(qapp, "ru_RU")
        qapp.processEvents()
        assert "Готово к работе" in footer.text()
        assert f"v{__version__}" in footer.text()
        assert checkbox.accessibleName() == "Выбрать все видимые строки"
    finally:
        install_translator(qapp, previous)
