"""Shared sortable tables, status pills, visible selection and row actions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PyQt6.QtCore import QEvent, QItemSelectionModel, QModelIndex, QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for
from video_uniquifier.gui.widgets.navigation import outline_icon
from video_uniquifier.gui.widgets.table_selection import install_selection_checkbox

KEY_ROLE = Qt.ItemDataRole.UserRole
PATH_ROLE = int(KEY_ROLE) + 1
STATUS_ROLE = int(KEY_ROLE) + 2
STATUS_LABELS = {
    "pending": "Pending", "running": "Running", "in_progress": "Running",
    "done": "Completed", "failed": "Failed", "cancelled": "Cancelled",
}


class StatusDelegate(QStyledItemDelegate):
    def __init__(self, table: StudioTable) -> None:
        super().__init__(table)
        self.table = table

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex,
    ) -> None:
        if painter is None:
            return
        status = index.data(STATUS_ROLE)
        if status not in STATUS_LABELS:
            super().paint(painter, option, index)
            return
        # Keep the native selection/focus background, then draw the status pill.
        background = QStyleOptionViewItem(option)
        self.initStyleOption(background, index)
        background.text = ""
        widget = option.widget
        if widget is not None:
            from PyQt6.QtWidgets import QStyle
            style = widget.style()
            if style is not None:
                style.drawControl(QStyle.ControlElement.CE_ItemViewItem, background, painter)
        tokens = tokens_for(self.table.app_state.theme)
        kind = "ok" if status == "done" else "fail" if status == "failed" else "warn"
        neutral = status in {"pending", "cancelled"}
        text = self.table.tr(STATUS_LABELS[status])
        rect = QRectF(option.rect).adjusted(Space.SM, Space.SM, -Space.SM, -Space.SM)
        rect.setWidth(min(rect.width(), option.fontMetrics.horizontalAdvance(text) + Space.XL))
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["bg_alt" if neutral else f"badge_{kind}_bg"]))
        painter.drawRoundedRect(rect, Space.XS, Space.XS)
        painter.setPen(QColor(tokens["fg_dim" if neutral else f"badge_{kind}_fg"]))
        text = option.fontMetrics.elidedText(
            text, Qt.TextElideMode.ElideRight, max(0, int(rect.width()) - Space.SM),
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class StudioTable(QTableWidget):
    refreshed = pyqtSignal()
    open_requested = pyqtSignal(str)

    def __init__(self, columns: int, state: AppState, key: str, status_column: int) -> None:
        super().__init__(0, columns)
        self.app_state, self.key, self.status_column = state, key, status_column
        self._updating = False
        self._header_ready = False
        self._header_sources: tuple[str, ...] = ()
        self.setProperty("studioTable", True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setMinimumHeight(Metrics.TABLE_HEIGHT)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setItemDelegateForColumn(status_column, StatusDelegate(self))
        vertical = self.verticalHeader()
        header = self.horizontalHeader()
        viewport = self.viewport()
        assert vertical is not None and header is not None and viewport is not None
        self.header, self.viewport_widget = header, viewport
        vertical.setDefaultSectionSize(Metrics.NAV_ROW_HEIGHT)
        self.header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header.setDefaultSectionSize(Metrics.TABLE_COLUMN_WIDTH)
        self.header.resizeSection(columns - 1, Metrics.TABLE_ACTION_WIDTH)
        self.header.setSectionsMovable(True)
        self.header.setStretchLastSection(True)
        self.header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.setSortingEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.open_requested.connect(self._open_file)
        self.app_state.theme_changed.connect(self._refresh_theme)
        self.header.sectionResized.connect(self._remember_header)
        self.header.sectionMoved.connect(self._remember_header)
        self.header.sortIndicatorChanged.connect(self._remember_header)
        self.selection_checkbox = install_selection_checkbox(self)
        self.refreshed.connect(self.selection_checkbox.refresh)

    def set_headers(self, sources: list[str]) -> None:
        self._header_sources = tuple(sources)
        self.setHorizontalHeaderLabels([self.tr(source) for source in sources])

    def restore_header(self) -> None:
        from PyQt6.QtCore import QByteArray
        raw = self.app_state.layout_state(self.key)
        if raw:
            self.header.restoreState(QByteArray.fromBase64(
                raw.encode("ascii", errors="ignore"),
            ))
        self._header_ready = True

    def _remember_header(self, *_args: object) -> None:
        if not self._header_ready:
            return
        self.app_state.set_layout_state(
            self.key, self.header.saveState().toBase64().data().decode("ascii"),
        )

    @contextmanager
    def updating(self) -> Iterator[None]:
        selected = self.selected_keys()
        sorting = self.isSortingEnabled()
        self._updating = True
        self.setSortingEnabled(False)
        try:
            yield
        finally:
            self.setSortingEnabled(sorting)
            self.clearSelection()
            selection = self.selectionModel()
            model = self.model()
            if selection is not None and model is not None:
                for row in range(self.rowCount()):
                    if self.row_key(row) in selected and not self.isRowHidden(row):
                        selection.select(
                            model.index(row, 0),
                            QItemSelectionModel.SelectionFlag.Select
                            | QItemSelectionModel.SelectionFlag.Rows,
                        )
            self._updating = False
            self.refreshed.emit()

    def row_key(self, row: int) -> str:
        item = self.item(row, 0)
        return str(item.data(KEY_ROLE) or "") if item is not None else ""

    def row_path(self, row: int) -> str:
        item = self.item(row, 0)
        return str(item.data(PATH_ROLE) or "") if item is not None else ""

    def selected_rows(self) -> list[int]:
        model = self.selectionModel()
        return sorted(index.row() for index in model.selectedRows()
                      if not self.isRowHidden(index.row())) if model is not None else []

    def selected_keys(self) -> list[str]:
        return [self.row_key(row) for row in self.selected_rows()]

    def find_key(self, key: str) -> int | None:
        return next((row for row in range(self.rowCount()) if self.row_key(row) == key), None)

    def file_item(self, text: str, key: str, path: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setData(KEY_ROLE, key)
        item.setData(PATH_ROLE, path)
        item.setToolTip(path)
        return item

    def status_item(self, status: str) -> QTableWidgetItem:
        item = QTableWidgetItem(self.tr(STATUS_LABELS.get(status, status)))
        item.setData(STATUS_ROLE, status)
        item.setToolTip(item.text())
        return item

    def path_item(self, path: str) -> QTableWidgetItem:
        item = QTableWidgetItem(path)
        item.setToolTip(path)
        return item

    def row_actions(self, path: str) -> QWidget:
        widget = QWidget()
        widget.setObjectName("table_actions")
        widget.setProperty("actionPath", path)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(Space.XS, 0, Space.XS, 0)
        layout.setSpacing(Space.XS)
        for icon, title, action in (
            ("open", "Open file", lambda: self.open_requested.emit(path)),
            ("folder", "Open containing folder", lambda: self._open_folder(path)),
        ):
            button = QPushButton()
            button.setObjectName("table_action")
            button.setProperty("studioIcon", icon)
            button.setProperty("studioTitle", title)
            button.setProperty("studioPath", path)
            button.setFixedSize(Metrics.CONTROL_HEIGHT, Metrics.CONTROL_HEIGHT)
            button.setAccessibleName(self.tr(title))
            button.setToolTip(self.tr(title) + "\n" + path)
            button.setIcon(outline_icon(icon, tokens_for(self.app_state.theme)["fg_dim"]))
            button.setEnabled(bool(path))
            button.clicked.connect(action)
            layout.addWidget(button)
        layout.addStretch(1)
        return widget

    def _refresh_theme(self, _theme: str = "") -> None:
        self.viewport_widget.update()
        for button in self.findChildren(QPushButton):
            icon = button.property("studioIcon")
            if isinstance(icon, str):
                button.setIcon(outline_icon(icon, tokens_for(self.app_state.theme)["fg_dim"]))

    def copy_selected_paths(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText("\n".join(self.row_path(row) for row in self.selected_rows()))

    def select_visible(self) -> None:
        self.selectAll()
        selection, model = self.selectionModel(), self.model()
        assert selection is not None and model is not None
        for row in range(self.rowCount()):
            if self.isRowHidden(row):
                selection.select(model.index(row, 0), QItemSelectionModel.SelectionFlag.Deselect
                                 | QItemSelectionModel.SelectionFlag.Rows)

    def action_path(self, row: int) -> str:
        actions = self.cellWidget(row, self.columnCount() - 1)
        path = actions.property("actionPath") if actions is not None else None
        return path if isinstance(path, str) and path else self.row_path(row)

    def _context_menu(self, point: QPoint) -> None:
        row = self.rowAt(point.y())
        if row < 0:
            return
        if row not in self.selected_rows():
            self.selectRow(row)
        path = self.action_path(row)
        menu = QMenu(self)
        menu.addAction(self.tr("Open file"), lambda: self.open_requested.emit(path))
        menu.addAction(self.tr("Open containing folder"), lambda: self._open_folder(path))
        menu.addSeparator()
        menu.addAction(self.tr("Copy selected paths"), self.copy_selected_paths)
        menu.addAction(self.tr("Select visible rows"), self.select_visible)
        menu.exec(self.viewport_widget.mapToGlobal(point))

    def _open_file(self, path: str) -> None:
        from PyQt6.QtCore import QUrl
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
        elif path:
            QMessageBox.warning(self, self.tr("File unavailable"), path)

    def _open_folder(self, path: str) -> None:
        from PyQt6.QtCore import QUrl
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve().parent)))

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.setHorizontalHeaderLabels([self.tr(source) for source in self._header_sources])
            for button in self.findChildren(QPushButton):
                title = button.property("studioTitle")
                if isinstance(title, str):
                    button.setAccessibleName(self.tr(title))
                    button.setToolTip(self.tr(title) + "\n" + str(button.property("studioPath")))
            with self.updating():
                for row in range(self.rowCount()):
                    item = self.item(row, self.status_column)
                    if item is not None:
                        status = item.data(STATUS_ROLE)
                        if status in STATUS_LABELS:
                            item.setText(self.tr(STATUS_LABELS[status]))
        super().changeEvent(event)


class TableTools(QWidget):
    def __init__(self, table: StudioTable, *, filter_rows: bool = True) -> None:
        super().__init__()
        self.table = table
        self.filter_rows = filter_rows
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(self.tr("Search files"))
        self.search.setPlaceholderText(self.tr("Search file, path or notes…"))
        row.addWidget(self.search, stretch=1)
        self.status = QComboBox()
        self.status.setAccessibleName(self.tr("Filter by status"))
        self.status.addItem(self.tr("All statuses"), "")
        for value in ("pending", "running", "in_progress", "done", "failed", "cancelled"):
            if value != "in_progress":
                self.status.addItem(self.tr(STATUS_LABELS[value]), value)
        row.addWidget(self.status)
        layout.addLayout(row)
        actions = QHBoxLayout()
        self.select = QPushButton(self.tr("Select visible rows"))
        self.select.setAccessibleName(self.tr("Select visible rows"))
        self.select.clicked.connect(table.select_visible)
        self.select.setProperty("variant", "quiet")
        actions.addWidget(self.select)
        self.copy = QPushButton(self.tr("Copy paths"))
        self.copy.clicked.connect(table.copy_selected_paths)
        self.copy.setProperty("variant", "quiet")
        self.copy.setAccessibleName(self.tr("Copy selected paths"))
        actions.addWidget(self.copy)
        self.count = QLabel()
        self.count.setObjectName("hint")
        self.count.setWordWrap(True)
        actions.addWidget(self.count, stretch=1)
        layout.addLayout(actions)
        self.search.textChanged.connect(self.apply_filters)
        self.status.currentIndexChanged.connect(self.apply_filters)
        table.refreshed.connect(self.apply_filters)
        table.itemSelectionChanged.connect(self._count)
        self.apply_filters()

    def apply_filters(self, *_args: object) -> None:
        if self.table._updating:
            return
        text = self.search.text().strip().casefold()
        status = self.status.currentData()
        if self.filter_rows:
            for row in range(self.table.rowCount()):
                values = [self.table.row_path(row)]
                for column in range(self.table.columnCount()):
                    item = self.table.item(row, column)
                    if item is not None:
                        values.append(item.text())
                item = self.table.item(row, self.table.status_column)
                raw = item.data(STATUS_ROLE) if item is not None else ""
                normalized = "running" if raw == "in_progress" else raw
                hidden = bool((text and text not in " ".join(values).casefold())
                              or (status and normalized != status))
                self.table.setRowHidden(row, hidden)
                if hidden:
                    selection, model = self.table.selectionModel(), self.table.model()
                    assert selection is not None and model is not None
                    selection.select(model.index(row, 0), QItemSelectionModel.SelectionFlag.Deselect
                                     | QItemSelectionModel.SelectionFlag.Rows)
        self._count()
        self.table.selection_checkbox.refresh()

    def _count(self) -> None:
        selected = len(self.table.selected_rows())
        visible = sum(not self.table.isRowHidden(row) for row in range(self.table.rowCount()))
        self.count.setText(self.tr("{visible} shown · {selected} selected").format(
            visible=visible, selected=selected,
        ))
        self.copy.setEnabled(selected > 0)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.search.setPlaceholderText(self.tr("Search file, path or notes…"))
            self.search.setAccessibleName(self.tr("Search files"))
            self.status.setAccessibleName(self.tr("Filter by status"))
            self.copy.setAccessibleName(self.tr("Copy selected paths"))
            self.select.setText(self.tr("Select visible rows"))
            self.select.setAccessibleName(self.tr("Select visible rows"))
            self.copy.setText(self.tr("Copy paths"))
            self.status.setItemText(0, self.tr("All statuses"))
            for index in range(1, self.status.count()):
                self.status.setItemText(index, self.tr(STATUS_LABELS[self.status.itemData(index)]))
            self._count()
        super().changeEvent(event)
