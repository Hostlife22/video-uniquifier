"""ChartWidget — series management + QPainter fallback rendering."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from video_uniquifier.gui.widgets.chart_widget import ChartWidget, Series


@pytest.fixture(scope="module")
def app(qapp) -> QApplication:
    return qapp


def test_chart_widget_set_series(qtbot, app: QApplication) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)
    chart.set_series([
        Series(name="a", color="#ff0000", points=[(0.0, 1.0), (1.0, 2.0)]),
    ])
    assert len(chart._series) == 1
    assert chart._series[0].name == "a"


def test_chart_widget_add_point(qtbot, app: QApplication) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)
    chart.set_series([Series(name="a", color="#00ff00")])
    chart.add_point("a", 0.0, 5.0)
    chart.add_point("a", 1.0, 7.0)
    assert len(chart._series[0].points) == 2


def test_chart_widget_add_point_to_unknown_series_creates_it(qtbot, app: QApplication) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)
    chart.add_point("new", 0.0, 1.0)
    assert len(chart._series) == 1
    assert chart._series[0].name == "new"


def test_chart_widget_clear(qtbot, app: QApplication) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)
    chart.set_series([Series(name="a", color="#00ff00", points=[(0.0, 1.0)])])
    chart.clear()
    assert chart._series == []
