from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import needs_ffmpeg
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.processor import process_video
from video_uniquifier.core.reels.runtime import ReelsError
from video_uniquifier.core.runner import CancelToken

pytestmark = [pytest.mark.integration, needs_ffmpeg]


def rules_for(**overrides):
    raw = {"video": {"width": 720, "height": 1280},
           "scenes": {"detect_enabled": False},
           "packaging": {"safe_area_preview_enabled": False},
           "quality_gate": {"sample_preview_enabled": False}}
    for key, value in overrides.items():
        raw[key] = {**raw.get(key, {}), **value}
    return ReelsRules.model_validate(raw)


def make_clip(path: Path, kind: str) -> Path:
    rate = "30000/1001" if kind == "fractional" else "30"
    size = "90x160" if kind == "vertical" else "160x90"
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            f"testsrc2=size={size}:rate={rate}:duration=2"]
    if kind == "silent":
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    elif kind != "missing":
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2"]
    if kind == "multi":
        args += ["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=2",
                 "-map", "0:v:0", "-map", "1:a:0", "-map", "2:a:0",
                 "-disposition:a:0", "0", "-disposition:a:1", "default"]
    if kind == "vfr":
        args += ["-vf", "select='if(lt(t,1),1,not(mod(n,2)))'", "-fps_mode", "vfr"]
    if kind == "hdr":
        args += ["-x264-params", "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc"]
    if kind == "subtitles":
        args += ["-vf", "drawbox=x=2:y=76:w=10:h=8:color=white:t=fill,"
                 "drawbox=x=148:y=76:w=10:h=8:color=white:t=fill"]
    args += ["-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(path)]
    subprocess.run(args, check=True, capture_output=True, timeout=30)
    return path


def test_delivery_reuses_native_graph_and_publishes_verified_artifacts(tiny_clip, tmp_path):
    rules = ReelsRules.model_validate({
        "video": {"width": 720, "height": 1280}, "scenes": {"detect_enabled": False},
        "packaging": {"safe_area_preview_enabled": False},
    })
    events = []
    result = process_video(tiny_clip, rules, tmp_path / "jobs", job_id="baseline",
                           on_status=lambda status, progress: events.append((status, progress)))
    report = json.loads((result / "report.json").read_text())
    assert report["quality_check"]["status"] == "passed"
    assert report["output"]["video"][0]["width"] == 720
    assert report["output"]["video"][0]["height"] == 1280
    assert report["output"]["audio"][0]["channels"] == 2
    assert report["selected_audio_stream_index"] == 1
    assert report["audio_normalization"]["status"] == "measured"
    assert report["video_encode_passes"] == 1
    assert report["native_profile"]["transforms"][0]["id"] == "video.fit_aspect"
    assert report["source"]["sha256"] != report["output"]["sha256"]
    assert (result / "output.mp4").is_file()
    assert not (result / "output.tmp.mp4").exists()
    assert events[-1] == ("success", 1.0)


@pytest.mark.parametrize("kind", ["missing", "silent", "multi", "fractional", "vfr", "vertical"])
def test_delivery_input_matrix(kind, tmp_path):
    source = make_clip(tmp_path / f"{kind}.mp4", kind)
    result = process_video(source, rules_for(), tmp_path / "jobs")
    report = json.loads((result / "report.json").read_text())
    assert report["quality_check"]["status"] == "passed"
    assert report["quality_check"]["duration_delta_sec"] <= 0.1
    assert report["audio_normalization"]["status"] == {
        "missing": "missing", "silent": "silent",
    }.get(kind, "measured")
    if kind == "missing":
        assert report["output"]["audio"] == []
    if kind == "multi":
        assert report["selected_audio_stream_index"] == 2
        assert len(report["output"]["audio"]) == 1
    if kind == "fractional":
        assert report["delivery_fps"] == "30000/1001"
    if kind == "vfr":
        assert report["source_analysis"]["variable_frame_rate"]
        assert report["delivery_fps"] == "30"
    if kind == "vertical":
        assert report["native_profile"]["transforms"][0]["params"]["mode"] == "pad_black"


def test_manual_trim_changes_video_and_audio_together(tiny_clip, tmp_path):
    rules = rules_for(scenes={"trim_start_sec": 0.4, "trim_end_sec": 0.5})
    result = process_video(tiny_clip, rules, tmp_path / "jobs")
    report = json.loads((result / "report.json").read_text())
    assert report["quality_check"]["expected_duration_sec"] == pytest.approx(1.1)
    assert report["output"]["duration_sec"] == pytest.approx(1.1, abs=0.08)
    assert report["quality_check"]["timing"]["end_drift_ms"] <= 100
    with pytest.raises(ReelsError, match="entire"):
        process_video(tiny_clip, rules_for(scenes={"trim_start_sec": 3.0}), tmp_path / "bad")


def test_hdr_requires_explicit_native_tonemapping(tmp_path):
    source = make_clip(tmp_path / "hdr.mp4", "hdr")
    with pytest.raises(ReelsError) as caught:
        process_video(source, rules_for(), tmp_path / "blocked", job_id="hdr")
    assert caught.value.code == "hdr_requires_tonemap"
    assert not (tmp_path / "blocked" / "results").exists()
    result = process_video(source, rules_for(video={"hdr_policy": "tonemap_sdr"}),
                           tmp_path / "converted")
    report = json.loads((result / "report.json").read_text())
    assert report["native_profile"]["transforms"][0]["id"] == "video.tonemap_sdr"
    assert not report["output"]["video"][0]["color"]["is_hdr"]


def test_pad_blur_retains_subtitle_marks_at_both_source_edges(tmp_path):
    source = make_clip(tmp_path / "subtitles.mp4", "subtitles")
    result = process_video(source, rules_for(), tmp_path / "jobs")
    frame = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(result / "output.mp4"),
                    "-frames:v", "1", "-update", "1", str(frame)],
                   check=True, capture_output=True, timeout=30)
    with Image.open(frame) as image:
        scale = 720 / 160
        y = round((1280 - 90 * scale) / 2 + 80 * scale)
        for x in (round(7 * scale), round(153 * scale)):
            assert min(image.getpixel((x, y))) > 220


def test_cancel_before_encode_and_qa_failure_never_publish_partial_media(
    tiny_clip, tmp_path, monkeypatch,
):
    token = CancelToken()

    def cancel_on_encode(state, _progress):
        if state == "processing":
            token.cancel()

    with pytest.raises(ReelsError) as caught:
        process_video(tiny_clip, rules_for(), tmp_path / "cancel", job_id="cancel",
                      cancel_token=token, on_status=cancel_on_encode)
    assert caught.value.code == "cancelled"
    assert not (tmp_path / "cancel" / "results").exists()
    assert not (tmp_path / "cancel" / "work" / "cancel").exists()
    failure = json.loads((tmp_path / "cancel" / "failures" / "cancel.json").read_text())
    assert failure["status"] == "cancelled"
    monkeypatch.setattr("video_uniquifier.core.reels.processor.inspect_delivery", lambda *a, **kw: {
        "status": "failed", "failures": ["av_timing"],
    })
    with pytest.raises(ReelsError, match="av_timing"):
        process_video(tiny_clip, rules_for(), tmp_path / "qa", job_id="failed")
    assert not (tmp_path / "qa" / "results").exists()
    report = json.loads((tmp_path / "qa" / "failures" / "failed.json").read_text())
    assert report["quality_check"]["failures"] == ["av_timing"]


def test_native_scene_detection_produces_an_ordered_unmodified_timeline(tmp_path):
    pytest.importorskip("scenedetect")
    source = tmp_path / "scenes.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:s=90x160:r=24:d=2",
        "-f", "lavfi", "-i", "color=blue:s=90x160:r=24:d=2",
        "-f", "lavfi", "-i", "color=yellow:s=90x160:r=24:d=2",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", str(source),
    ], check=True, capture_output=True, timeout=30)
    result = process_video(source, rules_for(scenes={"detect_enabled": True}), tmp_path / "jobs")
    report = json.loads((result / "report.json").read_text())
    timeline = report["scenes"]["source_timeline"]
    assert [scene["start_sec"] for scene in timeline] == pytest.approx([0, 2, 4], abs=0.05)
    assert [scene["scene_id"] for scene in report["scenes"]["output_timeline"]] == [1, 2, 3]
    assert report["output"]["duration_sec"] == pytest.approx(6, abs=0.05)
    assert (result / "scenes.json").is_file()


def test_optional_logo_composites_once_and_preview_is_a_separate_artifact(tiny_clip, tmp_path):
    Image.new("RGBA", (80, 40), (255, 0, 0, 255)).save(tmp_path / "logo.png")
    rules = rules_for(packaging={"enabled": True, "safe_area_preview_enabled": True,
                                "logo": {"enabled": True, "source": "logo.png", "width_px": 80,
                                         "margin_x_px": 50, "margin_y_px": 200, "opacity": 1.0}})
    result = process_video(tiny_clip, rules, tmp_path / "jobs", asset_root=tmp_path)
    report = json.loads((result / "report.json").read_text())
    assert report["video_encode_passes"] == 1
    assert report["packaging"]["layers"][0]["kind"] == "logo"
    assert (result / "safe-area.png").is_file()
    with Image.open(result / "safe-area.png") as preview:
        red, green, blue = preview.getpixel((620, 220))
        assert red > 200 and green < 60 and blue < 60
    assert report["output"]["duration_sec"] == pytest.approx(2, abs=0.1)


def test_timed_title_and_logo_use_one_encode_with_bounded_transient_retry(
    tiny_clip, tmp_path, monkeypatch,
):
    fonts = [Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
             Path("C:/Windows/Fonts/arial.ttf")]
    font = next((candidate for candidate in fonts if candidate.is_file()), None)
    if font is None:
        pytest.skip("local test font unavailable")
    shutil.copyfile(font, tmp_path / "font.ttf")
    Image.new("RGBA", (50, 25), (255, 0, 0, 255)).save(tmp_path / "logo.png")
    rules = rules_for(packaging={"enabled": True, "title": {
        "enabled": True, "text": "短剧 : ' [第一集]", "font_path": "font.ttf",
        "font_size_px": 28, "start_sec": 0.25, "end_sec": 1.0,
    }, "logo": {"enabled": True, "source": "logo.png", "margin_y_px": 300}})
    from video_uniquifier.core.reels import processor

    original = processor.execute
    attempts = 0

    def transient(args, log, token, **options):
        nonlocal attempts
        if log.name.startswith("encode-"):
            attempts += 1
            if attempts == 1:
                raise ReelsError("process_failed", "Temporary encoder failure", retryable=True)
        return original(args, log, token, **options)

    monkeypatch.setattr(processor, "execute", transient)
    result = process_video(tiny_clip, rules, tmp_path / "jobs", asset_root=tmp_path)
    report = json.loads((result / "report.json").read_text())
    assert report["encode_attempts"] == 2
    assert report["video_encode_passes"] == 1
    assert [layer["kind"] for layer in report["packaging"]["layers"]] == ["logo", "title"]
    assert "between(t,0.250000,1.000000)" in report["execution_argv"][
        report["execution_argv"].index("-filter_complex") + 1]
    assert report["quality_check"]["status"] == "passed"


def test_real_worker_api_upload_process_report_and_download(tiny_clip, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    import time

    from fastapi.testclient import TestClient

    from video_uniquifier.web.reels import build_reels_app

    rules = rules_for()
    app = build_reels_app(tmp_path / "api", {rules.preset_id: rules})
    with TestClient(app) as client:
        response = client.post("/api/video-jobs", files={
            "file": ("drama.mp4", tiny_clip.read_bytes(), "video/mp4"),
        })
        assert response.status_code == 202
        identifier = response.json()["job_id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            status = client.get(f"/api/video-jobs/{identifier}").json()
            if status["status"] in {"failed", "cancelled", "success"}:
                break
            time.sleep(0.05)
        assert status["status"] == "success", status
        report = client.get(status["report_url"]).json()
        assert report["quality_check"]["status"] == "passed"
        assert len(client.get(status["output_url"]).content) > 1000
