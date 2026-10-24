from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.unit.test_pipeline_graph import _src
from video_uniquifier.cli.reels import app
from video_uniquifier.core.models import QAAudioLoudness, QALoudness
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.inspection import (
    has_faststart,
    inspect_delivery,
    rate_for,
    timing_evidence,
)
from video_uniquifier.core.reels.runtime import ReelsError, atomic_json, json_object
from video_uniquifier.core.runner import CancelToken


def test_cli_schema_and_separate_business_validation(tmp_path):
    runner = CliRunner()
    schema = runner.invoke(app, ["schema"])
    assert schema.exit_code == 0
    assert json.loads(schema.stdout)["additionalProperties"] is False
    config = tmp_path / "rules.yaml"
    config.write_text("video: {crf: 21}\n")
    valid = runner.invoke(app, ["validate", str(config)])
    assert valid.exit_code == 0
    assert json.loads(valid.stdout)["effective_rules"]["audio"]["loudnorm"]["passes"] == 2
    config.write_text("ffmpeg_command: unsafe\n")
    invalid = runner.invoke(app, ["validate", str(config)])
    assert invalid.exit_code == 2
    assert json.loads(invalid.stderr)["error"]["code"] == "invalid_configuration"


def test_cli_events_share_a_generated_job_id_and_report_cancellation(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")

    def fake_process(_source, _rules, _root, **options):
        assert len(options["job_id"]) == 32
        options["on_status"]("processing", 0.2)
        return Path(options["job_id"])

    monkeypatch.setattr("video_uniquifier.cli.reels.process_video", fake_process)
    runner = CliRunner()
    result = runner.invoke(app, ["run", str(source), "--json-events"])
    assert result.exit_code == 0, result.output
    event, completed = [json.loads(line) for line in result.stdout.splitlines()]
    assert event["job_id"] == completed["job_id"]

    def cancelled(*_args, **_options):
        raise ReelsError("cancelled", "Cancelled")

    monkeypatch.setattr("video_uniquifier.cli.reels.process_video", cancelled)
    result = runner.invoke(app, ["run", str(source)])
    assert result.exit_code == 130
    assert json.loads(result.stderr)["error"]["code"] == "cancelled"


@pytest.mark.parametrize("rate,expected", [
    (24000 / 1001, "24000/1001"), (24, "24"), (25, "25"),
    (30000 / 1001, "30000/1001"), (30, "30"), (50, "50"),
    (60000 / 1001, "60000/1001"), (60, "60"), (17, "30"),
])
def test_preserve_common_cfr_but_normalize_vfr_or_explicit_override(rate, expected):
    assert rate_for(rate, False, ReelsRules()) == expected
    assert rate_for(rate, True, ReelsRules()) == "30"
    override = ReelsRules.model_validate({"video": {"fps_mode": "cfr30"}})
    assert rate_for(rate, False, override) == "30"


def test_timing_requires_real_stream_timestamps():
    assert timing_evidence({"streams": []}) == {"start_drift_ms": None, "end_drift_ms": None}
    streams = [{"codec_type": "video"}, {"codec_type": "audio"}]
    assert timing_evidence({"streams": streams})["end_drift_ms"] is None
    streams[0].update(start_time="0", duration="10")
    streams[1].update(start_time="0.02", duration="10.1")
    evidence = timing_evidence({"streams": streams})
    assert evidence["start_drift_ms"] == pytest.approx(20)
    assert evidence["end_drift_ms"] == pytest.approx(120)


@pytest.mark.parametrize("atoms,expected", [
    ([(8, b"ftyp"), (8, b"moov"), (8, b"mdat")], True),
    ([(8, b"ftyp"), (8, b"mdat"), (8, b"moov")], False),
    ([(0, b"free")], False), ([], False),
])
def test_faststart_checks_real_atom_order(tmp_path, atoms, expected):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"".join(struct.pack(">I4s", size, kind) for size, kind in atoms))
    assert has_faststart(path) is expected


def test_atomic_report_preserves_previous_json_if_serialization_fails(tmp_path):
    path = tmp_path / "report.json"
    atomic_json(path, {"status": "success"}, root=tmp_path)
    with pytest.raises(ValueError):
        atomic_json(path, {"measurement": float("nan")}, root=tmp_path)
    assert json_object(path) == {"status": "success"}
    assert list(tmp_path.iterdir()) == [path]
    path.write_text("[]")
    with pytest.raises(ValueError, match="object"):
        json_object(path)


def test_atomic_report_rejects_escape_and_symlink_paths(tmp_path):
    root = tmp_path / "jobs"
    root.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text('{"private": true}')
    with pytest.raises(ReelsError, match="root"):
        atomic_json(root / ".." / "secret.json", {"private": False}, root=root)
    link = root / "report.json"
    try:
        link.symlink_to(secret)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ReelsError, match="root"):
        atomic_json(link, {"private": False}, root=root)
    assert json_object(secret) == {"private": True}


def test_quality_gate_reports_bad_format_sync_decode_and_clipping(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from video_uniquifier.core.reels import inspection

    metadata = _src(tmp_path)
    metadata.path.write_bytes(struct.pack(">I4s", 8, b"mdat"))
    metadata = metadata.model_copy(update={
        "container": "mkv", "duration_sec": 8,
        "audio": [metadata.audio[0].model_copy(update={"codec": "opus", "channels": 1})],
    })
    measured = QALoudness(status="passed", streams=[QAAudioLoudness(
        stream_index=1, status="passed", integrated_lufs=-5, true_peak_dbtp=1,
    )])
    monkeypatch.setattr(inspection, "measure_output", lambda *a, **kw: measured)
    monkeypatch.setattr(inspection, "inspect_output_decode", lambda *a, **kw: SimpleNamespace(
        code="decode_failed"))
    report = inspect_delivery(metadata.path, metadata, {"streams": []}, ReelsRules(), 5, "30",
                              CancelToken(), audio_expected=True, normalization_expected=True)
    assert set(report["failures"]) == {
        "video_format", "display_aspect", "sample_aspect", "sdr_rec709", "frame_rate",
        "container", "faststart", "duration", "audio_format", "audio_profile", "av_timing",
        "decode_failed", "audio_clipping", "loudness_target", "true_peak_target",
    }
    assert report["status"] == "failed" and report["gates_enforced"] is True


def test_quality_rejects_missing_streams_and_unverified_loudness(tmp_path, monkeypatch):
    from video_uniquifier.core.reels import inspection

    metadata = _src(tmp_path).model_copy(update={"video": [], "audio": []})
    metadata.path.write_bytes(struct.pack(">I4s", 8, b"moov"))
    monkeypatch.setattr(inspection, "measure_output", lambda *a, **kw: QALoudness(
        status="not_verified", streams=[QAAudioLoudness(stream_index=1, status="not_verified")]))
    rules = ReelsRules.model_validate({"quality_gate": {
        "enabled": False, "require_video_decode_check": False,
    }})
    result = inspect_delivery(metadata.path, metadata, {"streams": []}, rules, 5, "24",
                              CancelToken(), audio_expected=True, normalization_expected=True)
    assert {"missing_video", "audio_count", "loudness_unverified", "loudness_target",
            "true_peak_target", "av_timing"}.issubset(result["failures"])
    assert result["gates_enforced"] is False and result["status"] == "failed"
    assert result["decode"] == "not_requested"
