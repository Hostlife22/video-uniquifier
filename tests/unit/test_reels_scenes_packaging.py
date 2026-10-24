from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.packaging import render_layers, safe_box
from video_uniquifier.core.reels.runtime import ReelsError
from video_uniquifier.core.reels.scenes import build_timeline, detect_timeline
from video_uniquifier.core.runner import CancelToken


@pytest.fixture
def assets(tmp_path):
    Image.new("RGBA", (100, 60), (240, 40, 20, 255)).save(tmp_path / "logo.png")
    # A test font is provided by Pillow's own installed wheel on some hosts;
    # otherwise use an existing OS font without downloading licensed assets.
    candidates = [Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("C:/Windows/Fonts/arial.ttf")]
    font = next((path for path in candidates if path.is_file()), None)
    if font is not None:
        shutil.copyfile(font, tmp_path / "font.ttf")
    return tmp_path


def test_scene_timeline_filters_short_cuts_and_maps_trim_without_reordering():
    timeline = build_timeline([6.0, 2.0, 2.0, -1.0, 2.5, 11.0, 9.5], 10, 2, 1, 2)
    source, output = timeline["source_timeline"], timeline["output_timeline"]
    assert [scene["start_sec"] for scene in source] == [0, 2, 6]
    assert [scene["scene_id"] for scene in output] == [1, 2, 3]
    assert output[0]["source_start_sec"] == 1
    assert output[0]["start_sec"] == 0
    assert output[-1]["end_sec"] == 7
    assert sum(scene["duration_sec"] for scene in output) == 7


def test_scene_missing_dependency_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setattr("importlib.util.find_spec", lambda _: None)
    with pytest.raises(ReelsError, match=r"\[scene\]") as caught:
        detect_timeline(tmp_path / "x.mp4", 10, ReelsRules(), tmp_path, CancelToken())
    assert caught.value.code == "scene_dependency"


def test_packaging_is_off_and_internal_safe_area_is_explicit(tmp_path):
    rules = ReelsRules()
    assert render_layers(rules, tmp_path, tmp_path, 10, CancelToken()) == ([], [], [])
    assert safe_box(rules) == (65, 269, 1015, 1344)


def test_logo_layer_has_alpha_and_does_not_cover_the_original_frame(assets):
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "logo": {
        "enabled": True, "source": "logo.png", "opacity": 0.5,
    }}})
    layers, metadata, warnings = render_layers(rules, assets, assets, 10, CancelToken())
    assert len(layers) == 1 and layers[0][1:] == (0.0, None)
    assert metadata[0]["box"] == (895, 300, 1015, 372)
    with Image.open(layers[0][0]) as image:
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((950, 330))[3] == 128
    assert any("heuristic" in warning for warning in warnings)


@pytest.mark.parametrize("options, expected_code", [
    ({"anchor": "bottom_right", "margin_y_px": 0}, "subtitle_zone_conflict"),
    ({"margin_x_px": 1900}, "packaging_bounds"),
])
def test_logo_conflicts_are_rejected_before_encoding(assets, options, expected_code):
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "logo": {
        "enabled": True, "source": "logo.png", **options,
    }}})
    with pytest.raises(ReelsError) as caught:
        render_layers(rules, assets, assets, 10, CancelToken())
    assert caught.value.code == expected_code


def test_tall_logo_is_rejected_before_allocating_a_resized_image(tmp_path, monkeypatch):
    Image.new("RGBA", (1, 4000), "red").save(tmp_path / "logo.png")
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "logo": {
        "enabled": True, "source": "logo.png", "width_px": 1080,
    }}})

    def unexpected_resize(*_args, **_kwargs):
        pytest.fail("out-of-bounds logo reached image resize")

    monkeypatch.setattr(Image.Image, "resize", unexpected_resize)
    with pytest.raises(ReelsError) as caught:
        render_layers(rules, tmp_path, tmp_path, 10, CancelToken())
    assert caught.value.code == "packaging_bounds"


def test_outside_safe_area_warns_when_it_does_not_obscure_subtitles(assets):
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "logo": {
        "enabled": True, "source": "logo.png", "margin_y_px": 0,
    }}})
    _, _, warnings = render_layers(rules, assets, assets, 10, CancelToken())
    assert any("outside" in warning for warning in warnings)


def test_title_special_characters_are_rasterized_and_timed(assets):
    if not (assets / "font.ttf").exists():
        pytest.skip("test requires an installed TrueType font")
    text = "短剧 100%: [A]; 'B'\\C"
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "title": {
        "enabled": True, "text": text, "font_path": "font.ttf", "font_size_px": 32,
        "start_sec": 1.0, "end_sec": 3.0,
    }}})
    layers, metadata, _ = render_layers(rules, assets, assets, 10, CancelToken())
    assert layers[0][1:] == (1.0, 3.0)
    assert metadata[0]["text"] == text
    with Image.open(layers[0][0]) as image:
        assert image.getchannel("A").getbbox() is not None


@pytest.mark.parametrize("text, start, expected", [("太长" * 100, 0.0, "title_lines"),
                                                 ("Title", 15.0, "title_timing")])
def test_title_overflow_and_non_effective_timing_are_rejected(assets, text, start, expected):
    if not (assets / "font.ttf").exists():
        pytest.skip("test requires an installed TrueType font")
    rules = ReelsRules.model_validate({"packaging": {"enabled": True, "title": {
        "enabled": True, "text": text, "font_path": "font.ttf", "start_sec": start,
    }}})
    with pytest.raises(ReelsError) as caught:
        render_layers(rules, assets, assets, 10, CancelToken())
    assert caught.value.code == expected
