"""Real-domain guards for HDR quality and long stratified audio clock evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_uniquifier.core.probe import probe
from video_uniquifier.core.qa import audio_fp, vmaf
from video_uniquifier.core.qa.report import build_report
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin


@pytest.mark.integration
def test_long_stratified_audio_keeps_similarity_without_inventing_physical_clock(
    tmp_path: Path,
) -> None:
    if not audio_fp.fpcalc_available():
        pytest.skip("fpcalc required")
    source = tmp_path / "long-varying.flac"
    subprocess.run([
        ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i",
        "aevalsrc=0.2*sin(2*PI*(300*t+0.1*t*t)):s=11025:d=620",
        "-c:a", "flac", str(source),
    ], check=True, capture_output=True, timeout=60)
    result = audio_fp.analyze_pair(
        source, source, input_duration_sec=620, output_duration_sec=620,
    )
    assert result.similarity.available
    assert result.similarity.similarity == pytest.approx(1)
    assert result.registered is not None and not result.registered.available
    assert result.registered.offset_frames is None
    assert "physical timeline" in (result.registered.note or "")
    assert "stratified" in (result.coverage_note or "")


@pytest.mark.integration
def test_raw_hdr_report_does_not_call_standard_sdr_vmaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "pq.mkv"
    subprocess.run([
        ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=64x64:rate=24:duration=1",
        "-vf", "format=yuv420p10le,setparams=color_primaries=bt2020:"
        "color_trc=smpte2084:colorspace=bt2020nc:range=limited",
        "-c:v", "libx265", "-preset", "ultrafast",
        "-x265-params", "pools=1:frame-threads=1:hdr10=1:colorprim=9:transfer=16:"
        "colormatrix=9", "-color_primaries", "bt2020",
        "-color_trc", "smpte2084", "-colorspace", "bt2020nc", str(source),
    ], check=True, capture_output=True, timeout=60)
    assert probe(source).video[0].color.is_hdr

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("standard SDR VMAF invoked in raw HDR domain")

    monkeypatch.setattr(vmaf, "compute", forbidden)
    report = build_report(source, source, samples=4, run_audio_fp=False, run_ssim=False,
                          predict_cid=False, run_registered=False)
    assert report.vmaf_mean is None
    assert any("raw HDR domain" in note for note in report.notes)
