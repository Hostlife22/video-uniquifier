"""Keyboard-accessible navigation between focused desktop workspaces."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QSizePolicy

from video_uniquifier.gui.design import Space


class WorkflowNavigation(QFrame):
    currentChanged = pyqtSignal(int)

    def __init__(self, titles: tuple[str, ...]) -> None:
        super().__init__()
        self.titles = titles
        self._index = 0
        self.setObjectName("workflow_navigation")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Space.SM)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for index in range(len(titles)):
            button = QPushButton()
            button.setObjectName("workflow_nav")
            button.setCheckable(True)
            button.setMinimumHeight(52)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(button, index)
            row.addWidget(button, stretch=1)
            self.buttons.append(button)
        self.group.idClicked.connect(self.setCurrentIndex)
        self.buttons[0].setChecked(True)
        self._retranslate()

    def currentIndex(self) -> int:
        return self._index

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self.buttons):
            return
        self.buttons[index].setChecked(True)
        if self._index != index:
            self._index = index
            self.currentChanged.emit(index)

    def _retranslate(self) -> None:
        for index, (button, title) in enumerate(zip(self.buttons, self.titles, strict=True)):
            button.setText(f"{index + 1:02}  {self.tr(title)}")
            button.setAccessibleName(f"{index + 1}. {self.tr(title)}")

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
