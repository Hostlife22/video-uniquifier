from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from video_uniquifier.core.models import Profile
from video_uniquifier.core.reels.config import ReelsRules, load_rules, resolve_asset
from video_uniquifier.core.reels.native import default_profile_path, validate_native_profile


def test_native_profile_is_separate_and_transform_parameters_are_valid():
    profile = validate_native_profile(default_profile_path())
    assert profile.seed == 42
    assert profile.audio_tracks == "first"
    assert profile.transforms[0].params["mode"] == "pad_blur"
    with pytest.raises(ValidationError):
        Profile.model_validate(ReelsRules().model_dump())


@pytest.mark.parametrize("patch", [
    {"unknown": True}, {"schema_version": 2},
    {"video": {"crf": 17}}, {"video": {"crf": 24}},
    {"video": {"crf": "21"}}, {"video": {"crf": True}},
    {"video": {"width": 720}}, {"video": {"codec": "h264_nvenc"}},
    {"video": {"geometry": {"nonvertical_source": "crop"}}},
    {"audio": {"change_pitch": True}}, {"audio": {"change_tempo": True}},
    {"audio": {"add_noise": True}}, {"audio": {"loudnorm": {"passes": 1}}},
    {"packaging": {"cover_insert_enabled": True}},
    {"packaging": {"watermark_removal": True}},
    {"packaging": {"enabled": True, "title": {"enabled": True}}},
    {"packaging": {"logo": {"enabled": True}}},
    {"scenes": {"threshold": float("nan")}}, {"scenes": {"trim_start_sec": -1.0}},
    {"scenes": {"auto_reorder": True}}, {"scenes": {"auto_drop_scenes": True}},
    {"scenes": {"blackdetect_report_only": False}},
    {"worker": {"max_cpu_jobs": 3}}, {"worker": {"ffmpeg_threads": 0}},
    {"worker": {"atomic_output": False}},
    {"quality_gate": {"no_external_platform_detection_claims": False}},
    {"packaging": {"title": {"color": "red;movie=bad"}}},
    {"packaging": {"title": {"start_sec": 2.0, "end_sec": 1.0}}},
])
def test_business_config_rejects_unknown_unsafe_or_unsupported_options(patch):
    with pytest.raises(ValidationError):
        ReelsRules.model_validate(patch)


@pytest.mark.parametrize("path", ["../secret.png", "/etc/passwd", "C:/font.ttf", "a\\b.png",
                                  "a/../../x", "a\n.png"])
def test_assets_must_be_confined_relative_paths(path):
    with pytest.raises(ValidationError):
        ReelsRules.model_validate({"packaging": {"logo": {"source": path}}})


def test_asset_resolver_rejects_symlinks_outside_root(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("outside")
    (assets / "logo.png").symlink_to(secret)
    with pytest.raises(ValueError, match="asset"):
        resolve_asset(assets, "logo.png")
    inside = assets / "good.png"
    inside.write_bytes(b"png")
    assert resolve_asset(assets, "good.png") == inside


@pytest.mark.parametrize("text", ["video:\n  crf: 21\n  crf: 23\n", "video: &v {}\nother: *v\n",
                                  "!!python/object:os.system {}", "[]"])
def test_business_yaml_rejects_duplicate_alias_unsafe_tags_and_wrong_root(tmp_path, text):
    path = tmp_path / "rules.yaml"
    path.write_text(text)
    with pytest.raises((ValueError, yaml.YAMLError)):
        load_rules(path)


def test_rules_roundtrip_and_manual_crop_and_720_canvas(tmp_path):
    rules = ReelsRules.model_validate({"video": {"width": 720, "height": 1280, "geometry": {
        "nonvertical_source": "crop", "allow_center_crop": True,
    }}})
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(rules.model_dump(mode="json")))
    assert load_rules(path) == rules


def test_oversized_yaml_is_rejected_before_parsing(tmp_path):
    path = tmp_path / "huge.yaml"
    path.write_bytes(b" " * (256 * 1024 + 1))
    with pytest.raises(ValueError, match="256 KiB"):
        load_rules(path)


def test_shipped_business_example_and_editor_schema_stay_in_sync():
    examples = Path(__file__).parents[2] / "examples" / "facebook_reels"
    assert load_rules(examples / "reels_business_rules.yaml") == ReelsRules()
    assert json.loads((examples / "reels_business.schema.json").read_text()) == (
        ReelsRules.model_json_schema())


def test_default_base_profile_uses_installed_package_resources(tmp_path, monkeypatch):
    """The worker must use packaged profiles, even beside a source checkout."""
    from video_uniquifier.core.reels import native

    package = tmp_path / "installed" / "video_uniquifier"
    profile_dir = package / "profiles"
    profile_dir.mkdir(parents=True)
    source = native.default_profile_path().read_text()
    (profile_dir / "facebook_reels_base.yaml").write_text(
        source.replace("name: facebook_reels_base", "name: bundled_only"),
    )
    monkeypatch.setattr(native, "files", lambda _name: package, raising=False)
    loaded = native.validate_native_profile(native.default_profile_path())
    assert loaded.name == "bundled_only"
