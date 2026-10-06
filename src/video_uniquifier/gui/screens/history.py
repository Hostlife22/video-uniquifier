"""History — past runs with re-open / re-run actions."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QWidget,
)

from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.design import Metrics
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.state import AppState, HistoryEntry
from video_uniquifier.gui.widgets.studio_table import StudioTable, TableTools


class HistoryScreen(ScreenBase):
    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._all_entries: list[HistoryEntry] = []
        self._build_ui()
        self.state.history_changed.connect(self._on_history_changed)
        self._on_history_changed(self.state.history)

    def _build_ui(self) -> None:
        layout = self.page_layout(
            'History',
            'Find completed jobs, open their videos and revisit quality reports.',
        )

        self.table = StudioTable(7, self.state, "history.header", 4)
        self.table.set_headers([
            "Date", "Source", "Profile", "Encoder",
            "Status", "Output", "Actions",
        ])
        self.table.sortItems(0, Qt.SortOrder.DescendingOrder)
        self.table.restore_header()
        self.table_tools = TableTools(self.table, filter_rows=False)
        self.filter_edit = self.table_tools.search
        self.filter_edit.textChanged.connect(self._refresh)
        self.table_tools.status.currentIndexChanged.connect(self._refresh)
        layout.addWidget(self.table_tools)
        layout.addWidget(self.table, stretch=1)
        self.clear_btn = QPushButton(self.tr("&Clear all"))
        self.clear_btn.clicked.connect(self._clear_history)
        mark(self.clear_btn, "Clear history", "Remove history records after confirmation.")
        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self.clear_btn)
        self.add_action_bar(controls)
        self.empty_label = QLabel(self.tr(
            "No matching jobs. Process a video or change the search to find previous results.",
        ))
        self.empty_label.setObjectName("hint")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

    def _on_history_changed(self, entries: list[HistoryEntry]) -> None:
        self._all_entries = list(entries)
        self._refresh()

    def _refresh(self) -> None:
        filter_text = self.filter_edit.text().casefold().strip()
        status = self.table_tools.status.currentData()
        with self.table.updating():
            self.table.setRowCount(0)
            for entry in self._all_entries:
                haystack = " ".join([
                    entry.source_path, entry.output_path, entry.profile_name,
                    entry.encoder_name, entry.status, entry.timestamp,
                    self.table.status_item(entry.status).text(),
                ]).casefold()
                if filter_text and filter_text not in haystack:
                    continue
                if status and entry.status != status:
                    continue
                self._append_row(entry)
        self.empty_label.setVisible(self.table.rowCount() == 0)

    def _append_row(self, entry: HistoryEntry) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        key = f"{entry.timestamp}|{entry.plan_hash}|{entry.output_path}"
        self.table.setItem(r, 0, self.table.file_item(entry.timestamp, key, entry.output_path))
        source = self.table.path_item(entry.source_path)
        source.setText(Path(entry.source_path).name)
        self.table.setItem(r, 1, source)
        self.table.setItem(r, 2, QTableWidgetItem(entry.profile_name))
        self.table.setItem(r, 3, QTableWidgetItem(entry.encoder_name))
        self.table.setItem(r, 4, self.table.status_item(entry.status))
        self.table.setItem(r, 5, self.table.path_item(entry.output_path))

        # Actions cell
        actions_widget = self._build_actions(entry)
        self.table.setCellWidget(r, 6, actions_widget)

    def _build_actions(self, entry: HistoryEntry) -> QWidget:
        w = self.table.row_actions(entry.output_path)
        h = w.layout()
        if isinstance(h, QHBoxLayout) and entry.qa_html_path:
            btn_qa = QPushButton("QA")
            btn_qa.setObjectName("table_action")
            btn_qa.setFixedSize(Metrics.CONTROL_HEIGHT, Metrics.CONTROL_HEIGHT)
            btn_qa.clicked.connect(lambda: self._open_path(entry.qa_html_path))
            mark(btn_qa, f"Open QA report for {Path(entry.source_path).name}",
                 f"Open the QA HTML report: {entry.qa_html_path}")
            h.insertWidget(2, btn_qa)
        return w

    def _open_path(self, path: str | None) -> None:
        if not path:
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "Missing", f"{p} no longer exists.")
            return
        webbrowser.open(p.as_uri())

    def _clear_history(self) -> None:
        if QMessageBox.question(
            self, "Clear history",
            "Remove all history entries? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.state.clear_history()

    def on_show(self) -> None:
        """Refresh whenever the user navigates here (catches background updates)."""
        self._on_history_changed(self.state.history)
