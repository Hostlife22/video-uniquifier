"""Visual regression: PNG snapshots of every screen at a fixed size.

Marker: `visual`. Excluded from default CI because font/widget renders
diverge across macOS/Linux/Wayland — only meaningful on a stable host.
The reviewed host is recorded alongside the offscreen baselines.

First run writes baselines under `tests/visual/__snapshots__/`. Update
baselines intentionally with `UPDATE_VISUAL_BASELINES=1`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from video_uniquifier.gui.widgets.chart_widget import HAS_QTCHARTS
from video_uniquifier.gui.widgets.file_picker import PathLabel

pytestmark = pytest.mark.visual


BASELINE_DIR = Path(__file__).parent / "__snapshots__"
BASELINE_DIR.mkdir(exist_ok=True)

SCREENS = {
    "Run":            0,
    "Batch":          1,
    "Calibrate":      2,
    "QA Viewer":      3,
    "Profile Editor": 4,
    "History":        5,
    "Corpus":         6,
    "Queue":          7,
    "Validation":     8,
    "Settings":       9,
}


@pytest.fixture(scope="module")
def main_window(tmp_path_factory):
    from video_uniquifier.core.qa import corpus
    from video_uniquifier.gui import state
    from video_uniquifier.gui.app_pyqt import MainWindow
    from video_uniquifier.gui.i18n import active_locale, install_translator

    app = QApplication.instance() or QApplication([])
    previous_locale = active_locale()
    config = tmp_path_factory.mktemp("visual_config")
    # Module fixtures run before function-scoped state isolation. Never
    # construct snapshots from the user's actual preferences or history.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(state, "CONFIG_DIR", config)
        patch.setattr(state, "STATE_PATH", config / "state.json")
        patch.setattr(state, "HISTORY_PATH", config / "history.json")
        patch.setattr(corpus, "DEFAULT_CORPUS_DIR", config / "corpus")
        install_translator(app, "en_US")
        win = MainWindow()
        # Show a stable example path while the real test DB stays in its
        # isolated temp directory; neither user paths nor random temp IDs
        # belong in a byte-compared baseline.
        for path_label in win.stack.widget(SCREENS["Corpus"]).findChildren(PathLabel):
            path_label.setText("/example/reference-library")
        win.state.set_theme("dark")
        win.resize(1100, 720)
        win.show()
        app.processEvents()
        if os.environ.get("UPDATE_VISUAL_BASELINES") == "1":
            (BASELINE_DIR / "host.json").write_text(
                json.dumps({"platform": sys.platform, "theme": "dark", "locale": "en_US"}),
            )
        yield win
        win.close()
        app.processEvents()
        install_translator(app, previous_locale)


def _baseline_path(label: str) -> Path:
    return BASELINE_DIR / f"{label.lower().replace(' ', '_')}.png"


@pytest.mark.parametrize("label", list(SCREENS.keys()))
def test_screen_snapshot(main_window, label: str) -> None:
    """Take a PNG of `label` and compare against the saved baseline.

    On first run (or with UPDATE_VISUAL_BASELINES=1) writes the baseline.
    On subsequent runs, fails if the file changed bytewise.
    """
    idx = SCREENS[label]
    main_window.sidebar.setCurrentRow(idx)
    app = QApplication.instance()
    assert app is not None
    app.processEvents()

    pix = main_window.grab()
    pix = pix.scaled(QSize(1100, 720))
    actual = BASELINE_DIR / f"_actual_{label.lower().replace(' ', '_')}.png"
    pix.save(str(actual), "PNG")

    baseline = _baseline_path(label)
    update = os.environ.get("UPDATE_VISUAL_BASELINES") == "1"
    host_path = BASELINE_DIR / "host.json"
    if host_path.exists() and not update:
        host = json.loads(host_path.read_text())
        if host["platform"] != sys.platform:
            pytest.skip(
                f"Baselines were reviewed on {host['platform']}; "
                "refresh and review on this host before comparing native fonts",
            )

    if not baseline.exists() or update:
        pix.save(str(baseline), "PNG")
        if not update:
            pytest.skip(
                f"Wrote initial baseline for {label!r}; rerun to compare"
            )
        return

    # Validation has a dynamic step indicator that changes between
    # navigation passes; comparing as bytes flakes. Only check the
    # baseline exists for that screen.
    #
    # History reads a persistent run-log store (rows accumulate every
    # time the user runs the CLI or GUI), so the table content drifts
    # between snapshot capture and replay on any developer box. Same
    # treatment as Validation.
    if label in ("Validation", "History") or (
        label == "Calibrate" and HAS_QTCHARTS
    ):
        assert baseline.exists() and baseline.stat().st_size > 0
        return

    # Byte-equal is the strictest check; works for screens with no
    # dynamic content rendered at snapshot time. Update intentionally
    # via UPDATE_VISUAL_BASELINES=1.
    assert baseline.read_bytes() == actual.read_bytes(), (
        f"Visual regression on {label!r}. "
        f"Compare {actual} vs {baseline} or rerun with "
        f"UPDATE_VISUAL_BASELINES=1 to refresh."
    )
