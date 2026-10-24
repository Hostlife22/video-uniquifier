"""Delivery guardrails and native graph contracts without external processes."""

from __future__ import annotations

import hashlib
import json
import math

import pytest

from tests.unit.test_pipeline_graph import _src
from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.models import SubtitleStream
from video_uniquifier.core.preflight import PreflightFinding
from video_uniquifier.core.reels import inspection, native, processor, runtime
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.runtime import ReelsError
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.transforms.audio_loudnorm import LoudnormMeasurement


@pytest.fixture
def measurement():
    return LoudnormMeasurement(input_i=-20, input_tp=-5, input_lra=3,
                              input_thresh=-30, target_offset=0)


@pytest.mark.parametrize("kind,code", [
    ("missing_video", "missing_video"), ("pixels", "input_pixels"),
    ("duration", "input_duration"), ("trim", "trim_duration"),
    ("subtitles", "trim_subtitle_track"), ("hdr", "hdr_requires_tonemap"),
    ("matrix", "unsupported_sdr_matrix"), ("transfer", "unknown_hdr_transfer"),
])
def test_source_validation_rejects_unsupported_media_before_encoding(
    tmp_path, monkeypatch, kind, code,
):
    source = _src(tmp_path, hdr=kind == "hdr")
    rules = ReelsRules()
    if kind == "missing_video":
        source = source.model_copy(update={"video": []})
    elif kind == "pixels":
        rules.worker.max_pixels = 4096
    elif kind == "duration":
        source = source.model_copy(update={"duration_sec": math.inf})
    elif kind == "trim":
        rules.scenes.trim_start_sec = source.duration_sec
    elif kind == "subtitles":
        rules.scenes.trim_start_sec = 1
        source = source.model_copy(update={"subtitle": [SubtitleStream(index=2, codec="srt")]})
    elif kind in {"matrix", "transfer"}:
        color = source.video[0].color.model_copy(update={
            "space": "bt2020c" if kind == "matrix" else "bt2020nc",
            "transfer": "unknown" if kind == "transfer" else "bt709",
        })
        video = source.video[0].model_copy(update={"color": color})
        source = source.model_copy(update={"video": [video]})
    monkeypatch.setattr(processor, "probe", lambda _path: source)
    with pytest.raises(ReelsError) as caught:
        processor.inspect_source(source.path, rules)
    assert caught.value.code == code


def test_source_size_and_suffix_limits_precede_media_probe(tmp_path, monkeypatch):
    def unexpected_probe(_path):
        pytest.fail("rejected file reached ffprobe")

    monkeypatch.setattr(processor, "probe", unexpected_probe)
    rules = ReelsRules.model_validate({"worker": {"max_input_mb": 1}})
    path = tmp_path / "media.mp4"
    with pytest.raises(ReelsError) as caught:
        processor.inspect_source(path, rules)
    assert caught.value.code == "input_path"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ReelsError) as caught:
        processor.inspect_source(path, rules)
    assert caught.value.code == "input_size"
    path = path.rename(tmp_path / "media.exe")
    with pytest.raises(ReelsError) as caught:
        processor.inspect_source(path, rules)
    assert caught.value.code == "input_extension"


def test_preflight_failure_stops_delivery_and_hdr_requires_explicit_conversion(
    tmp_path, monkeypatch,
):
    source = _src(tmp_path, hdr=True)
    rules = ReelsRules.model_validate({"video": {"hdr_policy": "tonemap_sdr"}})
    monkeypatch.setattr(processor, "probe", lambda _path: source)
    assert processor.inspect_source(source.path, rules) is source
    finding = PreflightFinding(code="encoder_unavailable", severity="fail", message="No encoder")
    monkeypatch.setattr(processor, "preflight", lambda *_args, **_kwargs: [finding])
    base = native.validate_native_profile(native.default_profile_path())
    with pytest.raises(ReelsError) as caught:
        processor.prepare_plan(source, rules, base, tmp_path)
    assert caught.value.code == "preflight_failed"
    assert "encoder_unavailable" in str(caught.value)


@pytest.mark.parametrize("audio_enabled", [True, False])
def test_derived_graph_uses_default_audio_and_applies_synchronized_trim(
    tmp_path, audio_enabled, measurement,
):
    source = _src(tmp_path, n_audio=2)
    source = source.model_copy(update={"audio": [
        audio.model_copy(update={"is_default": index == 1})
        for index, audio in enumerate(source.audio)
    ]})
    rules = ReelsRules.model_validate({"audio": {"enabled": audio_enabled},
        "scenes": {"trim_start_sec": 1.0, "trim_end_sec": 1.0}})
    base = native.validate_native_profile(native.default_profile_path())
    profile = native.derive_profile(base, rules, source)
    assert profile.audio_tracks == [2]
    plan = native.create_plan(source, profile)
    args = native.compose_command(plan, rules, tmp_path / "out.mp4", 3, "24",
                                  measurement, [(tmp_path / "title.png", 0.5, 2.0)])
    graph = args[args.index("-filter_complex") + 1]
    assert "[0:2]atrim=start=1.000000000:end=4.000000000" in graph
    assert "trim=start=1.000000000:end=4.000000000" in graph
    assert ("loudnorm=" in graph) is audio_enabled
    assert "between(t,0.500000,2.000000)" in graph
    assert args.count("-filter_complex") == 1
    assert args[args.index("-t") + 1] == "3.000000000"
    assert args[args.index("-r") + 1] == "24"
    assert args[args.index("-ar:a:0") + 1] == "48000"


def test_hdr_graph_and_missing_audio_do_not_request_loudness_measurements(tmp_path):
    source = _src(tmp_path, hdr=True, n_audio=0)
    rules = ReelsRules.model_validate({"video": {"hdr_policy": "tonemap_sdr"}})
    profile = native.derive_profile(native.validate_native_profile(native.default_profile_path()),
                                    rules, source)
    assert [transform.id for transform in profile.transforms] == [
        "video.tonemap_sdr", "video.fit_aspect",
    ]
    plan = native.create_plan(source, profile)
    assert native.measure_audio(plan, rules, 5, tmp_path / "cache.json", CancelToken()) == (
        None, "missing",
    )
    args = native.compose_command(plan, rules, tmp_path / "out.mp4", 5, "24", None, [])
    graph = args[args.index("-filter_complex") + 1]
    assert "tonemap" in graph and "[reels_audio]" not in graph
    assert "-c:a:0" not in args


def test_loudness_cache_avoids_remeasurement_and_excludes_silent_nonfinite_values(
    tmp_path, monkeypatch, measurement,
):
    source = _src(tmp_path)
    rules = ReelsRules()
    profile = native.derive_profile(native.validate_native_profile(native.default_profile_path()),
                                    rules, source)
    plan = native.create_plan(source, profile)
    calls = []

    def measure(*_args, **kwargs):
        calls.append(kwargs)
        return measurement

    monkeypatch.setattr(native, "measure", measure)
    cache = tmp_path / "cache.json"
    assert native.measure_audio(plan, rules, 5, cache, CancelToken()) == (measurement, "measured")
    assert native.measure_audio(plan, rules, 5, cache, CancelToken()) == (measurement, "measured")
    assert len(calls) == 1
    assert "aformat=channel_layouts=stereo" in calls[0]["pre_filter_complex"]
    rules.audio.enabled = False
    assert native.measure_audio(plan, rules, 5, cache, CancelToken()) == (None, "disabled")
    rules.audio.enabled = True
    silent = measurement.model_copy(update={"input_i": -math.inf, "input_tp": -math.inf})
    monkeypatch.setattr(native, "measure", lambda *_args, **_kwargs: silent)
    empty_cache = tmp_path / "silent.json"
    assert native.measure_audio(plan, rules, 5, empty_cache, CancelToken())[1] == "silent"
    assert not empty_cache.exists()


@pytest.mark.parametrize("cadence,variable", [
    ("VFR:0.5 min: 33 max: 34", False), ("VFR:0.5 min: 33 max: 66", True),
])
def test_diagnostics_distinguish_timestamp_rounding_from_vfr_and_report_intervals(
    tmp_path, monkeypatch, cadence, variable,
):
    text = cadence + "\nblack_start:1 black_end:2 black_duration:1\n"
    text += "silence_start: 0.5\nsilence_end: 1.5\nsilence_start: 4\n"
    monkeypatch.setattr(inspection, "execute", lambda *_args, **_kwargs: text)
    details = {"streams": [{"codec_type": "video", "time_base": "1/1000"}],
               "format": {"duration": "5"}}
    result = inspection.scan_source(tmp_path / "source.mp4", details, ReelsRules(), tmp_path,
                                    CancelToken(), 1)
    assert result["variable_frame_rate"] is variable
    assert result["black_intervals"] == [{"start_sec": 1, "end_sec": 2, "duration_sec": 1}]
    assert result["silence_intervals"] == [
        {"start_sec": 0.5, "end_sec": 1.5, "duration_sec": 1},
        {"start_sec": 4, "end_sec": 5, "duration_sec": 1},
    ]
    assert result["edits_applied"] is False


def test_unverified_cadence_and_invalid_probe_output_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(inspection, "execute", lambda *_args, **_kwargs: "[]")
    with pytest.raises(ReelsError) as caught:
        inspection.stream_details(tmp_path / "source.mp4", tmp_path, CancelToken())
    assert caught.value.code == "probe_invalid"
    with pytest.raises(ReelsError) as caught:
        inspection.scan_source(tmp_path / "source.mp4", {}, ReelsRules(), tmp_path,
                                CancelToken(), None)
    assert caught.value.code == "cadence_unverified"


def test_queued_cancellation_cleans_work_and_never_publishes_media(tmp_path):
    token = CancelToken()
    token.cancel()
    with pytest.raises(ReelsError) as caught:
        processor.process_video(tmp_path / "source.mp4", ReelsRules(), tmp_path / "jobs",
                                job_id="cancelled", cancel_token=token)
    assert caught.value.code == "cancelled"
    root = tmp_path / "jobs"
    report = json.loads((root / "failures/cancelled.json").read_text())
    assert report["status"] == "cancelled" and report["output"] is None
    assert not (root / "results").exists()
    assert not (root / "work/cancelled").exists()


def test_runtime_preserves_cancellation_instead_of_marking_it_retryable(tmp_path, monkeypatch):
    token = CancelToken()

    def interrupted(*_args, **_kwargs):
        token.cancel()
        raise PipelineError("process terminated")

    monkeypatch.setattr(runtime, "run", interrupted)
    with pytest.raises(ReelsError) as caught:
        runtime.execute(["ffmpeg", "output.mp4"], tmp_path / "log", token)
    assert caught.value.code == "cancelled" and not caught.value.retryable
    source = tmp_path / "source.mp4"
    source.write_bytes(b"owned test content")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert runtime.content_hash(source, CancelToken()) == expected
    with pytest.raises(ReelsError, match="cancelled"):
        runtime.content_hash(source, token)
