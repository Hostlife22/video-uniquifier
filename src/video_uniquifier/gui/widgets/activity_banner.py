"""Persistent task summaries while navigating away from processing pages."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from video_uniquifier.gui.design import Space


class ActivityBanner(QWidget):
    requested = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("action_bar")
        self.tasks = QComboBox()
        self.tasks.setAccessibleName(self.tr("Active tasks"))
        self.tasks.setMinimumContentsLength(18)
        self.details = QLabel()
        self.details.setObjectName("hint")
        self.details.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setAccessibleName(self.tr("Task progress"))
        self.progress.setTextVisible(False)
        self.return_btn = QPushButton(self.tr("Return to task"))
        self.return_btn.clicked.connect(self._return)
        self.tasks.currentIndexChanged.connect(self._select)
        row = QHBoxLayout(self)
        row.setContentsMargins(Space.LG, Space.MD, Space.LG, Space.MD)
        row.setSpacing(Space.MD)
        row.addWidget(self.tasks)
        row.addWidget(self.details, stretch=1)
        row.addWidget(self.progress, stretch=1)
        row.addWidget(self.return_btn)
        self._records: dict[int, tuple[str, float | None]] = {}
        self.hide()

    def set_tasks(self, tasks: list[tuple[int, str, str, float | None]]) -> None:
        current = self.tasks.currentData()
        self._records = {index: (details, fraction) for index, _label, details, fraction in tasks}
        existing = [(self.tasks.itemData(i), self.tasks.itemText(i))
                    for i in range(self.tasks.count())]
        if existing != [(index, label) for index, label, _details, _fraction in tasks]:
            # Progress polling must not reset a dropdown the user is navigating.
            block = self.tasks.blockSignals(True)
            self.tasks.clear()
            for index, label, _details, _fraction in tasks:
                self.tasks.addItem(label, index)
            selected = self.tasks.findData(current)
            if selected >= 0:
                self.tasks.setCurrentIndex(selected)
            self.tasks.blockSignals(block)
        self.tasks.setVisible(len(tasks) > 1)
        self.setVisible(bool(tasks))
        self._select()

    def _select(self) -> None:
        index = self.tasks.currentData()
        if index not in self._records:
            return
        details, fraction = self._records[index]
        self.details.setText(details)
        self.details.setToolTip(details)
        self.progress.setRange(0, 0 if fraction is None else 1000)
        if fraction is not None:
            self.progress.setValue(round(min(max(fraction, 0), 1) * 1000))

    def _return(self) -> None:
        index = self.tasks.currentData()
        if isinstance(index, int):
            self.requested.emit(index)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.return_btn.setText(self.tr("Return to task"))
            self.tasks.setAccessibleName(self.tr("Active tasks"))
            self.progress.setAccessibleName(self.tr("Task progress"))
        super().changeEvent(event)
