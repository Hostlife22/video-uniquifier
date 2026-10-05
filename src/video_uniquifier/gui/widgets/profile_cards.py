"""Plain-language shortcuts to existing shipped profiles."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QResizeEvent
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
        self._label_measurements: dict[QLabel, tuple[str, str, int, int]] = {}
        self._fitting_cards = False
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_card_text)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Space.SM)
        for key in PRESETS:
            button = QPushButton()
            button.setObjectName("profile_card")
            button.setCheckable(True)
            button.setMinimumHeight(Metrics.PROFILE_CARD_HEIGHT)
            button.installEventFilter(self)
            column = QVBoxLayout(button)
            column.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
            column.setSpacing(Space.SM)
            labels = []
            for index in range(3):
                label = QLabel()
                label.setWordWrap(True)
                label.setObjectName("section_title" if index == 0 else "hint")
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                label.installEventFilter(self)
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
        self._fit_card_text()

    def _fit_card_text(self) -> None:
        if self._fitting_cards:
            return
        self._fitting_cards = True
        try:
            # QPushButton ignores its child layout's height-for-width. Compute
            # each label's current wrapped height, rather than relying on a
            # layout cache populated before Windows finishes font/style polish.
            for key, button in self.buttons.items():
                layout = button.layout()
                if layout is None:
                    continue
                margins = layout.contentsMargins()
                width = max(1, button.contentsRect().width() - margins.left() - margins.right())
                height = margins.top() + margins.bottom()
                labels = self.labels[key]
                for label in labels:
                    signature = (label.text(), label.font().key(), width)
                    measured = self._label_measurements.get(label)
                    if measured is None or measured[:3] != signature:
                        # QLabel's heightForWidth includes its previous explicit
                        # minimum. Clear that only for a new measurement so a
                        # smaller font or wider card can shrink again, and layout
                        # requests from setting the minimum settle after one pass.
                        label.setMinimumHeight(0)
                        needed = max(0, label.heightForWidth(width))
                        self._label_measurements[label] = (*signature, needed)
                    else:
                        needed = measured[3]
                    if label.minimumHeight() != needed:
                        label.setMinimumHeight(needed)
                    height += needed
                height += layout.spacing() * (len(labels) - 1)
                needed = max(Metrics.PROFILE_CARD_HEIGHT, height)
                if button.minimumHeight() != needed:
                    button.setMinimumHeight(needed)
        finally:
            self._fitting_cards = False

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is not None and event.type() in (
            QEvent.Type.FontChange, QEvent.Type.StyleChange,
            QEvent.Type.LayoutRequest, QEvent.Type.Resize,
        ):
            # Coalesce changes and measure after Qt applies the new font and
            # lays out the children. Text changes need this even without resize.
            self._fit_timer.start()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self._fit_card_text()

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._translate()
        super().changeEvent(event)
