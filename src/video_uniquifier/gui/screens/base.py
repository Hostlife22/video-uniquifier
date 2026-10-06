"""ScreenBase + PlaceholderScreen — common screen contract."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.guides import GUIDES
from video_uniquifier.gui.state import AppState
from video_uniquifier.gui.widgets.page_guide import GuidePanel


class ScreenBase(QWidget):
    """Base class for all sidebar-registered screens.

    All real screens inherit and take an AppState in the constructor.
    Override `on_show()` if the screen needs to refresh state when the
    user navigates to it (called by MainWindow on tab switch).
    """

    navigate_requested = pyqtSignal(str)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self._page_strings: tuple[str, str] | None = None
        self.help_button: QPushButton | None = None
        self.guide_panel: GuidePanel | None = None

    def page_layout(self, title: str, description: str) -> QVBoxLayout:
        """Scrollable page chrome so dense screens cannot enlarge the whole window."""
        self._page_strings = (title, description)
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_scroll.setAccessibleName(self.tr(title))
        content = QWidget()
        self.page_scroll.setWidget(content)
        self.outer_layout.addWidget(self.page_scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(Space.PAGE, Space.PAGE, Space.PAGE, Space.PAGE)
        layout.setSpacing(Space.LG)
        self.page_title = QLabel(self.tr(title))
        self.page_title.setObjectName("title")
        self.page_title.setWordWrap(True)
        header = QHBoxLayout()
        header.setSpacing(Space.LG)
        header.addWidget(self.page_title, stretch=1)
        if title in GUIDES:
            self.help_button = QPushButton(self.tr("How to use"))
            self.help_button.setObjectName("page_help")
            self.help_button.setCheckable(True)
            self.help_button.setToolTip(self.tr("Show or hide this page's guide (F1)"))
            self.help_button.setAccessibleName(self.tr("How to use"))
            self.help_button.toggled.connect(self._set_guide_visible)
            header.addWidget(self.help_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        self.page_subtitle = QLabel(self.tr(description))
        self.page_subtitle.setObjectName("subtitle")
        self.page_subtitle.setWordWrap(True)
        layout.addWidget(self.page_subtitle)
        if title in GUIDES:
            self.guide_panel = GuidePanel(GUIDES[title])
            self.guide_panel.dismissed.connect(self._dismiss_guide)
            layout.addWidget(self.guide_panel)
            self._set_guide_visible(False)
        return layout

    def toggle_guide(self) -> None:
        """Used by the window's F1 shortcut, including when navigation has focus."""
        if self.help_button is not None:
            self.help_button.click()

    def _set_guide_visible(self, visible: bool) -> None:
        if self.guide_panel is not None:
            self.guide_panel.setVisible(visible)
            if visible:
                # Bring the guide header into view even when F1 was pressed
                # while the user was working farther down the page.
                scrollbar = self.page_scroll.verticalScrollBar()
                if scrollbar is not None:
                    scrollbar.setValue(0)
        if self.help_button is not None:
            self.help_button.setAccessibleDescription(self.tr(
                "Guide expanded. Click to hide." if visible
                else "Guide collapsed. Click to show.",
            ))

    def _dismiss_guide(self) -> None:
        if self.help_button is not None:
            self.help_button.setChecked(False)
            self.help_button.setFocus()

    def changeEvent(self, event: QEvent | None) -> None:
        if (event is not None and event.type() == QEvent.Type.LanguageChange
                and self._page_strings is not None):
            title, description = self._page_strings
            self.page_title.setText(self.tr(title))
            self.page_subtitle.setText(self.tr(description))
            if self.help_button is not None:
                self.help_button.setText(self.tr("How to use"))
                self.help_button.setAccessibleName(self.tr("How to use"))
                self.help_button.setToolTip(self.tr("Show or hide this page's guide (F1)"))
                self._set_guide_visible(self.help_button.isChecked())
        super().changeEvent(event)

    def add_action_bar(self, actions: QHBoxLayout) -> None:
        bar = QWidget()
        bar.setObjectName("action_bar")
        actions.setContentsMargins(Space.PAGE, Space.MD, Space.PAGE, Space.MD)
        actions.setSpacing(Space.SM)
        bar.setLayout(actions)
        self.outer_layout.addWidget(bar)

    def showEvent(self, event: QShowEvent | None) -> None:
        for combo in self.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
            )
            combo.setMinimumContentsLength(14)
        for table in self.findChildren(QTableWidget):
            if table.property("studioTable"):
                continue
            table.setProperty("studioTable", True)
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.setMinimumHeight(Metrics.TABLE_HEIGHT)
            header = table.verticalHeader()
            if header is not None:
                header.setDefaultSectionSize(Metrics.CONTROL_HEIGHT + Space.SM)
        super().showEvent(event)

    def on_show(self) -> None:  # pragma: no cover - default no-op
        """Hook for screens that need to refresh on navigation. Override."""

    def shutdown_workers(self, wait_ms: int = 16_000) -> bool:
        """Cooperatively stop every worker owned by this screen.

        Screens are also instantiated directly by tests and embedders, so
        cleanup cannot live only in ``MainWindow.closeEvent``.  In particular,
        EncoderSelector owns a nested detection QThread that is not present in
        the screen's attribute dictionary.
        """
        from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector

        all_stopped = True
        for selector in self.findChildren(EncoderSelector):
            all_stopped = selector.shutdown_detection(wait_ms) and all_stopped

        for obj in tuple(vars(self).values()):
            if not isinstance(obj, QThread) or not obj.isRunning():
                continue
            cancel = getattr(obj, "request_cancel", None)
            if callable(cancel):
                cancel()
            obj.quit()
            all_stopped = obj.wait(wait_ms) and all_stopped
        return all_stopped

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Never let Qt destroy a screen while one of its QThreads runs."""
        stopped = self.shutdown_workers()
        if event is not None:
            if stopped:
                event.accept()
            else:
                # Keep the widgets and their owning Python references alive.
                # A later close attempt can finish after the cooperative
                # cancellation reaches the worker.
                event.ignore()


class PlaceholderScreen(QWidget):
    """Stub shown for screens not yet implemented in this release."""

    def __init__(self, name: str, lands_in: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(f"<h2>{name}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        sub = QLabel(f"Coming in {lands_in}.")
        sub.setObjectName("status")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
