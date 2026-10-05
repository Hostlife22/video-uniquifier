"""Unavailable measurements must not masquerade as successful zero scores."""

from pathlib import Path

import pytest

from video_uniquifier.core.calibration import loop
from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.qa import audio_fp, cid_predict, phash, sscd


def test_absent_visual_and_audio_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(phash, "_probe_duration", lambda _: 10.)
    monkeypatch.setattr(phash, "_sample_hashes_range", lambda *args: [])
    monkeypatch.setattr(cid_predict, "_full_fingerprint", lambda _: [])
    result = cid_predict.predict(Path("a"), Path("b"))
    assert result.match_probability_self is None
    assert not result.chunks


def test_residual_window_and_common_clock(monkeypatch) -> None:
    monkeypatch.setattr(phash, "_probe_duration", lambda _: 9.5)
    monkeypatch.setattr(phash, "_sample_hashes_range", lambda p, start, span, n: [0] * n)
    monkeypatch.setattr(cid_predict, "_full_fingerprint", lambda _: [])
    result = cid_predict.predict(Path("a"), Path("b"))
    assert len(result.chunks) == 3
    assert result.chunks[-1].end_sec == 9.5
    assert all(c.audio_similarity is None for c in result.chunks)


def test_calibration_refuses_missing_audio(monkeypatch) -> None:
    result = cid_predict.CIDPredictResult(.1, [], None, [])
    monkeypatch.setattr(loop, "predict", lambda *args: result)
    monkeypatch.setattr(loop, "probe_file", lambda _: type("Meta", (), {"audio": [1]})())
    with pytest.raises(PipelineError, match="audio fingerprint required"):
        loop._evaluate_chromaprint(Path("a"), Path("b"), None)


def test_constant_audio_has_no_alignment_confidence() -> None:
    result = audio_fp.align_fingerprints([7] * 100, [7] * 100)
    assert not result.available
    assert result.confidence == 0
    assert result.offset_frames is None


def test_static_visual_matrix_has_no_alignment_confidence() -> None:
    result = sscd.align_cosine_matrix([[1.] * 8 for _ in range(8)])
    assert not result.available
    assert result.confidence == 0
    assert result.mean_offset_frames is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1.1])
def test_invalid_cosine_matrix_is_unavailable(value: float) -> None:
    result = sscd.align_cosine_matrix([[value, .3], [.3, .9]])
    assert not result.available
    assert result.mean_similarity is None


def test_calibration_cache_rejects_changed_toolchain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(loop, "_scoring_environment", lambda _: "old")
    loop._save_trial(tmp_path, "plan", "chromaprint", loop._CachedTrial(.1, 90., "vmaf", None))
    assert loop._load_trial(tmp_path, "plan", "chromaprint") is not None
    monkeypatch.setattr(loop, "_scoring_environment", lambda _: "new")
    assert loop._load_trial(tmp_path, "plan", "chromaprint") is None
