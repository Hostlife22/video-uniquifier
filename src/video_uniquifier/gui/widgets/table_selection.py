"""An explicit, themed select-all checkbox in the native table corner."""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import (
    QEvent,
    QItemSelection,
    QItemSelectionModel,
    QObject,
    QPoint,
    Qt,
    pyqtSlot,
)
from PyQt6.QtGui import QPaintEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QTableWidget,
)

from video_uniquifier.gui.design import Metrics


class TableSelectionCheckBox(QCheckBox):
    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table)
        self.table = table
        self.setObjectName("table_selection")
        self.setTristate(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._retranslate()
        self.clicked.connect(self._toggle_selection)
        table.installEventFilter(self)
        for header in (table.horizontalHeader(), table.verticalHeader()):
            assert header is not None
            header.geometriesChanged.connect(self._position)
        self._position()
        model, selection = table.model(), table.selectionModel()
        assert model is not None and selection is not None
        selection.selectionChanged.connect(self.refresh)
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset,
                       model.layoutChanged, model.dataChanged):
            signal.connect(self.refresh)
        self.refresh()
        self._position()

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Select all visible rows"))
        description = self.tr("Select or clear all visible rows in this table.")
        self.setAccessibleDescription(description)
        self.setToolTip(description)

    def initStyleOption(self, option: QStyleOptionButton | None) -> None:
        super().initStyleOption(option)
        if option is not None:
            style = self.style()
            assert style is not None
            size = style.subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self).size()
            option.rect = QStyle.alignedRect(
                self.layoutDirection(), Qt.AlignmentFlag.AlignCenter, size, self.rect(),
            )

    def paintEvent(self, event: QPaintEvent | None) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_CheckBox, option)

    def hitButton(self, point: QPoint) -> bool:
        return self.rect().contains(point)

    def nextCheckState(self) -> None:
        self.setCheckState(Qt.CheckState.Unchecked if self.checkState() == Qt.CheckState.Checked
                           else Qt.CheckState.Checked)

    @pyqtSlot()
    def _position(self) -> None:
        if sip.isdeleted(self.table):
            return
        horizontal, vertical = self.table.horizontalHeader(), self.table.verticalHeader()
        assert horizontal is not None and vertical is not None
        self.setGeometry(vertical.x(), horizontal.y(), vertical.width(), horizontal.height())
        self.setVisible(not horizontal.isHidden() and not vertical.isHidden())
        self.raise_()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self.table and event is not None and event.type() in (
            QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest,
            QEvent.Type.LayoutDirectionChange,
        ):
            self._position()
        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def _selectable_cells(self) -> dict[int, list[int]]:
        model = self.table.model()
        assert model is not None
        required = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        rows = {}
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            columns = [column for column in range(self.table.columnCount())
                       if model.flags(model.index(row, column)) & required == required]
            if columns:
                rows[row] = columns
        return rows

    @pyqtSlot()
    def refresh(self) -> None:
        if sip.isdeleted(self.table) or getattr(self.table, "_updating", False):
            return
        rows = self._selectable_cells()
        allowed = self.table.selectionMode() not in (
            QAbstractItemView.SelectionMode.NoSelection,
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.setEnabled(bool(rows) and allowed)
        selected = {(index.row(), index.column()) for index in self.table.selectedIndexes()}
        cells = {(row, column) for row, columns in rows.items() for column in columns}
        state = (Qt.CheckState.Checked if cells and cells <= selected
                 else Qt.CheckState.PartiallyChecked if cells & selected
                 else Qt.CheckState.Unchecked)
        self.setCheckState(state)

    @pyqtSlot()
    def _toggle_selection(self) -> None:
        selection, model = self.table.selectionModel(), self.table.model()
        assert selection is not None and model is not None
        if self.checkState() == Qt.CheckState.Unchecked:
            selection.clearSelection()
        else:
            ranges = QItemSelection()
            for row in self._selectable_cells():
                ranges.select(model.index(row, 0), model.index(row, self.table.columnCount() - 1))
            selection.select(ranges, QItemSelectionModel.SelectionFlag.ClearAndSelect
                             | QItemSelectionModel.SelectionFlag.Rows)
        self.refresh()


def install_selection_checkbox(table: QTableWidget) -> TableSelectionCheckBox:
    existing = getattr(table, "_selection_checkbox", None)
    if isinstance(existing, TableSelectionCheckBox):
        return existing
    header = table.verticalHeader()
    assert header is not None
    header.setMinimumWidth(Metrics.CONTROL_HEIGHT)
    table.ensurePolished()
    # Use public header geometry, never a wrapper for Qt's private corner button.
    # Repeated native-child discovery/casting can invalidate SIP's wrapper cache.
    table.setCornerButtonEnabled(False)
    checkbox = TableSelectionCheckBox(table)
    # Qt owns the C++ child; retain its Python subclass on the table as well.
    table._selection_checkbox = checkbox  # type: ignore[attr-defined]
    return checkbox
