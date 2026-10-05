"""Plain-language shortcuts to existing shipped profiles."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from video_uniquifier.gui.design import Metrics, Space

PRESETS = {
    "soft": ("Gentle", "Small crop, subtle color correction and light noise.",
             "Audio: pitch adjustment and loudness normalization."),
    "medium": ("Balanced", "More visible crop, color correction and noise.",
               "Audio: pitch, equalizer and loudness normalization."),
    "aggressive": ("Pronounced", "Stronger changes plus a slight rotation. Review picture quality.",
                   "Audio: pitch, equalizer and loudness normalization."),
}


class ProfileCards(QWidget):
    selected = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.buttons: dict[str, QPushButton] = {}
        self.labels: dict[str, list[QLabel]] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Space.SM)
        for key in PRESETS:
            button = QPushButton()
            button.setObjectName("profile_card")
            button.setCheckable(True)
            button.setMinimumHeight(Metrics.PROFILE_CARD_HEIGHT)
            column = QVBoxLayout(button)
            column.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
            column.setSpacing(Space.SM)
            labels = []
            for index in range(3):
                label = QLabel()
                label.setWordWrap(True)
                label.setObjectName("section_title" if index == 0 else "hint")
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                column.addWidget(label)
                labels.append(label)
            column.addStretch(1)
            button.clicked.connect(lambda _checked, preset=key: self.selected.emit(preset))
            row.addWidget(button, stretch=1)
            self.buttons[key] = button
            self.labels[key] = labels
        self._translate()

    def set_selected(self, key: str) -> None:
        for preset, button in self.buttons.items():
            button.setChecked(preset == key)

    def _translate(self) -> None:
        for key, sources in PRESETS.items():
            for label, source in zip(self.labels[key], sources, strict=True):
                label.setText(self.tr(source))
            self.buttons[key].setAccessibleName(self.tr(sources[0]))
            self.buttons[key].setAccessibleDescription(
                self.tr(sources[1]) + " " + self.tr(sources[2]),
            )

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._translate()
        super().changeEvent(event)
