"""Native event delivery must outlive a test helper's local widget reference."""

from __future__ import annotations

import gc

from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QWidget


def test_registered_widget_survives_until_queued_event_is_delivered(qtbot, qapp):
    delivered = []

    class Window(QWidget):
        def event(self, event):
            if event.type() == QEvent.Type.User:
                delivered.append(True)
                return True
            return super().event(event)

    def enqueue():
        window = Window()
        qtbot.addWidget(window)
        QCoreApplication.postEvent(window, QEvent(QEvent.Type.User))

    enqueue()
    gc.collect()
    qapp.processEvents()
    assert delivered == [True]
