"""Grouped sidebar without changing stable screen indices or keyboard shortcuts."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from video_uniquifier.gui.design import Metrics, Space, Type
from video_uniquifier.gui.theme import tokens_for

# A single outline family: 24-unit grid, rounded strokes, no raster dependencies.
_PATHS = {
    "open": '<path d="M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14'
            'a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
    "folder": '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11'
              'a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    "Run": '<rect x="3" y="4" width="18" height="16" rx="3"/>'
           '<path d="m10 8 6 4-6 4Z"/>',
    "Batch": '<rect x="7" y="7" width="14" height="14" rx="3"/>'
             '<path d="M17 3H6a3 3 0 0 0-3 3v11"/>',
    "Calibrate": '<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/>',
    "QA Viewer": '<path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14'
                 'a2 2 0 0 0 2-2v-3M8 16l4-4 3 2 6-8"/>',
    "Profile Editor": '<path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6"/>',
    "History": '<path d="M3 5v5h5M3 10a9 9 0 1 1 2 8M12 7v5l3 2"/>',
    "Corpus": '<rect x="3" y="4" width="7" height="16" rx="2"/>'
              '<path d="m14 4 6-1 3 16-6 1Z M6 8h1m-1 8h1"/>',
    "Queue": '<path d="M9 6h12M9 12h12M9 18h12"/>'
             '<circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/>'
             '<circle cx="4" cy="18" r="1"/>',
    "Validation": '<path d="M9 3h6M10 3v6l-6 9a2 2 0 0 0 2 3h12'
                  'a2 2 0 0 0 2-3l-6-9V3M7 16h10"/>',
    "Settings": '<path d="M9 3h6l1 4 4 1v8l-4 1-1 4H9l-1-4-4-1V8l4-1Z"/>'
                '<circle cx="12" cy="12" r="3"/>',
    "brand": '<rect x="3" y="3" width="18" height="18" rx="5"/>'
             '<path d="m8 8 4 8 4-8"/>',
}

NAV_LABELS = {
    "Run": "Process video", "Batch": "Batch processing", "Calibrate": "Auto-tune",
    "QA Viewer": "Quality reports", "Profile Editor": "Profiles", "History": "History",
    "Corpus": "Reference library", "Queue": "Processing queue",
    "Validation": "Experiments", "Settings": "Settings",
}
NAV_GROUPS = {0: "WORKSPACE", 2: "TUNING & QUALITY", 5: "LIBRARY", 7: "TOOLS"}


def outline_icon(name: str, color: str, size: int = Metrics.ICON) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
        f'stroke-linejoin="round">{_PATHS[name]}</svg>'
    )
    # Keep a 2x vector rasterization for Retina; icon sizes remain logical pixels.
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


class NavigationDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget, theme: str) -> None:
        super().__init__(parent)
        self.theme = theme
        self._icons: dict[tuple[str, str], QIcon] = {}

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        height = Metrics.NAV_ROW_HEIGHT
        if index.row() in NAV_GROUPS:
            height += Metrics.NAV_SECTION_HEIGHT
        return QSize(0, height)

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex,
    ) -> None:
        if painter is None:
            return
        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtWidgets import QStyle

        tokens = tokens_for(self.theme)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        row = QRectF(option.rect)
        if index.row() in NAV_GROUPS:
            font = QFont(option.font)
            font.setPixelSize(Type.CAPTION)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            painter.setPen(QColor(tokens["fg_dim"]))
            label = QCoreApplication.translate("Navigation", NAV_GROUPS[index.row()])
            group = row.adjusted(Space.LG, Space.SM, -Space.SM, 0)
            group.setHeight(Metrics.NAV_SECTION_HEIGHT - Space.SM)
            painter.drawText(group, Qt.AlignmentFlag.AlignVCenter, label)
            row.setTop(row.top() + Metrics.NAV_SECTION_HEIGHT)
        row.adjust(Space.SM, Space.XS, -Space.SM, -Space.XS)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["selected_bg" if selected else "hover"]))
            painter.drawRoundedRect(row, Metrics.CONTROL_RADIUS, Metrics.CONTROL_RADIUS)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens["accent_warm"]), 2))
            painter.drawRoundedRect(row, Metrics.CONTROL_RADIUS, Metrics.CONTROL_RADIUS)
        source = str(index.data(Qt.ItemDataRole.UserRole))
        color = tokens["selected_fg" if selected else "fg_dim"]
        key = (source, color)
        if key not in self._icons:
            self._icons[key] = outline_icon(source, color)
        icon_rect = row.toRect()
        icon_rect.setLeft(icon_rect.left() + Space.MD)
        icon_rect.setTop(icon_rect.top() + (icon_rect.height() - Metrics.ICON) // 2)
        icon_rect.setSize(QSize(Metrics.ICON, Metrics.ICON))
        self._icons[key].paint(painter, icon_rect)
        text_rect = row.adjusted(Space.MD + Metrics.ICON + Space.MD, 0, -Space.SM, 0)
        font = QFont(option.font)
        font.setPixelSize(Type.BODY)
        font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, str(index.data()))
        painter.restore()
