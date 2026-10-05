"""Prevent availability and held-out data leakage from inflating evaluation."""

import pytest

from tools.audit_detector_eval import assess, choose_threshold


def test_valid_zero_is_a_measurement_but_missing_positive_is_missed() -> None:
    rows = [
        {"positive": True, "scores": {"audio": 0.}},
        {"positive": True, "scores": {"audio": None}},
        {"positive": False, "scores": {"audio": None}},
    ]
    result = assess(rows, "audio", 0.)
    assert result["tp"] == 1 and result["fn"] == 1 and result["tn"] == 1
    assert result["unavailable"] == 2
    assert result["recall"] == .5


def test_holdout_cannot_choose_threshold() -> None:
    with pytest.raises(ValueError, match="development"):
        choose_threshold([{"split": "holdout", "scores": {"phash": .99}}], "phash")
