"""Experimental VBV arms retain every unrelated encoder option."""
import json
from types import SimpleNamespace

import pytest

from tools.rate_control_experiment import scaled_vbv, select_existing


def test_scaled_vbv_changes_only_two_values():
    original = ["-c:v", "libx264", "-crf", "18", "-maxrate", "1000k",
                "-bufsize", "2M", "-g", "60", "out.mp4"]
    expected = list(original)
    expected[5], expected[7] = "4000k", "8M"
    assert scaled_vbv(original, 4) == expected
    assert original[5] == "1000k"


@pytest.mark.parametrize("multiplier", [0, 1, 33, float("nan"), float("inf")])
def test_scaled_vbv_rejects_invalid_multiplier(multiplier):
    with pytest.raises(ValueError):
        scaled_vbv(["-maxrate", "1000", "-bufsize", "2000"], multiplier)


@pytest.mark.parametrize("args", [["-maxrate"], ["-maxrate", "1000"]])
def test_scaled_vbv_requires_complete_bounded_arm(args):
    with pytest.raises(ValueError):
        scaled_vbv(args, 2)


@pytest.fixture
def selection_fixture(tmp_path, monkeypatch):
    root = tmp_path / "experiment"
    cell = root / "case__variant"
    cell.mkdir(parents=True)
    (cell / "reference.mkv").write_bytes(b"reference")
    rows = []
    for policy in ("source_cap", "crf_only"):
        (cell / f"{policy}-0.mp4").write_bytes(b"encoded")
        rows.append({"case": "case", "variant": "variant", "policy": policy,
                     "repeat": 0, "size_bytes": 7, "seconds": 6, "vmaf": 100,
                     "wall_sec": 1, "source_sha256": "a" * 64})
    (root / "results.json").write_text(json.dumps({
        "complete": True,
        "method": "paired encoding-only against identical transformed FFV1 SDR reference",
        "rows": rows,
    }))
    monkeypatch.setattr("tools.rate_control_experiment.probe", lambda _: SimpleNamespace(
        duration_sec=6, video=[SimpleNamespace(color=SimpleNamespace(is_hdr=False))],
    ))
    monkeypatch.setattr("tools.rate_control_experiment.decoded_timeline", lambda _: {
        "streams": [{"kind": "video", "frames": 144, "start_sec": 0, "end_sec": 6,
                     "missing_pts_frames": 0, "non_increasing_pts_frames": 0}],
    })
    return root, tmp_path / "selection.json"


def test_existing_selection_uses_fresh_scores_not_stale_scores(selection_fixture, monkeypatch):
    root, output = selection_fixture
    calls = []

    def score(reference, candidate):
        calls.append((reference.name, candidate.name))
        value = 90 if candidate.name.startswith("source_cap") else 96
        return SimpleNamespace(score=value, note="measured")

    monkeypatch.setattr("tools.rate_control_experiment.vmaf", score)
    result = select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                             maximum_average_bitrate_bps=1000)
    assert len(calls) == 2
    assert result["cells"][0]["selection"]["selected_candidate_id"] == "crf_only-0.mp4"
    assert result["production_defaults_changed"] is False
    assert output.exists()


def test_missing_current_metric_cannot_select_old_high_score(selection_fixture, monkeypatch):
    root, output = selection_fixture
    monkeypatch.setattr("tools.rate_control_experiment.vmaf", lambda *_: SimpleNamespace(
        score=None, note="unavailable",
    ))
    result = select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                             maximum_average_bitrate_bps=1000)
    assert result["cells"][0]["selection"]["status"] == "NO_FEASIBLE_CANDIDATE"


def test_changed_candidate_size_refused(selection_fixture):
    root, output = selection_fixture
    (root / "case__variant/source_cap-0.mp4").write_bytes(b"changed size")
    with pytest.raises(ValueError, match="size differs"):
        select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                        maximum_average_bitrate_bps=1000)
    assert not output.exists()


def test_hdr_reference_refused(selection_fixture, monkeypatch):
    root, output = selection_fixture
    monkeypatch.setattr("tools.rate_control_experiment.probe", lambda _: SimpleNamespace(
        duration_sec=6, video=[SimpleNamespace(color=SimpleNamespace(is_hdr=True))],
    ))
    with pytest.raises(ValueError, match="SDR"):
        select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                        maximum_average_bitrate_bps=1000)
    assert not output.exists()


def test_hdr_candidate_cannot_be_scored_as_sdr(selection_fixture, monkeypatch):
    root, output = selection_fixture
    monkeypatch.setattr("tools.rate_control_experiment.probe", lambda path: SimpleNamespace(
        duration_sec=6,
        video=[SimpleNamespace(color=SimpleNamespace(is_hdr=path.suffix == ".mp4"))],
    ))
    with pytest.raises(ValueError, match="candidate must be bounded"):
        select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                        maximum_average_bitrate_bps=1000)
    assert not output.exists()


def test_failed_decoded_frames_cannot_pass_quality(selection_fixture, monkeypatch):
    root, output = selection_fixture
    monkeypatch.setattr("tools.rate_control_experiment.decoded_timeline", lambda path: {
        "streams": [{"kind": "video", "frames": 143 if path.suffix == ".mp4" else 144,
                     "start_sec": 0, "end_sec": 6, "missing_pts_frames": 0,
                     "non_increasing_pts_frames": 0}],
    })
    monkeypatch.setattr("tools.rate_control_experiment.vmaf", lambda *_: SimpleNamespace(
        score=100, note="measured",
    ))
    result = select_existing(root, output, minimum_vmaf=95, maximum_size_ratio=2,
                             maximum_average_bitrate_bps=1000)
    assert result["cells"][0]["selection"]["status"] == "NO_FEASIBLE_CANDIDATE"
