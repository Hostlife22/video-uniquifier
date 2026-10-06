"""Styled numeric controls preserve stepping, limits and edit space."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox, QStyle, QStyleOptionSpinBox

from video_uniquifier.gui.theme import qss_for
from video_uniquifier.gui.widgets.sample_timeline import TimecodeSpinBox


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("widget_class", [QSpinBox, QDoubleSpinBox, TimecodeSpinBox])
def test_themed_arrows_step_without_overlapping_text(qtbot, theme, widget_class):
    spin = widget_class()
    qtbot.addWidget(spin)
    spin.setStyleSheet(qss_for(theme))
    spin.setRange(0, 1000)
    spin.setSingleStep(1)
    spin.setValue(5)
    spin.resize(240, 40)
    spin.show()
    option = QStyleOptionSpinBox()
    spin.initStyleOption(option)
    style = spin.style()
    up = style.subControlRect(
        QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxUp, spin,
    )
    down = style.subControlRect(
        QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxDown, spin,
    )
    editor = spin.lineEdit()
    assert editor is not None
    for rect in (up, down):
        assert not rect.isEmpty()
        assert spin.rect().contains(rect)
        assert not rect.intersects(editor.geometry())
    qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=up.center())
    assert spin.value() == 6
    qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=down.center())
    assert spin.value() == 5
    spin.setValue(spin.maximum())
    qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=up.center())
    assert spin.value() == spin.maximum()
    spin.setValue(spin.minimum())
    qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=down.center())
    assert spin.value() == spin.minimum()
    spin.setValue(5)
    spin.setFocus()
    qtbot.keyClick(spin, Qt.Key.Key_Up)
    assert spin.value() == 6
