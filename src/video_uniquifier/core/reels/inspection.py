"""Source cadence and report-only diagnostics; output format/timing/loudness QA."""

from __future__ import annotations

import json
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from video_uniquifier.core.media_validation import inspect_output_decode
from video_uniquifier.core.models import SourceMeta
from video_uniquifier.core.qa.loudness import measure_output
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.runtime import ReelsError, check_cancel, execute
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin, ffprobe_bin

COMMON_RATES = (Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
                Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60))


def stream_details(path: Path, work: Path, token: CancelToken) -> dict[str, Any]:
    """Supplement SourceMeta without changing the stable engine model."""
    text = execute([ffprobe_bin(), "-v", "error", "-show_streams", "-show_format",
                    "-of", "json", str(path)], work / "ffprobe.json", token,
                   timeout=60, progress=False)
    raw: object = json.loads(text)
    if not isinstance(raw, dict):
        raise ReelsError("probe_invalid", "FFprobe did not return a metadata object.")
    return raw


def video_details(details: dict[str, Any]) -> dict[str, Any]:
    return next((stream for stream in details.get("streams", [])
                 if stream.get("codec_type") == "video"
                 and not stream.get("disposition", {}).get("attached_pic")), {})


def rate_for(source_rate: float, variable: bool, rules: ReelsRules) -> str:
    """Preserve recognized rational CFR rates, otherwise explicitly deliver 30 CFR."""
    if not variable and rules.video.fps_mode == "auto":
        for rate in COMMON_RATES:
            if abs(float(rate) - source_rate) < 0.01:
                return str(rate)
    return str(rules.video.fallback_fps)


def scan_source(
    path: Path, details: dict[str, Any], rules: ReelsRules, work: Path,
    token: CancelToken, audio_index: int | None,
) -> dict[str, Any]:
    """Detect VFR from actual timestamps; black/silence findings never edit content."""
    video_filters = ["vfrdet"]
    if rules.scenes.blackdetect_enabled:
        video_filters.append("blackdetect=d=0.1:pix_th=0.10")
    args = [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path),
            "-map", "0:v:0", "-vf", ",".join(video_filters)]
    if audio_index is not None and rules.scenes.silence_detect_enabled:
        args += ["-map", f"0:{audio_index}", "-af", "silencedetect=noise=-50dB:d=0.5"]
    else:
        args += ["-an"]
    args += ["-sn", "-dn", "-fps_mode", "passthrough", "-f", "null", os.devnull]
    text = execute(args, work / "source-scan.log", token,
                   timeout=rules.worker.wall_timeout_sec)
    found = re.search(r"VFR:([\d.]+).*?\(min:\s*(\d+)\s+max:\s*(\d+)", text)
    variable = False
    if found and float(found[1]) > 0:
        timebase = Fraction(video_details(details).get("time_base", "1/1000"))
        # Matroska millisecond timestamp quantization alone is not VFR.
        variable = float((int(found[3]) - int(found[2])) * timebase) > 0.002
    elif "VFR:" not in text:
        raise ReelsError("cadence_unverified", "Could not verify source frame cadence.")
    black = [{"start_sec": float(a), "end_sec": float(b), "duration_sec": float(c)}
             for a, b, c in re.findall(
                 r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", text)]
    silence: list[dict[str, float]] = []
    start: float | None = None
    for match in re.finditer(r"silence_(start|end):\s*([\d.]+)", text):
        if match[1] == "start":
            start = float(match[2])
        elif start is not None:
            end = float(match[2])
            silence.append({"start_sec": start, "end_sec": end, "duration_sec": end - start})
            start = None
    if start is not None:
        end = float(details.get("format", {}).get("duration", start))
        silence.append({"start_sec": start, "end_sec": end, "duration_sec": end - start})
    return {"variable_frame_rate": variable, "black_intervals": black,
            "silence_intervals": silence, "edits_applied": False}


def timing_evidence(details: dict[str, Any]) -> dict[str, float | None]:
    """Use stream start/end timestamps, rather than the container duration alone."""
    video = video_details(details)
    audio = next((s for s in details.get("streams", []) if s.get("codec_type") == "audio"), None)
    if audio is None:
        return {"start_drift_ms": None, "end_drift_ms": None}
    try:
        vs, ast = float(video["start_time"]), float(audio["start_time"])
        ve, ae = vs + float(video["duration"]), ast + float(audio["duration"])
    except (KeyError, TypeError, ValueError):
        return {"start_drift_ms": None, "end_drift_ms": None}
    return {"start_drift_ms": abs(vs - ast) * 1000, "end_drift_ms": abs(ve - ae) * 1000}


def inspect_delivery(
    path: Path, metadata: SourceMeta, details: dict[str, Any], rules: ReelsRules,
    expected_duration: float, expected_fps: str, token: CancelToken,
    *, audio_expected: bool, normalization_expected: bool,
) -> dict[str, Any]:
    """Fail closed on technical contract violations; no external-platform verdict."""
    check_cancel(token)
    failures: list[str] = []
    video = metadata.video[0] if metadata.video else None
    if video is None:
        failures.append("missing_video")
    else:
        if (video.codec, video.pix_fmt, video.width, video.height) != (
            "h264", "yuv420p", rules.video.width, rules.video.height,
        ):
            failures.append("video_format")
        if abs(video.width / video.height - 9 / 16) > rules.quality_gate.expected_aspect_tolerance:
            failures.append("display_aspect")
        raw_video = video_details(details)
        if raw_video.get("sample_aspect_ratio") != "1:1":
            failures.append("sample_aspect")
        if any(raw_video.get(key) != "bt709" for key in (
            "color_space", "color_transfer", "color_primaries",
        )) or video.color.is_hdr:
            failures.append("sdr_rec709")
        if abs(video.fps - float(Fraction(expected_fps))) > 0.02:
            failures.append("frame_rate")
    if metadata.container != "mp4":
        failures.append("container")
    duration_delta = abs(metadata.duration_sec - expected_duration)
    if duration_delta > rules.quality_gate.max_duration_delta_sec:
        failures.append("duration")
    if len(metadata.audio) != int(audio_expected):
        failures.append("audio_count")
    for audio in metadata.audio:
        if (audio.codec, audio.sample_rate, audio.channels) != ("aac", 48000, 2):
            failures.append("audio_format")
        raw_audio: dict[str, Any] = next(
            (s for s in details["streams"] if s["index"] == audio.index), {})
        if raw_audio.get("profile") != "LC":
            failures.append("audio_profile")
    timing = timing_evidence(details)
    drift_limit = min(rules.audio.max_av_drift_ms, rules.quality_gate.max_av_drift_ms)
    if audio_expected and any(value is None or value > drift_limit for value in timing.values()):
        failures.append("av_timing")
    decode = "not_requested"
    if rules.quality_gate.require_video_decode_check:
        failure = inspect_output_decode(path, cancel_token=token)
        decode = "passed" if failure is None else "failed"
        if failure:
            failures.append(failure.code)
    loudness = measure_output(path, metadata, cancel_token=token)
    for measured in loudness.streams:
        if measured.status != "passed":
            failures.append("loudness_unverified")
        if measured.true_peak_dbtp is not None and measured.true_peak_dbtp > 0:
            failures.append("audio_clipping")
        if normalization_expected:
            if measured.integrated_lufs is None or abs(
                measured.integrated_lufs - rules.audio.loudnorm.integrated_lufs,
            ) > 1.0:
                failures.append("loudness_target")
            if measured.true_peak_dbtp is None or measured.true_peak_dbtp > (
                rules.audio.loudnorm.true_peak_dbtp + 0.5
            ):
                failures.append("true_peak_target")
    check_cancel(token)
    return {"status": "failed" if failures else "passed", "failures": sorted(set(failures)),
            "gates_enforced": rules.quality_gate.enabled, "decode": decode,
            "expected_duration_sec": expected_duration, "duration_delta_sec": duration_delta,
            "timing": timing, "loudness": loudness.model_dump(mode="json"),
            "listening_review": "manual_required", "subtitle_review": "manual_required",
            "visual_similarity": {"status": "not_computed",
                                  "reason": "Reframed output has no registered reference."},
            "platform_originality": "not_assessed"}
