"""Resizable studio panels with keyboard access and validated Qt state restore."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QEvent, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent, QPen, QShowEvent
from PyQt6.QtWidgets import QSplitter, QSplitterHandle, QWidget

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for


class StudioHandle(QSplitterHandle):
    def __init__(
        self, orientation: Qt.Orientation, parent: QSplitter, state: AppState,
    ) -> None:
        super().__init__(orientation, parent)
        self.state = state
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self.tr("Resize panels"))
        self.setToolTip(self.tr("Drag to resize; use arrow keys when focused."))

    def paintEvent(self, event: QPaintEvent | None) -> None:
        tokens = tokens_for(self.state.theme)
        painter = QPainter(self)
        painter.setPen(QPen(
            QColor(tokens["accent" if self.underMouse() or self.hasFocus() else "border"]),
            Metrics.SPLITTER_LINE,
        ))
        if self.orientation() == Qt.Orientation.Horizontal:
            center = self.width() // 2
            painter.drawLine(center, Space.SM, center, self.height() - Space.SM)
        else:
            center = self.height() // 2
            painter.drawLine(Space.MD, center, self.width() - Space.MD, center)
        painter.end()

    def event(self, event: QEvent | None) -> bool:
        handled = super().event(event)
        if event is not None and event.type() in (
            QEvent.Type.Enter, QEvent.Type.Leave, QEvent.Type.FocusIn, QEvent.Type.FocusOut,
        ):
            self.update()
        return handled

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.setAccessibleName(self.tr("Resize panels"))
            self.setToolTip(self.tr("Drag to resize; use arrow keys when focused."))
        super().changeEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        negative, positive = (
            (Qt.Key.Key_Left, Qt.Key.Key_Right)
            if self.orientation() == Qt.Orientation.Horizontal
            else (Qt.Key.Key_Up, Qt.Key.Key_Down)
        )
        if event.key() in (negative, positive):
            position = self.pos().x() if self.orientation() == Qt.Orientation.Horizontal \
                else self.pos().y()
            self.moveSplitter(position + (
                Metrics.SPLITTER_STEP if event.key() == positive else -Metrics.SPLITTER_STEP
            ))
            event.accept()
            return
        super().keyPressEvent(event)


class StudioSplitter(QSplitter):
    def __init__(self, orientation: Qt.Orientation, state: AppState, key: str) -> None:
        super().__init__(orientation)
        self.state = state
        self.key = key
        self.setHandleWidth(Metrics.SPLITTER_HANDLE)
        self.setChildrenCollapsible(False)
        self._restored = False
        self.splitterMoved.connect(self.remember)

    def createHandle(self) -> QSplitterHandle:
        return StudioHandle(self.orientation(), self, self.state)

    def remember(self, _position: int = 0, _index: int = 0) -> None:
        self.state.set_layout_state(self.key, self.saveState().toBase64().data().decode("ascii"))

    def showEvent(self, event: QShowEvent | None) -> None:
        if not self._restored:
            self._restored = True
            raw = self.state.layout_state(self.key)
            if raw:
                self.restoreState(QByteArray.fromBase64(raw.encode("ascii", errors="ignore")))
        super().showEvent(event)

    def addWidget(self, widget: QWidget | None) -> None:
        super().addWidget(widget)
        if widget is not None:
            widget.setMinimumSize(0, 0)
