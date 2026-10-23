"""Strict business configuration. Never pass this document to load_profile()."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RulesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True,
                              allow_inf_nan=False)


def asset_path(value: str | None) -> str | None:
    if value is not None and (
        not value or PurePosixPath(value).is_absolute()
        or any(part == ".." for part in value.split("/"))
        or any(char in value for char in ("\\", ":", "\x00", "\n", "\r"))
    ):
        raise ValueError("asset must be a relative path inside the configured asset root")
    return value


class PublishRules(RulesModel):
    platform: Literal["facebook"] = "facebook"
    surface: Literal["reels"] = "reels"
    channel: Literal["organic"] = "organic"
    posting_method: Literal["manual_app", "api"] = "manual_app"


class GeometryRules(RulesModel):
    vertical_source: Literal["fit"] = "fit"
    nonvertical_source: Literal["pad_blur", "fit", "crop"] = "pad_blur"
    allow_center_crop: bool = False
    blur_sigma: float = Field(default=20.0, gt=0, le=80)

    @model_validator(mode="after")
    def manual_crop_only(self) -> GeometryRules:
        if self.nonvertical_source == "crop" and not self.allow_center_crop:
            raise ValueError("crop requires allow_center_crop=true")
        return self


class VideoRules(RulesModel):
    width: Literal[720, 1080] = 1080
    height: Literal[1280, 1920] = 1920
    aspect_ratio: Literal["9:16"] = "9:16"
    pixel_format: Literal["yuv420p"] = "yuv420p"
    codec: Literal["libx264"] = "libx264"
    crf: int = Field(default=21, ge=18, le=23)
    preset: Literal["veryfast", "medium"] = "veryfast"
    fps_mode: Literal["auto", "cfr30"] = "auto"
    fallback_fps: Literal[30] = 30
    faststart: bool = True
    upscale_warning: bool = True
    hdr_policy: Literal["fail_with_advice", "tonemap_sdr"] = "fail_with_advice"
    geometry: GeometryRules = Field(default_factory=GeometryRules)

    @model_validator(mode="after")
    def vertical_canvas(self) -> VideoRules:
        if self.width * 16 != self.height * 9:
            raise ValueError("canvas must be 1080x1920 or 720x1280")
        return self


class LogoRules(RulesModel):
    enabled: bool = False
    source: str | None = None
    anchor: Literal["top_right", "top_left", "bottom_right", "bottom_left"] = "top_right"
    width_px: int = Field(default=120, ge=8, le=1080)
    margin_x_px: int = Field(default=65, ge=0, le=1920)
    margin_y_px: int = Field(default=300, ge=0, le=1920)
    opacity: float = Field(default=0.9, gt=0, le=1)

    _source_path = field_validator("source")(asset_path)


class TitleRules(RulesModel):
    enabled: bool = False
    text: str | None = Field(default=None, max_length=500)
    font_path: str | None = None
    font_size_px: int = Field(default=54, ge=12, le=160)
    color: str = "#FFFFFF"
    outline_px: int = Field(default=3, ge=0, le=10)
    max_lines: int = Field(default=2, ge=1, le=4)
    position: Literal["top_safe", "center_safe", "bottom_safe"] = "top_safe"
    start_sec: float = Field(default=0.0, ge=0)
    end_sec: float | None = Field(default=None, gt=0)

    _font_path = field_validator("font_path")(asset_path)

    @field_validator("color")
    @classmethod
    def hex_color(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("color must be #RRGGBB")
        return value

    @model_validator(mode="after")
    def title_inputs(self) -> TitleRules:
        if self.enabled and (not self.text or not self.text.strip() or not self.font_path):
            raise ValueError("enabled title requires human-provided text and font_path")
        if self.text and any(ord(char) < 32 and char != "\n" for char in self.text):
            raise ValueError("title contains unsupported control characters")
        if self.end_sec is not None and self.end_sec <= self.start_sec:
            raise ValueError("title end_sec must exceed start_sec")
        return self


class SafeAreaRules(RulesModel):
    left_fraction: float = Field(default=0.06, ge=0, lt=0.5)
    right_fraction: float = Field(default=0.06, ge=0, lt=0.5)
    top_fraction: float = Field(default=0.14, ge=0, lt=0.5)
    bottom_fraction: float = Field(default=0.30, ge=0, lt=0.5)


class SubtitleZone(RulesModel):
    bottom_fraction: float = Field(default=0.30, ge=0, lt=0.75)


class PackagingRules(RulesModel):
    enabled: bool = False
    template_id: str = Field(default="reels_default_v1", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    cover_insert_enabled: Literal[False] = False
    watermark_removal: Literal[False] = False
    logo: LogoRules = Field(default_factory=LogoRules)
    title: TitleRules = Field(default_factory=TitleRules)
    safe_area: SafeAreaRules = Field(default_factory=SafeAreaRules)
    safe_area_preview_enabled: bool = True
    protect_existing_hard_subtitles: bool = True
    subtitle_zone: SubtitleZone = Field(default_factory=SubtitleZone)

    @model_validator(mode="after")
    def enabled_assets(self) -> PackagingRules:
        if self.logo.enabled and not self.logo.source:
            raise ValueError("enabled logo requires a local source")
        if not self.enabled and (self.logo.enabled or self.title.enabled):
            raise ValueError("enable packaging explicitly before enabling title or logo")
        return self


class LoudnessRules(RulesModel):
    enabled: bool = True
    passes: Literal[2] = 2
    integrated_lufs: float = Field(default=-16.0, ge=-30, le=-10)
    true_peak_dbtp: float = Field(default=-1.5, ge=-6, le=-1)
    lra: float = Field(default=11.0, ge=1, le=20)
    skip_if_silent: bool = True


class AudioRules(RulesModel):
    enabled: bool = True
    codec: Literal["aac"] = "aac"
    bitrate: Literal["128k"] = "128k"
    sample_rate: Literal[48000] = 48000
    channels: Literal[2] = 2
    loudnorm: LoudnessRules = Field(default_factory=LoudnessRules)
    change_pitch: Literal[False] = False
    change_tempo: Literal[False] = False
    add_noise: Literal[False] = False
    missing_audio: Literal["silent_video_ok"] = "silent_video_ok"
    max_av_drift_ms: int = Field(default=100, ge=1, le=500)


class SceneRules(RulesModel):
    detect_enabled: bool = True
    detector: Literal["pyscenedetect_content"] = "pyscenedetect_content"
    threshold: float = Field(default=27.0, gt=0, le=255)
    min_scene_length_sec: float = Field(default=2.0, gt=0, le=3600)
    preserve_original_order: Literal[True] = True
    auto_reorder: Literal[False] = False
    auto_drop_scenes: Literal[False] = False
    trim_start_sec: float = Field(default=0.0, ge=0)
    trim_end_sec: float = Field(default=0.0, ge=0)
    auto_insert_transitions: Literal[False] = False
    blackdetect_enabled: bool = True
    blackdetect_report_only: Literal[True] = True
    silence_detect_enabled: bool = True
    silence_detect_report_only: Literal[True] = True


class QualityRules(RulesModel):
    enabled: bool = True
    require_video_stream: Literal[True] = True
    expected_aspect_tolerance: float = Field(default=0.01, gt=0, le=0.05)
    max_duration_delta_sec: float = Field(default=0.5, gt=0, le=0.5)
    max_av_drift_ms: int = Field(default=100, ge=1, le=500)
    require_video_decode_check: bool = True
    sample_preview_seconds: int = Field(default=10, ge=1, le=180)
    compare_against_source: bool = True
    no_external_platform_detection_claims: Literal[True] = True


def _default_extensions() -> list[Literal["mp4", "mov", "mkv", "webm"]]:
    return ["mp4", "mov", "mkv"]


class WorkerRules(RulesModel):
    ffmpeg_threads: Literal["auto"] | Annotated[int, Field(ge=1, le=32)] = "auto"
    max_cpu_jobs: int = Field(default=2, ge=1, le=2)
    max_retries: int = Field(default=1, ge=0, le=3)
    temp_keep_on_failure: bool = False
    atomic_output: Literal[True] = True
    allow_input_extensions: list[Literal["mp4", "mov", "mkv", "webm"]] = Field(
        default_factory=_default_extensions, min_length=1,
    )
    max_input_mb: int = Field(default=2048, ge=1, le=8192)
    max_duration_sec: float = Field(default=7200.0, gt=0, le=14400)
    max_pixels: int = Field(default=8_847_360, ge=4096, le=33_177_600)
    wall_timeout_sec: int = Field(default=14400, ge=1, le=86400)


class ReelsRules(RulesModel):
    schema_version: Literal[1] = 1
    preset_id: str = Field(default="facebook_reels_drama_v1", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    publish: PublishRules = Field(default_factory=PublishRules)
    video: VideoRules = Field(default_factory=VideoRules)
    packaging: PackagingRules = Field(default_factory=PackagingRules)
    audio: AudioRules = Field(default_factory=AudioRules)
    scenes: SceneRules = Field(default_factory=SceneRules)
    quality_gate: QualityRules = Field(default_factory=QualityRules)
    worker: WorkerRules = Field(default_factory=WorkerRules)


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys rather than silently changing operator intent."""


def _unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError("YAML keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_rules(path: Path) -> ReelsRules:
    """Load bounded, local YAML and reject unknown fields, aliases and duplicate keys."""
    if path.stat().st_size > 256 * 1024:
        raise ValueError("business YAML exceeds 256 KiB")
    text = path.read_text(encoding="utf-8")
    if any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken)) for token in yaml.scan(text)):
        raise ValueError("YAML anchors and aliases are not supported")
    return ReelsRules.model_validate(yaml.load(text, Loader=UniqueKeyLoader))


def resolve_asset(root: Path, relative: str) -> Path:
    """Confine assets, including symlinks, to a trusted root."""
    asset_path(relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("asset does not exist inside the configured asset root")
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("asset exceeds 32 MiB")
    return path
