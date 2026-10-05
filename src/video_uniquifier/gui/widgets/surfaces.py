"""Reusable labelled surfaces and progressive disclosure for desktop screens."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.design import Metrics, Space


class FieldGrid(QWidget):
    """Labelled fields that wrap into two or three columns with the window."""

    def __init__(self) -> None:
        super().__init__()
        self._fields: list[QWidget] = []
        self._headings: list[tuple[QLabel, str]] = []
        self._columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(Space.LG)

    def add_field(self, label: str, control: QWidget) -> None:
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        heading = QLabel(self.tr(label))
        heading.setObjectName("field_label")
        heading.setBuddy(control)
        layout.addWidget(heading)
        layout.addWidget(control)
        self._fields.append(field)
        self._headings.append((heading, label))
        self._reflow()

    def _reflow(self) -> None:
        # Each field keeps enough space for a descriptive label and desktop control.
        columns = 3 if self.width() >= Metrics.GRID_WIDE else 2
        for index, field in enumerate(self._fields):
            self.grid.addWidget(field, index // columns, index % columns)
        for column in range(3):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self._columns = columns

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        columns = 3 if self.width() >= Metrics.GRID_WIDE else 2
        if columns != self._columns:
            self._reflow()

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            for heading, source in self._headings:
                heading.setText(self.tr(source))
        super().changeEvent(event)


class SectionCard(QFrame):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self._title_source = title
        self._description_source = description
        self.setObjectName("section_card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.LG)
        self.body.setSpacing(Space.MD)
        self.heading = QLabel(self.tr(title))
        self.heading.setObjectName("section_title")
        self.body.addWidget(self.heading)
        if description:
            self.hint = QLabel(self.tr(description))
            self.hint.setObjectName("hint")
            self.hint.setWordWrap(True)
            self.body.addWidget(self.hint)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.heading.setText(self.tr(self._title_source))
            if self._description_source:
                self.hint.setText(self.tr(self._description_source))
        super().changeEvent(event)


class Disclosure(QWidget):
    """Keyboard-operable disclosure; hidden controls leave the tab order."""

    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self._title = title
        self._description = description
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        self.toggle = QPushButton()
        self.toggle.setObjectName("disclosure")
        self.toggle.setCheckable(True)
        self.toggle.clicked.connect(self.set_expanded)
        mark(self.toggle, self.tr(title), self.tr(description))
        layout.addWidget(self.toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.content = QWidget()
        self.content.setObjectName("disclosure_content")
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(Space.MD)
        layout.addWidget(self.content)
        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self._retranslate()

    def _retranslate(self) -> None:
        expanded = self.toggle.isChecked()
        self.toggle.setText(("−  " if expanded else "+  ") + self.tr(self._title))
        self.toggle.setAccessibleName(self.tr(self._title))
        self.toggle.setAccessibleDescription(self.tr(self._description))

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
