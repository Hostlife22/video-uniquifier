"""FilePickerRow — single-line widget for picking input/output paths."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.design import Space
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.theme import tokens_for
from video_uniquifier.gui.widgets.navigation import outline_icon


class PathLabel(QLabel):
    """Elide long paths while keeping the full value available to assistive tools."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def setText(self, text: str | None) -> None:
        self.set_full_text(text or "")

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self._update_text()

    def _update_text(self) -> None:
        super().setText(self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideMiddle, max(0, self.width()),
        ))

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._update_text()


class FilePickerRow(QWidget):
    """Label + path display + Browse button + drag-drop target.

    Emits `path_changed(Path)` whenever the user picks or drops a file.
    """

    path_changed = pyqtSignal(object)        # Path | None

    def __init__(
        self,
        label: str,
        kind: Literal["input", "output"] = "input",
        file_filter: str = "Video files (*.mp4 *.mov *.mkv *.webm);;All files (*)",
        state: AppState | None = None,
    ) -> None:
        super().__init__()
        self.kind = kind
        self.file_filter = file_filter
        self.state = state
        self._path: Path | None = None
        self._label_source = label.rstrip(":")
        self.setAcceptDrops(True)
        self._build_ui(label)

    def _build_ui(self, label: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.SM)
        self.field_label = QLabel(self.tr(self._label_source))
        self.field_label.setObjectName("field_label")
        layout.addWidget(self.field_label)
        self.surface = QWidget()
        self.surface.setObjectName("field_surface")
        row = QHBoxLayout(self.surface)
        row.setContentsMargins(Space.MD, Space.SM, Space.SM, Space.SM)
        row.setSpacing(Space.MD)
        self.file_icon = QLabel()
        self._update_icon()
        row.addWidget(self.file_icon)
        labels = QVBoxLayout()
        labels.setSpacing(Space.XS)
        self.path_label = PathLabel()
        self.path_label.setObjectName("path")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        labels.addWidget(self.path_label)
        self.directory_label = PathLabel()
        self.directory_label.setObjectName("hint")
        labels.addWidget(self.directory_label)
        row.addLayout(labels, stretch=1)
        self.browse_btn = QPushButton(self.tr("Choose…" if self.kind == "input" else "Save as…"))
        self.browse_btn.clicked.connect(self._on_browse)
        self.field_label.setBuddy(self.browse_btn)
        # Strip the trailing colon and trim so the accessible name is
        # spoken as "Browse input file" rather than "Browse Input:".
        clean_label = label.rstrip(":").strip() or self.kind
        mark(
            self.browse_btn,
            f"Browse {self.kind} file",
            f"Pick a {clean_label.lower()} via the file dialog.",
        )
        row.addWidget(self.browse_btn)
        layout.addWidget(self.surface)
        self._update_labels()
        if self.state is not None:
            self.state.theme_changed.connect(lambda _theme: self._update_icon())

    def _update_icon(self) -> None:
        theme = self.state.theme if self.state is not None else "dark"
        icon = outline_icon(
            "Run" if self.kind == "input" else "History", tokens_for(theme)["fg_dim"],
        )
        self.file_icon.setPixmap(icon.pixmap(20, 20))

    def _update_labels(self) -> None:
        if self._path is not None:
            self.path_label.set_full_text(self._path.name)
            self.directory_label.set_full_text(str(self._path.parent))
            self.surface.setToolTip(str(self._path))
        else:
            self.path_label.set_full_text(self.tr("No video selected" if self.kind == "input"
                                                  else "Choose an output file"))
            self.directory_label.set_full_text(self.tr("Drop a video here" if self.kind == "input"
                                                       else "Processed video · MP4"))

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.field_label.setText(self.tr(self._label_source))
            self.browse_btn.setText(self.tr("Choose…" if self.kind == "input" else "Save as…"))
            self._update_labels()
        super().changeEvent(event)

    def set_path(self, path: Path | None) -> None:
        """Programmatic path setter (does not re-emit if unchanged)."""
        if path == self._path:
            return
        self._path = path
        self._update_labels()
        self.path_changed.emit(path)

    def current_path(self) -> Path | None:
        return self._path

    def _on_browse(self) -> None:
        if self.kind == "output":
            path_str, _ = QFileDialog.getSaveFileName(
                self, self.tr("Output file"), str(self._path or ""), self.file_filter,
            )
        else:
            path_str, _ = QFileDialog.getOpenFileName(
                self, self.tr("Input file"), str(self._path or ""), self.file_filter,
            )
        if not path_str:
            return
        self.set_path(Path(path_str))

    # ---- drag-drop ----
    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        md = event.mimeData()
        if self.isEnabled() and md is not None and any(
            url.isLocalFile() and Path(url.toLocalFile()).is_file() for url in md.urls()
        ):
            self._set_drag_active(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent | None) -> None:
        self._set_drag_active(False)
        if event is not None:
            event.accept()

    def _set_drag_active(self, active: bool) -> None:
        self.surface.setProperty("dragActive", active)
        style = self.surface.style()
        if style is not None:
            style.unpolish(self.surface)
            style.polish(self.surface)

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is None:
            return
        self._set_drag_active(False)
        if not self.isEnabled():
            return
        md = event.mimeData()
        if md is None:
            return
        urls = md.urls()
        if not urls:
            return
        for url in urls:
            local = url.toLocalFile()
            if url.isLocalFile() and Path(local).is_file():
                self.set_path(Path(local))
                event.acceptProposedAction()
                break
