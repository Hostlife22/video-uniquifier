"""Render populated status cells with the actual delegate and theme palettes."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QFontMetrics, QImage, QPainter
from PyQt6.QtWidgets import QStyleOptionViewItem

from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for
from video_uniquifier.gui.widgets.studio_table import StatusDelegate, StudioTable


@pytest.mark.parametrize("theme", ["dark", "light", "system"])
@pytest.mark.parametrize("status, background_token", [
    ("done", "badge_ok_bg"),
    ("failed", "badge_fail_bg"),
    ("running", "badge_warn_bg"),
    ("in_progress", "badge_warn_bg"),
    ("pending", "bg_alt"),
    ("cancelled", "bg_alt"),
    ("legacy-status", None),
])
def test_status_cells_render_without_palette_errors(qtbot, theme, status, background_token):
    state = AppState()
    table = StudioTable(2, state, "status-paint.header", 1)
    qtbot.addWidget(table)
    table.setRowCount(1)
    table.setItem(0, 1, table.status_item(status))
    # Switching a live table must use the new palette on its next repaint.
    state.set_theme(theme)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 200, 44)
    option.widget = table.viewport()
    option.font = table.font()
    option.fontMetrics = QFontMetrics(table.font())
    image = QImage(200, 44, QImage.Format.Format_ARGB32)
    image.fill(QColor("magenta"))
    delegate = table.itemDelegateForColumn(1)
    assert isinstance(delegate, StatusDelegate)
    painter = QPainter(image)
    try:
        delegate.paint(painter, option, table.model().index(0, 1))
    finally:
        painter.end()
    if background_token is not None:
        assert image.pixelColor(10, 22) == QColor(tokens_for(theme)[background_token])
