"""MainWindow with sidebar navigation + QStackedWidget content area.

v0.5.0 — replaces the single-window v0.4 shell. Adds 10 sidebar entries
(only Run functional in this release; others land in v0.5.1–v0.5.4).
"""

from __future__ import annotations

import contextlib
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import cast

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QFontDatabase, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier import __version__
from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.screens.base import ScreenBase
from video_uniquifier.gui.screens.batch import BatchScreen
from video_uniquifier.gui.screens.calibrate import CalibrateScreen
from video_uniquifier.gui.screens.corpus import CorpusScreen
from video_uniquifier.gui.screens.history import HistoryScreen
from video_uniquifier.gui.screens.profile_editor import ProfileEditorScreen
from video_uniquifier.gui.screens.qa_viewer import QaViewerScreen
from video_uniquifier.gui.screens.queue import QueueScreen
from video_uniquifier.gui.screens.run import RunScreen
from video_uniquifier.gui.screens.settings import SettingsScreen
from video_uniquifier.gui.screens.validation import ValidationScreen
from video_uniquifier.gui.state import CONFIG_DIR, AppState
from video_uniquifier.gui.theme import ThemeName, qss_for, tokens_for
from video_uniquifier.gui.widgets.activity_banner import ActivityBanner
from video_uniquifier.gui.widgets.navigation import NAV_LABELS, NavigationDelegate, outline_icon

_log = logging.getLogger(__name__)


def _install_global_excepthook() -> None:
    """Catch unhandled exceptions raised inside Qt slots / event handlers.

    Without this, an unhandled exception from a slot causes Qt to call
    ``qFatal`` and abort the process silently — the user sees the window
    vanish with no error to copy into a bug report. We:

    * append the full traceback to ``CONFIG_DIR/crash.log`` (rotation
      bounded to 100 KiB to prevent a runaway loop from filling the disk)
    * show a modal QMessageBox with severity + summary + collapsible
      "Show details" containing the full traceback (Copy works on it)
    * delegate to ``sys.__excepthook__`` so the stderr trail still
      reaches CI logs and ``--no-gui`` users.

    Pre-existing ``KeyboardInterrupt`` semantics are preserved (it is
    NOT shown in a dialog — it propagates through ``__excepthook__``
    so Ctrl+C still terminates).
    """
    prev_hook = sys.excepthook

    def _hook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        # Always delegate first so stderr + CI logs see the trace even
        # if our crash.log / QMessageBox path itself raises.
        with contextlib.suppress(Exception):
            prev_hook(exc_type, exc, tb)

        if issubclass(exc_type, KeyboardInterrupt):
            return  # let the default handler tear down cleanly

        text = "".join(traceback.format_exception(exc_type, exc, tb))

        # Append to crash.log. Best-effort; never re-raise inside the hook.
        with contextlib.suppress(OSError):
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            crash_path = CONFIG_DIR / "crash.log"
            # Rotate if the file already exceeds the cap — a tight
            # exception loop could otherwise fill the disk.
            if crash_path.exists() and crash_path.stat().st_size > 100 * 1024:
                crash_path.replace(crash_path.with_suffix(".log.1"))
            with crash_path.open("a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now().isoformat(timespec='seconds')} ---\n")
                f.write(text)
                f.write("\n")

        # Show a modal dialog. Only attempt if a QApplication is alive —
        # constructing a QMessageBox without one raises a different error.
        app = QApplication.instance()
        # Headless/offscreen test and server processes may retain a shared
        # QApplication from an earlier component. A modal exec() there has
        # no user who can close it and deadlocks the process until timeout.
        if app is None or QApplication.platformName() in {"offscreen", "minimal"}:
            return
        with contextlib.suppress(Exception):
            dlg = QMessageBox()
            dlg.setIcon(QMessageBox.Icon.Critical)
            dlg.setWindowTitle("video-uniquifier — unhandled error")
            dlg.setText(f"{exc_type.__name__}: {exc}")
            dlg.setInformativeText(
                f"A crash report was appended to:\n{CONFIG_DIR / 'crash.log'}\n\n"
                "Click 'Show Details…' to copy the full traceback for a bug report.",
            )
            dlg.setDetailedText(text)
            dlg.setStandardButtons(QMessageBox.StandardButton.Close)
            dlg.exec()

    sys.excepthook = _hook


def _crash_log_path() -> Path:
    """Public helper for tests + Settings 'Open crash log' future button."""
    return CONFIG_DIR / "crash.log"

# (Label, factory) — factory takes AppState and returns the screen widget.
# Placeholders are anonymous factories that ignore state.
SIDEBAR_ITEMS: list[tuple[str, str]] = [
    ("Run",            "v0.5.0"),     # functional
    ("Batch",          "v0.5.1"),
    ("Calibrate",      "v0.5.1"),
    ("QA Viewer",      "v0.5.2"),
    ("Profile Editor", "v0.5.2"),
    ("History",        "v0.5.2"),
    ("Corpus",         "v0.5.4"),
    ("Queue",          "v0.5.3"),
    ("Validation",     "v0.5.3"),
    ("Settings",       "v0.5.4"),
]


def _build_screen(label: str, lands_in: str, state: AppState) -> QWidget:
    """Instantiate the real screen if available, else PlaceholderScreen."""
    if label == "Run":
        return RunScreen(state)
    if label == "Batch":
        return BatchScreen(state)
    if label == "Calibrate":
        return CalibrateScreen(state)
    if label == "QA Viewer":
        return QaViewerScreen(state)
    if label == "Profile Editor":
        return ProfileEditorScreen(state)
    if label == "History":
        return HistoryScreen(state)
    if label == "Queue":
        return QueueScreen(state)
    if label == "Validation":
        return ValidationScreen(state)
    if label == "Corpus":
        return CorpusScreen(state)
    if label == "Settings":
        return SettingsScreen(state)
    from video_uniquifier.gui.screens.base import PlaceholderScreen
    return PlaceholderScreen(label, lands_in)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Uniquifier")
        self.resize(Metrics.WINDOW_WIDTH, Metrics.WINDOW_HEIGHT)
        self.setMinimumSize(Metrics.MIN_WINDOW_WIDTH, Metrics.MIN_WINDOW_HEIGHT)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))

        self.state = AppState()
        self.setStyleSheet(qss_for(cast(ThemeName, self.state.theme)))
        self.state.theme_changed.connect(self._on_theme_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand, grouped navigation and quiet footer share one sidebar surface.
        shell = QWidget()
        shell.setObjectName("sidebar_shell")
        shell.setFixedWidth(Metrics.SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(shell)
        sidebar_layout.setContentsMargins(0, Space.XL, 0, Space.LG)
        sidebar_layout.setSpacing(Space.LG)
        brand = QHBoxLayout()
        brand.setContentsMargins(Space.LG, 0, Space.LG, 0)
        self.brand_icon = QLabel()
        self._update_brand_icon()
        brand.addWidget(self.brand_icon)
        brand_name = QLabel("Video\nUniquifier")
        brand_name.setObjectName("brand")
        brand.addWidget(brand_name, stretch=1)
        sidebar_layout.addLayout(brand)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMouseTracking(True)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_delegate = NavigationDelegate(self.sidebar, self.state.theme)
        self.sidebar.setItemDelegate(self.nav_delegate)
        self.sidebar.setAccessibleName("Main navigation")
        self.sidebar.setAccessibleDescription(
            "Switch between Run, Batch, Calibrate, QA Viewer, "
            "Profile Editor, History, Corpus, Queue, Validation, "
            "and Settings. Use Ctrl+1 through Ctrl+0 (Ctrl+0 = Settings) "
            "to jump directly.",
        )
        for label, _lands_in in SIDEBAR_ITEMS:
            item = QListWidgetItem(self.tr(NAV_LABELS[label]), self.sidebar)
            item.setData(Qt.ItemDataRole.UserRole, label)
            item.setToolTip(self.tr(NAV_LABELS[label]))
        sidebar_layout.addWidget(self.sidebar, stretch=1)
        self.sidebar_note = QLabel(self.tr("Local processing") + f"  ·  v{__version__}")
        self.sidebar_note.setObjectName("eyebrow")
        self.sidebar_note.setContentsMargins(Space.XL, 0, Space.SM, 0)
        sidebar_layout.addWidget(self.sidebar_note)
        layout.addWidget(shell)

        # Stacked content
        self.stack = QStackedWidget()
        for label, lands_in in SIDEBAR_ITEMS:
            screen = _build_screen(label, lands_in, self.state)
            if isinstance(screen, ScreenBase):
                screen.navigate_requested.connect(self._navigate_to)
            self.stack.addWidget(screen)
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.activity_banner = ActivityBanner()
        self.activity_banner.requested.connect(self.sidebar.setCurrentRow)
        column.addWidget(self.activity_banner)
        column.addWidget(self.stack, stretch=1)
        layout.addWidget(content, stretch=1)
        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(250)
        self.activity_timer.timeout.connect(self._refresh_activity)
        self.activity_timer.start()

        self.sidebar.currentRowChanged.connect(self._on_nav)
        self.sidebar.setCurrentRow(0)

        # Ctrl+1..Ctrl+9 → first 9 screens; Ctrl+0 → 10th (Settings).
        # Using QShortcut (not button shortcuts) so the binding is
        # active globally regardless of which screen has focus.
        for idx in range(len(SIDEBAR_ITEMS)):
            digit = (idx + 1) % 10  # 0..8 → 1..9; 9 → 0
            sc = QShortcut(QKeySequence(f"Ctrl+{digit}"), self)
            sc.activated.connect(lambda i=idx: self.sidebar.setCurrentRow(i))

        self.help_shortcut = QShortcut(QKeySequence("F1"), self)
        self.help_shortcut.activated.connect(self._toggle_page_guide)

        self.setCentralWidget(root)
        bar = QStatusBar()
        self.setStatusBar(bar)
        bar.showMessage(self.tr("Ready"))

    def _toggle_page_guide(self) -> None:
        screen = self.stack.currentWidget()
        if isinstance(screen, ScreenBase):
            screen.toggle_guide()

    def _navigate_to(self, label: str) -> None:
        for index, (source, _version) in enumerate(SIDEBAR_ITEMS):
            if source == label:
                self.sidebar.setCurrentRow(index)
                return

    def _refresh_activity(self) -> None:
        tasks: list[tuple[int, str, str, float | None]] = []
        for index, (label, _version) in enumerate(SIDEBAR_ITEMS):
            screen = self.stack.widget(index)
            if isinstance(screen, RunScreen):
                if not any(worker is not None for worker in (
                    screen.run_worker, screen._sample_worker,
                    screen._save_worker, screen._tune_worker,
                )):
                    continue
                details = screen.status_label.text()
                if (screen._save_worker is None and screen._tune_worker is None
                        and screen.processing_status.phase is not None):
                    details += "  ·  " + screen.processing_status.time_label.text()
                fraction = (screen.progress_bar.value() / 1000
                            if screen.progress_bar.maximum() > 0
                            and screen._tune_worker is None else None)
                tasks.append((index, self.tr(NAV_LABELS[label]), details, fraction))
            elif isinstance(screen, (BatchScreen, CalibrateScreen, QueueScreen)):
                worker = screen.drain_worker if isinstance(screen, QueueScreen) else screen.worker
                if worker is None:
                    continue
                progress = screen.progress_bar
                maximum = progress.maximum()
                fraction = progress.value() / maximum if maximum > 0 else None
                title = self.tr(NAV_LABELS[label])
                tasks.append((index, title, title, fraction))
        self.activity_banner.set_tasks(tasks)

    def _update_brand_icon(self) -> None:
        icon = outline_icon("brand", tokens_for(self.state.theme)["accent"], 40)
        self.brand_icon.setPixmap(icon.pixmap(40, 40))

    def changeEvent(self, event: QEvent | None) -> None:
        if (event is not None and event.type() == QEvent.Type.LanguageChange
                and hasattr(self, "sidebar")):
            for index, (label, _version) in enumerate(SIDEBAR_ITEMS):
                item = self.sidebar.item(index)
                if item is not None:
                    item.setText(self.tr(NAV_LABELS[label]))
                    item.setToolTip(self.tr(NAV_LABELS[label]))
            self.sidebar_note.setText(self.tr("Local processing") + f"  ·  v{__version__}")
            viewport = self.sidebar.viewport()
            if viewport is not None:
                viewport.update()
        super().changeEvent(event)

    def _on_nav(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        widget = self.stack.currentWidget()
        if isinstance(widget, ScreenBase):
            widget.on_show()

    def _on_theme_changed(self, theme: str) -> None:
        self.setStyleSheet(qss_for(cast(ThemeName, theme)))
        self.nav_delegate.theme = theme
        viewport = self.sidebar.viewport()
        if viewport is not None:
            viewport.update()
        self._update_brand_icon()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Cancel and join every running worker before the window closes.

        Without this, QueueStatusWorker's infinite poll loop keeps the
        process alive after the window is gone, and an active encode
        can keep writing to its output file mid-corruption.
        """
        # Persist any in-memory AppState (recent files, etc.) — Settings
        # was the only call site before, so closing without visiting it
        # discarded changes.
        with contextlib.suppress(Exception):
            self.state.save()

        all_stopped = True
        for i in range(self.stack.count()):
            screen = self.stack.widget(i)
            if screen is None:
                continue
            if isinstance(screen, ScreenBase):
                all_stopped = screen.shutdown_workers() and all_stopped
        if event is not None:
            if all_stopped:
                self.activity_timer.stop()
                event.accept()
            else:
                _log.warning("close deferred: one or more GUI workers are still running")
                event.ignore()


def _maybe_prompt_telemetry_consent(parent: QMainWindow | None = None) -> None:
    """v0.9 R3 — first-run-only opt-in dialog for local telemetry.

    Runs at most once per user: the consent marker file (see
    :func:`core.telemetry.default_consent_marker`) flips the gate
    permanently. The default decision is *off*; the user must
    deliberately click Enable. A dismissed dialog (close button)
    records 'disabled' so we don't re-prompt forever.
    """
    from video_uniquifier.core.telemetry import (
        TelemetryConfig,
        has_consent_marker,
        write_consent_marker,
    )
    if has_consent_marker():
        return
    box = QMessageBox(parent)
    box.setWindowTitle("Local telemetry")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText("Help improve video-uniquifier with local-only telemetry?")
    box.setInformativeText(
        "When enabled, each completed or failed encode appends one "
        "anonymous summary event (profile name, encoder, wall-clock, "
        "segment count, OS) to a JSONL file in your per-user data "
        "directory.\n\n"
        "Telemetry is OFF by default. Nothing is sent over the "
        "network in this release — you can review or export events "
        "from Settings → Local telemetry, or via "
        "`video-uniq telemetry status`.\n\n"
        "Your choice is remembered; change it any time in Settings."
    )
    from PyQt6.QtWidgets import QPushButton
    enable_btn = box.addButton("&Enable", QMessageBox.ButtonRole.AcceptRole)
    keep_disabled_btn = box.addButton(
        "&Keep disabled", QMessageBox.ButtonRole.RejectRole,
    )
    if isinstance(keep_disabled_btn, QPushButton):
        box.setDefaultButton(keep_disabled_btn)
    box.exec()
    enabled = box.clickedButton() is enable_btn
    try:
        write_consent_marker(enabled)
    except OSError:
        return
    if enabled:
        try:
            from video_uniquifier.gui.state import AppState
            # Use a transient AppState only to persist — MainWindow
            # may already have one; setting via that one syncs the
            # signal subscribers. We avoid coupling here so this
            # function can run before MainWindow exists.
            state = AppState()
            state.set_telemetry(TelemetryConfig(enabled=True))
        except Exception:  # noqa: BLE001 — never block startup
            pass


def _resolve_boot_locale() -> str:
    """Persisted locale wins; env-derived hint is the first-launch fallback.

    Reads state.json ahead of widget construction so the translator
    is in place before any ``tr()`` call. A missing or unreadable
    state.json falls back to the system hint and ultimately to
    en_US — the i18n layer accepts an unknown locale by emitting
    source strings, so this never blocks startup.
    """
    import json

    from video_uniquifier.gui.i18n import (
        SOURCE_LOCALE,
        available_locales,
        system_locale_hint,
    )
    from video_uniquifier.gui.state import STATE_PATH
    locale: str | None = None
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            persisted = data.get("locale")
            if isinstance(persisted, str) and persisted:
                locale = persisted
    except (OSError, json.JSONDecodeError):
        locale = None
    if locale is None:
        locale = system_locale_hint()
    if locale is None or locale not in available_locales():
        locale = SOURCE_LOCALE
    return locale


def main() -> None:
    if sys.argv[1:] == ["--version"]:
        print(__version__)
        return

    app = QApplication(sys.argv)
    app.setApplicationName("video-uniq-gui")
    app.setApplicationVersion(__version__)
    _install_global_excepthook()
    # v0.9 R5 — install the translator BEFORE MainWindow constructs
    # any widget so the first paint already shows the right language.
    from video_uniquifier.gui.i18n import install_translator
    install_translator(app, _resolve_boot_locale())
    win = MainWindow()
    win.show()
    _maybe_prompt_telemetry_consent(win)
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
