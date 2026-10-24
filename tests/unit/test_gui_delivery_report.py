"""Report presentation uses measured values and never invents missing metrics."""

from copy import deepcopy

import pytest
from PyQt6.QtCore import Qt

from video_uniquifier.gui.i18n import active_locale, install_translator
from video_uniquifier.gui.widgets.delivery_report import DeliveryReportDialog


@pytest.fixture
def report():
    source = {
        "filename": "Episode 1.mp4", "duration_sec": 110.875, "size_bytes": 41112544,
        "video": [{"width": 1080, "height": 1920, "fps": 24, "codec": "h264",
                   "bit_rate": 2800079}],
        "audio": [{"sample_rate": 44100, "channels": 2, "bit_rate": 160008}],
    }
    output = deepcopy(source)
    output["size_bytes"] = 46451465
    output["video"][0]["bit_rate"] = 3215034
    output["audio"][0].update(sample_rate=48000, bit_rate=131198)
    return {
        "source": source, "output": output,
        "audio_normalization": {"measurement": {"input_i": -10.25}},
        "effective_rules": {"scenes": {"trim_start_sec": 0, "trim_end_sec": 0},
                            "packaging": {"enabled": False}},
        "quality_check": {
            "status": "passed", "decode": "passed", "faststart": True,
            "duration_delta_sec": 0, "timing": {"start_drift_ms": 0, "end_drift_ms": 0},
            "loudness": {"streams": [{"integrated_lufs": -16.06, "true_peak_dbtp": -5.23}]},
            "listening_review": "manual_required", "subtitle_review": "manual_required",
            "visual_similarity": {"status": "not_computed"}, "failures": [],
        }, "warnings": [],
    }


@pytest.fixture
def dialog(report, qtbot, qapp):
    locale = active_locale()
    install_translator(qapp, "en_US")
    widget = DeliveryReportDialog(report)
    qtbot.addWidget(widget)
    yield widget
    install_translator(qapp, locale)


def test_measured_comparison_and_checks_match_the_export(dialog, report):
    expected = [
        ("1080 × 1920", "1080 × 1920"), ("24.00 fps", "24.00 fps"),
        ("110.875 s", "110.875 s"), ("H264", "H264"),
        ("2.80 Mbps", "3.22 Mbps"), ("41.1 MB", "46.5 MB"),
        ("-10.25 LUFS", "-16.06 LUFS"), ("44.1 kHz", "48.0 kHz"),
        ("160 kbps", "131 kbps"), ("2", "2"),
    ]
    for row, pair in enumerate(expected):
        assert tuple(dialog.comparison.item(row, column).text() for column in (1, 2)) == pair
    assert dialog.checks.item(5, 1).text() == "-5.23 dBTP"
    assert dialog.checks.item(6, 1).text() == "Manual review needed"
    assert dialog.checks.item(8, 1).text() == "Not measured"
    assert "Title: Disabled" in dialog.changes.text()
    report["source"]["duration_sec"] = 7
    dialog._render()
    assert dialog.comparison.item(2, 1).text() == "110.875 s"


def test_live_chinese_translation_and_small_window(dialog, qapp, qtbot):
    dialog.resize(600, 440)
    dialog.show()
    install_translator(qapp, "zh_CN")
    qapp.processEvents()
    assert dialog.windowTitle() == "视频交付质量报告"
    assert dialog.comparison.horizontalHeaderItem(1).text() == "原视频"
    assert dialog.comparison.item(6, 0).text() == "综合响度"
    assert dialog.checks.item(6, 1).text() == "需要人工检查"
    for tab in (0, 1):
        dialog.tabs.setCurrentIndex(tab)
        qapp.processEvents()
        assert dialog.size().width() == 600 and dialog.size().height() == 440
        assert dialog.rect().contains(dialog.close_btn.mapTo(dialog,
                                      dialog.close_btn.rect().bottomRight()))
    install_translator(qapp, "en_US")
    qapp.processEvents()
    assert dialog.windowTitle() == "Delivery quality report"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()


@pytest.mark.parametrize("malformed", [None, [], {"video": [None], "audio": "bad"}])
def test_incomplete_metadata_is_explicitly_unmeasured(dialog, malformed):
    dialog._report = {"source": malformed, "output": malformed}
    dialog._render()
    for row in range(dialog.comparison.rowCount()):
        assert dialog.comparison.item(row, 1).text() == "Not measured"
        assert dialog.comparison.item(row, 2).text() == "Not measured"


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), "30"])
def test_invalid_numbers_are_not_shown_as_measurements(dialog, value):
    assert dialog._number(value, "LUFS") == "Not measured"


def test_silent_video_does_not_invent_audio_measurements(dialog):
    for key in ("source", "output"):
        dialog._report[key]["audio"] = []
    dialog._render()
    for row in range(6, 10):
        assert dialog.comparison.item(row, 1).text() == "No audio track"
        assert dialog.comparison.item(row, 2).text() == "No audio track"


def test_failed_checks_warnings_and_packaging_are_readable(dialog):
    dialog._report["quality_check"].update(status="failed", faststart=False,
                                           failures=["audio_clipping", "unknown", {}])
    dialog._report["warnings"] = ["Check dialogue.", None]
    dialog._report["effective_rules"]["packaging"] = {
        "enabled": True, "title": {"enabled": True}, "logo": {"enabled": False},
    }
    dialog._render()
    assert dialog.summary.text() == "Technical QA: Failed"
    assert dialog.checks.item(1, 1).text() == "Failed"
    assert "Failed: Measured true peak" in dialog.notices.text()
    assert "Check dialogue." in dialog.notices.text()
    assert "Title: Enabled. Logo: Disabled" in dialog.changes.text()
    assert "audio_clipping" not in dialog.notices.text()
    dialog.show()
    dialog.close_btn.click()
    assert not dialog.isVisible()
