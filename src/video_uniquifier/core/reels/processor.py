"""One local job: preflight -> one encode -> QA -> atomic artifact directory."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from video_uniquifier import __version__
from video_uniquifier.core.models import Plan, Profile, SourceMeta
from video_uniquifier.core.output_reservation import RunAdmission, RunAdmissionFull
from video_uniquifier.core.preflight import has_fail, preflight
from video_uniquifier.core.probe import probe
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.inspection import (
    inspect_delivery,
    rate_for,
    scan_source,
    stream_details,
    video_details,
)
from video_uniquifier.core.reels.native import (
    compose_command,
    create_plan,
    default_profile_path,
    derive_profile,
    measure_audio,
    validate_native_profile,
)
from video_uniquifier.core.reels.runtime import (
    ReelsError,
    atomic_json,
    check_cancel,
    content_hash,
    execute,
)
from video_uniquifier.core.resource_budget import resource_pool_dir
from video_uniquifier.core.runner import CancelToken, RunEvent
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin

StatusCallback = Callable[[str, float], None]


def inspect_source(path: Path, rules: ReelsRules) -> SourceMeta:
    """Validate actual media after bounded path/size checks, never the suffix alone."""
    if not path.is_file() or path.is_symlink():
        raise ReelsError("input_path", "Input must be a regular local file, not a symlink.")
    if path.suffix.lower().lstrip(".") not in rules.worker.allow_input_extensions:
        raise ReelsError("input_extension", "This input file extension is not allowed.")
    if path.stat().st_size > rules.worker.max_input_mb * 1024 * 1024:
        raise ReelsError("input_size", "Input exceeds the configured upload size limit.")
    source = probe(path)
    if not source.video:
        raise ReelsError("missing_video", "Input has no primary video stream.")
    video = source.video[0]
    if video.width * video.height > rules.worker.max_pixels:
        raise ReelsError("input_pixels", "Input exceeds the configured decoded pixel limit.")
    if not math.isfinite(source.duration_sec) or not 0 < source.duration_sec <= (
        rules.worker.max_duration_sec
    ):
        raise ReelsError("input_duration", "Input duration is missing or exceeds the limit.")
    if rules.scenes.trim_start_sec + rules.scenes.trim_end_sec >= source.duration_sec:
        raise ReelsError("trim_duration", "Trim would remove the entire video.")
    if source.subtitle and (rules.scenes.trim_start_sec or rules.scenes.trim_end_sec):
        raise ReelsError("trim_subtitle_track", "Trim with selectable subtitles is unsupported; "
                         "burn authorized subtitles into the source first to retain timing.")
    if video.color.is_hdr and rules.video.hdr_policy != "tonemap_sdr":
        raise ReelsError("hdr_requires_tonemap", "HDR/PQ/HLG source requires explicit "
                         "video.hdr_policy=tonemap_sdr and FFmpeg zscale support.")
    return source


def prepare_plan(source: SourceMeta, rules: ReelsRules, base: Profile, work: Path) -> tuple[
    Plan, list[dict[str, Any]],
]:
    profile = derive_profile(base, rules, source)
    plan = create_plan(source, profile)
    findings = preflight(source, plan, plan.encoder, work_dir=work,
                         verify_encoder_capability=True)
    if has_fail(findings):
        failed = "; ".join(f"{f.code}: {f.message}" for f in findings if f.severity == "fail")
        raise ReelsError("preflight_failed", failed)
    return plan, [finding.model_dump() for finding in findings]


def process_video(
    source_path: Path, rules: ReelsRules, root: Path, *,
    job_id: str | None = None, asset_root: Path | None = None,
    profile_path: Path | None = None, cancel_token: CancelToken | None = None,
    on_status: StatusCallback | None = None,
) -> Path:
    """Publish results/<job_id> only after QA; failure reports contain no media artifact."""
    job_id = job_id or uuid4().hex
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", job_id):
        raise ReelsError("job_id", "Invalid job id.")
    token = cancel_token or CancelToken()
    status = on_status or (lambda _state, _progress: None)
    work = root / "work" / job_id
    final = root / "results" / job_id
    if final.exists() or work.exists():
        raise ReelsError("job_exists", "Job id already exists; retry with a fresh attempt id.")
    work.mkdir(parents=True)
    started = time.monotonic()
    report: dict[str, Any] = {
        "schema_version": 1, "job_id": job_id, "preset_id": rules.preset_id,
        "preset_version": rules.schema_version, "engine_version": __version__,
        "engine_baseline": "e9138ddbc798cb23e28b44d9edf7959a712f0add",
        "source": None, "output": None, "warnings": [], "quality_check": None,
        "effective_rules": rules.model_dump(mode="json"), "status": "probing",
    }
    lease: RunAdmission | None = None
    try:
        status("queued", 0.0)
        pool = resource_pool_dir("facebook-reels-cpu")
        while lease is None:
            check_cancel(token)
            try:
                lease = RunAdmission.acquire(pool, job_id, rules.worker.max_cpu_jobs)
            except RunAdmissionFull:
                token.wait(0.1)
        check_cancel(token)
        status("probing", 0.02)
        base = validate_native_profile(profile_path or default_profile_path())
        source = inspect_source(source_path, rules)
        check_cancel(token)
        source_hash = content_hash(source_path, token)
        report["source"] = source.model_dump(mode="json", exclude={"path"})
        report["source"].update(filename=source_path.name, sha256=source_hash)
        details = stream_details(source_path, work, token)
        raw_video = video_details(details)
        rotation = next((s.get("rotation", 0) for s in raw_video.get("side_data_list", [])
                         if "rotation" in s), 0)
        if abs(float(rotation)) % 180:
            report["warnings"].append("Source rotation is applied before fitting the canvas.")
        plan, findings = prepare_plan(source, rules, base, work)
        report["preflight"] = findings
        duration = source.duration_sec - rules.scenes.trim_start_sec - rules.scenes.trim_end_sec
        selected = plan.profile.audio_tracks
        audio_index = selected[0] if isinstance(selected, list) else (
            source.audio[0].index if source.audio else None
        )
        report["selected_audio_stream_index"] = audio_index
        if len(source.audio) > 1:
            report["warnings"].append("Only the default/first audio track is delivered; "
                                       "other language/commentary tracks are not mixed.")
        scan = scan_source(source_path, details, rules, work, token, audio_index)
        report["source_analysis"] = scan
        fps = rate_for(source.video[0].fps, scan["variable_frame_rate"], rules)
        report["delivery_fps"] = fps
        if scan["variable_frame_rate"]:
            report["warnings"].append("VFR normalized to 30 CFR; review speech sync.")
        video = source.video[0]
        if rules.video.upscale_warning and (video.width < rules.video.width
                                           or video.height < rules.video.height):
            report["warnings"].append("Source resolution is below the canvas; upscaling "
                                       "does not add detail.")
        if not video.color.is_hdr and any(getattr(video.color, key) == "unknown"
                                         for key in ("space", "primaries", "transfer")):
            report["warnings"].append(
                "Untagged SDR is interpreted as Rec.709; verify source color.")
        cache_key = hashlib.sha256(json.dumps({
            "source": source_hash, "audio": audio_index, "duration": duration,
            "trim_start": rules.scenes.trim_start_sec,
            "loudnorm": rules.audio.loudnorm.model_dump(), "channels": 2, "version": __version__,
        }, sort_keys=True).encode()).hexdigest()
        measurement, audio_state = measure_audio(plan, rules, duration,
                                                 root / "cache" / f"{cache_key}.json", token)
        report["audio_normalization"] = {"status": audio_state, "passes": 2,
                                          "measurement": json.loads(measurement.model_dump_json())
                                          if measurement is not None else None}
        if audio_state == "silent" and rules.audio.loudnorm.skip_if_silent:
            raw = plan.profile.model_dump()
            raw["transforms"] = [t for t in raw["transforms"] if t["id"] != "audio.loudnorm"]
            plan = create_plan(source, Profile.model_validate(raw))
        report["native_profile"] = plan.profile.model_dump(mode="json")
        report["plan_hash"] = plan.plan_hash
        temporary_output = work / "output.tmp.mp4"
        layers: list[tuple[Path, float, float | None]] = []
        args = compose_command(plan, rules, temporary_output, duration, fps, measurement, layers)
        report["execution_argv"] = args
        report["video_encode_passes"] = 1
        status("processing", 0.10)

        def progress(event: RunEvent) -> None:
            if event.kind == "progress":
                try:
                    seconds = float(str(event.payload.get("out_time_us", 0))) / 1_000_000
                except ValueError:
                    return
                status("processing", 0.10 + 0.72 * min(1.0, max(0.0, seconds / duration)))

        report["encode_attempts"] = 0
        for attempt in range(rules.worker.max_retries + 1):
            report["encode_attempts"] = attempt + 1
            try:
                execute(args, work / f"encode-{attempt}.log", token,
                        timeout=rules.worker.wall_timeout_sec, on_event=progress)
                break
            except ReelsError as encoding_error:
                if not encoding_error.retryable or attempt == rules.worker.max_retries:
                    raise
                temporary_output.unlink(missing_ok=True)
                report["warnings"].append(f"Retrying failed encode, attempt {attempt + 2}.")
                token.wait(0.25 * (2 ** attempt))
                check_cancel(token)
        status("qa", 0.84)
        output = probe(temporary_output)
        output_details = stream_details(temporary_output, work, token)
        quality = inspect_delivery(temporary_output, output, output_details, rules, duration,
                                   fps, token, audio_expected=bool(source.audio),
                                   normalization_expected=audio_state == "measured")
        report["quality_check"] = quality
        if quality["failures"] and rules.quality_gate.enabled:
            raise ReelsError("quality_failed",
                             "Delivery QA failed: " + ", ".join(quality["failures"]))
        check_cancel(token)
        report["output"] = output.model_dump(mode="json", exclude={"path"})
        report["output"].update(filename="output.mp4", sha256=content_hash(temporary_output, token))
        report["elapsed_sec"] = time.monotonic() - started
        report["status"] = "success"
        report["ffmpeg_version"] = execute([ffmpeg_bin(), "-version"], work / "version.log",
                                            token, timeout=10, progress=False).splitlines()[0]
        os.replace(temporary_output, work / "output.mp4")
        atomic_json(work / "report.json", report)
        final.parent.mkdir(parents=True, exist_ok=True)
        check_cancel(token)
        os.replace(work, final)
        status("success", 1.0)
        return final
    except Exception as exc:
        error = exc if isinstance(exc, ReelsError) else ReelsError("processing_failed", str(exc))
        if token.is_cancelled():
            error = ReelsError("cancelled", "Task cancelled by the user.")
        report.update(status="cancelled" if error.code == "cancelled" else "failed",
                      error={"code": error.code, "message": str(error),
                             "retryable": error.retryable},
                      elapsed_sec=time.monotonic() - started)
        atomic_json(root / "failures" / f"{job_id}.json", report)
        if not rules.worker.temp_keep_on_failure:
            shutil.rmtree(work, ignore_errors=True)
        raise error from exc
    finally:
        if lease is not None:
            lease.release()
