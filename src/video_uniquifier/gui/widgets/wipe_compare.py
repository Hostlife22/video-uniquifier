"""Shared image canvas with an accessible draggable before/after divider."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.theme import ThemeName, tokens_for


class WipeCompare(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.images = [QImage(), QImage()]
        self.divider = 0.5
        self.zoom: float | None = None
        self.offset = QPointF()
        self._drag: str | None = None
        self._last = QPointF()
        self.theme: ThemeName = "dark"
        self.setMinimumHeight(Metrics.REVIEW_VIDEO_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._translate()

    def _translate(self) -> None:
        self.setAccessibleName(self.tr("Before / after divider"))
        self.setToolTip(self.tr(
            "Drag the divider; drag the image to pan when zoomed. Arrow keys move the divider.",
        ))

    def set_theme(self, theme: str) -> None:
        self.theme = "light" if theme == "light" else "dark"
        self.update()

    def set_images(self, original: QImage, processed: QImage) -> None:
        self.images = [original, processed]
        self.update()

    def set_zoom(self, zoom: float | None) -> None:
        self.zoom = zoom
        self.offset = QPointF()
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        tokens = tokens_for(self.theme)
        painter.fillRect(self.rect(), QColor(tokens["bg_deep"]))
        split = self.width() * self.divider
        for index, image in enumerate(self.images):
            if image.isNull():
                continue
            if self.zoom is None:
                scale = min(self.width() / image.width(), self.height() / image.height())
            else:
                scale = self.zoom / self.devicePixelRatioF()
            width, height = image.width() * scale, image.height() * scale
            target = QRectF((self.width() - width) / 2 + self.offset.x(),
                            (self.height() - height) / 2 + self.offset.y(), width, height)
            painter.save()
            painter.setClipRect(QRectF(0 if index == 0 else split, 0,
                                      split if index == 0 else self.width() - split, self.height()))
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom is None)
            painter.drawImage(target, image)
            painter.restore()
        painter.setPen(QPen(QColor(tokens["accent"]), 2))
        painter.drawLine(QPointF(split, 0), QPointF(split, self.height()))
        painter.setBrush(QColor(tokens["accent"]))
        radius = Metrics.WIPE_HANDLE_RADIUS
        painter.drawEllipse(QPointF(split, self.height() / 2), radius, radius)
        for index, source in enumerate(("Original", "Processed")):
            text = self.tr(source)
            bounds = painter.fontMetrics().boundingRect(text).adjusted(
                -Space.SM, -Space.XS, Space.SM, Space.XS,
            )
            bounds.moveTopLeft(self.rect().topLeft())
            bounds.translate(Space.MD if index == 0 else self.width() - bounds.width() - Space.MD,
                             Space.MD)
            painter.fillRect(bounds, QColor(tokens["bg_alt"]))
            painter.setPen(QColor(tokens["fg"]))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, text)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens["accent_warm"]), 2))
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._translate()
            self.update()
        super().changeEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._last = event.position()
            self._drag = ("divider" if abs(event.position().x() - self.width() * self.divider)
                          <= Metrics.WIPE_HANDLE_TARGET else "pan")
            self.mouseMoveEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None or self._drag is None:
            super().mouseMoveEvent(event)
            return
        if self._drag == "divider":
            self.divider = min(max(event.position().x() / max(1, self.width()), 0), 1)
        elif self.zoom is not None:
            self.offset += event.position() - self._last
        self._last = event.position()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._drag = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                                                 Qt.Key.Key_Home, Qt.Key.Key_End):
            if event.key() == Qt.Key.Key_Home:
                self.divider = 0
            elif event.key() == Qt.Key.Key_End:
                self.divider = 1
            else:
                self.divider = min(max(self.divider + (0.02 if event.key() == Qt.Key.Key_Right
                                                       else -0.02), 0), 1)
            self.update()
        else:
            super().keyPressEvent(event)
