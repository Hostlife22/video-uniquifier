"""Headless smoke: MainWindow opens + every sidebar entry renders without error."""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_main_window_launches_and_navigates(gui_window_factory, qapp) -> None:
    """Open MainWindow, traverse all 10 sidebar entries, no exceptions."""
    from video_uniquifier.gui.app_pyqt import SIDEBAR_ITEMS

    app = qapp
    win = gui_window_factory()
    win.show()
    app.processEvents()

    assert win.sidebar.count() == len(SIDEBAR_ITEMS)

    for i in range(win.sidebar.count()):
        win.sidebar.setCurrentRow(i)
        app.processEvents()
        # Screen identities stay stable even when the sidebar is regrouped.
        from video_uniquifier.gui.widgets.navigation import NAV_ORDER
        assert SIDEBAR_ITEMS[win.stack.currentIndex()][0] == NAV_ORDER[i]
