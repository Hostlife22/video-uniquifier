"""An inline, dismissible quick start that keeps the working screen available."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QPushButton

from video_uniquifier.gui.design import Space
from video_uniquifier.gui.guides import PageGuide
from video_uniquifier.gui.widgets.surfaces import SectionCard


class GuidePanel(SectionCard):
    dismissed = pyqtSignal()

    def __init__(self, guide: PageGuide) -> None:
        super().__init__("Quick start")
        self.setAccessibleName(self.tr("Quick start"))
        self._texts: list[tuple[QLabel, str]] = []
        steps = QGridLayout()
        steps.setHorizontalSpacing(Space.MD)
        steps.setVerticalSpacing(Space.MD)
        steps.setColumnStretch(1, 1)
        for index, source in enumerate(guide.steps):
            number = QLabel(f"{index + 1:02}")
            number.setObjectName("eyebrow")
            steps.addWidget(number, index, 0, alignment=Qt.AlignmentFlag.AlignTop)
            steps.addWidget(self._label(source), index, 1)
        self.body.addLayout(steps)
        self.body.addWidget(self._label("Key terms", "field_label"))
        for source in guide.terms:
            self.body.addWidget(self._label(source))
        self.body.addWidget(self._label(guide.tip, "hint"))
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.dismissed)
        self.body.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._translate()

    def _label(self, source: str, role: str = "") -> QLabel:
        label = QLabel(self.tr(source))
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName(role)
        self._texts.append((label, source))
        return label

    def _translate(self) -> None:
        self.setAccessibleName(self.tr("Quick start"))
        for label, source in self._texts:
            label.setText(self.tr(source))
        self.close_button.setText(self.tr("Hide guide"))
        self.close_button.setAccessibleName(self.tr("Hide guide"))

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._translate()
        super().changeEvent(event)
