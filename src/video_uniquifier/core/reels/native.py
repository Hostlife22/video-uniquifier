"""Version-pinned adapter to the existing 2.1.2 full-file filter graph.

Only this module composes engine labels/argv. No native Profile/RunOptions fields
or transform registry contracts are changed by the business delivery options.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from video_uniquifier.core import EncoderCandidate, Plan, Profile, SourceMeta, compute_plan_hash
from video_uniquifier.core.pipeline import FilterGraph
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.runtime import atomic_json, check_cancel
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.transforms import get
from video_uniquifier.core.transforms.audio_loudnorm import (
    LoudnormMeasurement,
    LoudnormParams,
    measure,
)


def derive_profile(base: Profile, rules: ReelsRules, source: SourceMeta) -> Profile:
    """Derive only native schema fields, without introducing editorial transforms."""
    raw = base.model_dump(mode="python")
    transforms: list[dict[str, Any]] = []
    video = source.video[0]
    vertical = abs(video.width / video.height - 9 / 16) < 0.01
    mode = "pad_black" if vertical else {
        "fit": "pad_black", "pad_blur": "pad_blur", "crop": "crop",
    }[rules.video.geometry.nonvertical_source]
    if video.color.is_hdr and rules.video.hdr_policy == "tonemap_sdr":
        transforms.append({"id": "video.tonemap_sdr", "params": {}})
    transforms.append({"id": "video.fit_aspect", "params": {
        "target_aspect": "9:16", "mode": mode, "target_width": rules.video.width,
        "target_height": rules.video.height, "allow_upscale": True,
        "blur_sigma": rules.video.geometry.blur_sigma,
    }})
    ln = rules.audio.loudnorm
    if source.audio and rules.audio.enabled and ln.enabled:
        transforms.append({"id": "audio.loudnorm", "params": {
            "integrated": ln.integrated_lufs, "true_peak": ln.true_peak_dbtp, "lra": ln.lra,
        }})
    raw.update(transforms=transforms, audio_tracks="first", keep_hdr=False,
               output_container="mp4", target_codec="h264", target_loudness_lufs=ln.integrated_lufs,
               seed_strategy="fixed", seed=42, segmentation={"mode": "keyframe"})
    selected = next((audio for audio in source.audio if audio.is_default), None)
    if selected is not None:
        raw["audio_tracks"] = [selected.index]
    return Profile.model_validate(raw)


def validate_native_profile(path: Path) -> Profile:
    """Validate both the native outer schema and each registered transform's params."""
    profile = load_profile(path)
    if profile.target_codec != "h264" or profile.output_container != "mp4" or profile.keep_hdr:
        raise ValueError("Reels base profile must declare H.264 MP4 SDR delivery")
    allowed = {"video.fit_aspect", "audio.loudnorm"}
    if {transform.id for transform in profile.transforms} != allowed:
        raise ValueError("Reels base profile must contain only fit_aspect and loudnorm")
    if len(profile.transforms) != 2 or any(not t.enabled for t in profile.transforms):
        raise ValueError("Reels base transforms must each be enabled exactly once")
    for transform in profile.transforms:
        spec = get(transform.id)
        spec.schema.model_validate({**spec.defaults, **transform.params})
    return profile


def default_profile_path() -> Path:
    packaged = Path(__file__).with_name("facebook_reels_base.yaml")
    return packaged if packaged.is_file() else (
        Path(__file__).parents[4] / "custom_profiles" / "facebook_reels_base.yaml"
    )


def create_plan(source: SourceMeta, profile: Profile) -> Plan:
    """Select the explicit software codec; engine preflight verifies capabilities."""
    encoder = EncoderCandidate(name="libx264", vendor="x264", codec="h264", works=True,
                               max_parallel=2)
    return Plan(source=source, profile=profile, encoder=encoder,
                plan_hash=compute_plan_hash(source, profile, encoder), run_seed=42)


def audio_prefilter(plan: Plan, rules: ReelsRules, duration: float) -> str:
    start = rules.scenes.trim_start_sec
    selected = plan.profile.audio_tracks
    index = selected[0] if isinstance(selected, list) else plan.source.audio[0].index
    return (f"[0:{index}]atrim=start={start:.9f}:end={start + duration:.9f},"
            f"asetpts=PTS-{start:.9f}/TB,"
            "aresample=48000:async=1:first_pts=0,aformat=channel_layouts=stereo,"
            f"apad=whole_dur={duration:.9f},atrim=duration={duration:.9f}[reels_audio]")


def measure_audio(
    plan: Plan, rules: ReelsRules, duration: float, cache: Path, token: CancelToken,
) -> tuple[LoudnormMeasurement | None, str]:
    if not plan.source.audio:
        return None, "missing"
    if not rules.audio.enabled or not rules.audio.loudnorm.enabled:
        return None, "disabled"
    check_cancel(token)
    params = LoudnormParams(integrated=rules.audio.loudnorm.integrated_lufs,
                            true_peak=rules.audio.loudnorm.true_peak_dbtp,
                            lra=rules.audio.loudnorm.lra)
    try:
        cached = json.loads(cache.read_text(encoding="utf-8"))
        result = LoudnormMeasurement.model_validate(cached)
    except (FileNotFoundError, ValueError, TypeError):
        result = measure(plan.source.path, params, pre_filter_complex=audio_prefilter(
            plan, rules, duration), pre_output_label="reels_audio", cancel_token=token)
        if all(math.isfinite(value) for value in result.model_dump().values()):
            atomic_json(cache, result.model_dump())
    check_cancel(token)
    if result.input_i == -math.inf and result.input_tp == -math.inf:
        return result, "silent"
    if not math.isfinite(result.input_i):
        return result, "unmeasurable_short_audio"
    return result, "measured"


def compose_command(
    plan: Plan, rules: ReelsRules, destination: Path, duration: float, fps: str,
    measurement: LoudnormMeasurement | None,
    layers: list[tuple[Path, float, float | None]],
) -> list[str]:
    """Fuse trim, native fit/loudnorm, delivery and optional RGBA layers in one encode."""
    built = FilterGraph(plan, destination, loudnorm_measurement=measurement).build()
    start = rules.scenes.trim_start_sec
    graph = built.filter_complex
    # Native graph labels refer to relative track ids. Prefix only the matching
    # input node; generated transform labels never contain a colon.
    graph = graph.replace("[0:v:0]", "[reels_video]")
    prefix = (f"[0:v:0]trim=start={start:.9f}:end={start + duration:.9f},"
              f"setpts=PTS-{start:.9f}/TB[reels_video]")
    if plan.source.audio:
        selected = plan.profile.audio_tracks
        absolute = selected[0] if isinstance(selected, list) else plan.source.audio[0].index
        relative = next(i for i, stream in enumerate(plan.source.audio) if stream.index == absolute)
        graph = graph.replace(f"[0:a:{relative}]", "[reels_audio]")
        prefix += ";" + audio_prefilter(plan, rules, duration)
    graph = prefix + ";" + graph
    vlabel = built.output_video_label
    # Convert, rather than merely relabel, known non-709 SDR. Untagged SDR uses
    # the explicitly recorded BT.709 assumption. HDR uses the native tonemap.
    color = plan.source.video[0].color
    if not color.is_hdr:
        input_color = color.space if color.space in {"bt709", "smpte170m", "bt470bg"} else "bt709"
        graph += f";[{vlabel}]colorspace=iall={input_color}:all=bt709:range=tv[reels_color]"
        vlabel = "reels_color"
    inputs: list[str] = []
    for index, (path, begin, end) in enumerate(layers, start=1):
        inputs += ["-loop", "1", "-i", str(path)]
        enable = f"gte(t,{begin:.6f})" if end is None else f"between(t,{begin:.6f},{end:.6f})"
        graph += (f";[{vlabel}][{index}:v:0]overlay=0:0:shortest=1:"
                  f"enable='{enable}'[reels_layer_{index}]")
        vlabel = f"reels_layer_{index}"
    graph += f";[{vlabel}]setsar=1,format=yuv420p[reels_out]"
    args = built.args[:-1]
    graph_index = args.index("-filter_complex")
    args[graph_index:graph_index] = inputs
    args[args.index("-filter_complex") + 1] = graph
    args[args.index("-map") + 1] = "[reels_out]"
    if plan.source.audio and built.output_audio_label is not None:
        for index, value in enumerate(args[:-1]):
            if value == "-map" and args[index + 1] == built.output_audio_label:
                args[index + 1] = "[reels_audio]"
    threads = rules.worker.ffmpeg_threads
    if threads == "auto":
        threads = max(1, min(8, (os.cpu_count() or 2) // rules.worker.max_cpu_jobs))
    args += ["-crf", str(rules.video.crf), "-preset", rules.video.preset,
             "-threads", str(threads), "-filter_complex_threads", str(threads),
             "-r", fps, "-fps_mode", "cfr", "-pix_fmt", "yuv420p",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             "-color_range", "tv", "-t", f"{duration:.9f}"]
    if plan.source.audio:
        args += ["-c:a:0", "aac", "-profile:a:0", "aac_low", "-ar:a:0", "48000",
                 "-ac:a:0", "2", "-b:a:0", "128k"]
    args += ["-movflags", "+faststart" if rules.video.faststart else "0", str(destination)]
    return args
