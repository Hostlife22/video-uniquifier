"""Accessible source filmstrip and unbounded-hours timecode input."""
from __future__ import annotations

import re

from PyQt6.QtCore import QEvent, QRect, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap, QValidator
from PyQt6.QtWidgets import QDoubleSpinBox, QSlider

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for


def timecode(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    whole, fraction = divmod(centiseconds, 100)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{fraction:02d}"


class TimecodeSpinBox(QDoubleSpinBox):
    def __init__(self) -> None:
        super().__init__()
        self._translate()

    def _translate(self) -> None:
        editor = self.lineEdit()
        if editor is not None:
            editor.setAccessibleName(self.tr("Start time"))
            editor.setAccessibleDescription("HH:MM:SS.cc")

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._translate()
        super().changeEvent(event)

    def textFromValue(self, value: float) -> str:
        return timecode(value)

    def valueFromText(self, text: str | None) -> float:
        match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d)(?:[.,](\d{1,2}))?", (text or "").strip())
        if match is None:
            return self.value()
        hours, minutes, seconds, fraction = match.groups()
        return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                + float("0." + (fraction or "0")))

    def validate(self, text: str | None, pos: int) -> tuple[QValidator.State, str, int]:
        text = text or ""
        if re.fullmatch(r"\d+:[0-5]\d:[0-5]\d(?:[.,]\d{1,2})?", text.strip()):
            value = self.valueFromText(text)
            state = (QValidator.State.Acceptable if self.minimum() <= value <= self.maximum()
                     else QValidator.State.Intermediate)
        elif re.fullmatch(r"[\d:.,]*", text):
            state = QValidator.State.Intermediate
        else:
            state = QValidator.State.Invalid
        return state, text, pos


class SampleTimeline(QSlider):
    def __init__(self, state: AppState) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.state = state
        self.frames: list[tuple[float, QPixmap]] = []
        self.length_sec = 15.0
        self.setRange(0, 0)
        self.setSingleStep(1000)
        self.setPageStep(10000)
        self.setFixedHeight(Metrics.FILMSTRIP_HEIGHT)
        self.setAccessibleName(self.tr("Sample timeline"))
        self.setToolTip(self.tr(
            "Click or drag to choose the sample start; arrow keys move by one second.",
        ))
        state.theme_changed.connect(lambda _theme: self.update())
        self.valueChanged.connect(lambda _value: self.update())

    def reset(self) -> None:
        self.frames.clear()
        self.setRange(0, 0)
        self.update()

    def add_frame(self, stamp: float, pixmap: QPixmap) -> None:
        self.frames.append((stamp, pixmap))
        self.frames.sort(key=lambda item: item[0])
        self.update()

    def _at(self, event: QMouseEvent) -> None:
        if self.maximum() <= 0:
            return
        fraction = (event.position().x() - Space.XS) / max(1, self.width() - 2 * Space.XS)
        self.setValue(round(min(max(fraction, 0), 1) * self.maximum()))

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._at(event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._at(event)
        else:
            super().mouseMoveEvent(event)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        tokens = tokens_for(self.state.theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        strip = QRect(Space.XS, Space.XS, self.width() - 2 * Space.XS,
                      self.height() - Metrics.FILMSTRIP_LABEL_HEIGHT)
        painter.fillRect(strip, QColor(tokens["bg_deep"]))
        if self.frames:
            width = strip.width() / len(self.frames)
            for index, (_stamp, image) in enumerate(self.frames):
                rect = QRect(round(strip.left() + index * width), strip.top(),
                             round(width), strip.height())
                fitted = image.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(rect.center().x() - fitted.width() // 2,
                                   rect.center().y() - fitted.height() // 2, fitted)
        else:
            painter.setPen(QColor(tokens["fg_dim"]))
            painter.drawText(strip, Qt.AlignmentFlag.AlignCenter, self.tr("Video thumbnails"))
        if self.maximum() > 0:
            start = strip.left() + strip.width() * self.value() / self.maximum()
            end = strip.left() + strip.width() * min(
                self.maximum(), self.value() + self.length_sec * 1000,
            ) / self.maximum()
            tint = QColor(tokens["accent"])
            tint.setAlpha(55)
            painter.fillRect(QRect(round(start), strip.top(), max(2, round(end - start)),
                                   strip.height()), tint)
            painter.setPen(QColor(tokens["accent"]))
            painter.drawRect(round(start), strip.top(), max(2, round(end - start)), strip.height())
            painter.drawLine(round(start), strip.top(), round(start), strip.bottom())
        painter.setPen(QColor(tokens["fg_dim"]))
        labels = QRect(strip.left(), strip.bottom() + Space.XS, strip.width(),
                       Metrics.FILMSTRIP_LABEL_HEIGHT - Space.XS)
        painter.drawText(labels, Qt.AlignmentFlag.AlignLeft, "00:00:00")
        painter.drawText(labels, Qt.AlignmentFlag.AlignRight,
                         timecode(self.maximum() / 1000).split(".")[0])
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens["accent_warm"]), 2))
            painter.drawRect(strip.adjusted(1, 1, -1, -1))
        painter.end()

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.setAccessibleName(self.tr("Sample timeline"))
        super().changeEvent(event)
