"""Rounded frames keep their opaque child widgets away from every corner."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QStyle,
    QStyleOptionTabWidgetFrame,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)

from video_uniquifier.gui.design import Metrics
from video_uniquifier.gui.theme import qss_for


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_table_headers_and_scrollbars_leave_room_for_the_frame_corners(qtbot, theme):
    table = QTableWidget(30, 3)
    qtbot.addWidget(table)
    table.setStyleSheet(qss_for(theme))
    table.setHorizontalHeaderLabels(["File", "Status", "Path"])
    for row in range(table.rowCount()):
        table.setItem(row, 0, QTableWidgetItem(f"Video {row}"))
    table.resize(380, 260)
    table.show()
    QApplication.processEvents()
    interior = table.rect().adjusted(
        Metrics.CONTROL_RADIUS, Metrics.CONTROL_RADIUS,
        -Metrics.CONTROL_RADIUS, -Metrics.CONTROL_RADIUS,
    )
    for child in (table.viewport(), table.horizontalHeader(), table.verticalHeader(),
                  table.horizontalScrollBar(), table.verticalScrollBar()):
        if child.isVisible():
            assert interior.contains(child.mapTo(table, child.rect().topLeft()))
            assert interior.contains(child.mapTo(table, child.rect().bottomRight()))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_tab_page_background_does_not_cover_rounded_pane_corners(qtbot, theme):
    tabs = QTabWidget()
    qtbot.addWidget(tabs)
    tabs.setStyleSheet(qss_for(theme))
    page = QWidget()
    tabs.addTab(page, "Report")
    tabs.resize(380, 260)
    tabs.show()
    QApplication.processEvents()
    option = QStyleOptionTabWidgetFrame()
    tabs.initStyleOption(option)
    frame = tabs.style().subElementRect(QStyle.SubElement.SE_TabWidgetTabPane, option, tabs)
    interior = frame.adjusted(
        Metrics.CONTROL_RADIUS, Metrics.CONTROL_RADIUS,
        -Metrics.CONTROL_RADIUS, -Metrics.CONTROL_RADIUS,
    )
    assert interior.contains(page.mapTo(tabs, page.rect().topLeft()))
    assert interior.contains(page.mapTo(tabs, page.rect().bottomRight()))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_table_corner_matches_header_and_still_selects_all_cells(qtbot, theme):
    from PyQt6.QtCore import Qt

    table = QTableWidget(2, 2)
    qtbot.addWidget(table)
    table.setStyleSheet(qss_for(theme))
    for row in range(2):
        for column in range(2):
            table.setItem(row, column, QTableWidgetItem(f"{row}:{column}"))
    table.resize(380, 260)
    table.show()
    QApplication.processEvents()
    corner = table.findChild(QAbstractButton)
    assert corner is not None
    header = table.horizontalHeader()
    corner_image = corner.grab().toImage()
    header_image = header.grab().toImage()
    # Sample the empty header background away from labels and borders.
    assert corner_image.pixelColor(corner_image.rect().center()) == header_image.pixelColor(2, 2)
    qtbot.mouseClick(corner, Qt.MouseButton.LeftButton)
    assert len(table.selectedIndexes()) == 4
