"""A state indicator for the existing import, preview and export workflow."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from video_uniquifier.gui.design import Space

_STEPS = ("Import video", "Adjust and preview", "Export result")


class WorkflowSteps(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("workflow_steps")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._current = 0
        self._complete = False
        self._items: list[tuple[QFrame, QLabel, QLabel]] = []
        row = QHBoxLayout(self)
        row.setContentsMargins(Space.LG, Space.MD, Space.LG, Space.MD)
        row.setSpacing(Space.LG)
        for index in range(len(_STEPS)):
            item = QFrame()
            item.setObjectName("workflow_step")
            content = QHBoxLayout(item)
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(Space.SM)
            number = QLabel(f"{index + 1:02}")
            number.setObjectName("step_number")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setFixedSize(28, 28)
            content.addWidget(number)
            texts = QVBoxLayout()
            texts.setSpacing(2)
            title = QLabel()
            title.setObjectName("step_title")
            hint = QLabel()
            hint.setObjectName("eyebrow")
            texts.addWidget(title)
            texts.addWidget(hint)
            content.addLayout(texts, stretch=1)
            row.addWidget(item, stretch=1)
            self._items.append((item, title, hint))
        self._refresh()

    def set_stage(self, stage: int, *, complete: bool = False) -> None:
        """Reflect task state without navigating or changing processing options."""
        self._current = max(0, min(stage, len(_STEPS) - 1))
        self._complete = complete
        self._refresh()

    def set_compact(self, compact: bool) -> None:
        """Keep the current step visible in short desktop windows."""
        inset = Space.SM if compact else Space.MD
        self.layout().setContentsMargins(Space.LG, inset, Space.LG, inset)
        for _item, _title, hint in self._items:
            hint.setVisible(not compact)

    def _refresh(self) -> None:
        for index, (item, title, hint) in enumerate(self._items):
            done = index < self._current or self._complete
            state = "done" if done else "current" if index == self._current else "upcoming"
            if item.property("state") != state:
                item.setProperty("state", state)
                style = item.style()
                if style is not None:
                    for widget in (item, *item.findChildren(QLabel)):
                        style.unpolish(widget)
                        style.polish(widget)
            title.setText(self.tr(_STEPS[index]))
            hint.setText(self.tr("Complete" if done else "Current step"
                                 if state == "current" else "Next"))
            item.setAccessibleName(f"{index + 1}. {title.text()}: {hint.text()}")

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._refresh()
        super().changeEvent(event)
