"""Unit tests for calibration.intensity.scale_profile."""

from __future__ import annotations

import pytest

from video_uniquifier.core.calibration.intensity import _around_one, scale_profile
from video_uniquifier.core.models import Profile, TransformConfig


def _profile(transforms: list[TransformConfig]) -> Profile:
    return Profile(name="t", transforms=transforms)


def _get(p: Profile, transform_id: str) -> dict:
    for tc in p.transforms:
        if tc.id == transform_id:
            # Recover the *effective* params (merge defaults).
            from video_uniquifier.core.transforms import get
            spec = get(transform_id)
            return {**spec.defaults, **tc.params}
    raise KeyError(transform_id)


def test_around_one_helper() -> None:
    assert _around_one(1.0, 2.0) == 1.0
    assert _around_one(1.02, 2.0) == pytest.approx(1.04)
    assert _around_one(0.99, 2.0) == pytest.approx(0.98)
    assert _around_one(1.05, 0.5) == pytest.approx(1.025)


def test_scale_crop_resize() -> None:
    p = _profile([TransformConfig(id="video.crop_resize",
                                  params={"max_strength": 0.04})])
    out = scale_profile(p, 2.0)
    assert _get(out, "video.crop_resize")["max_strength"] == pytest.approx(0.08)


def test_scale_color_eq_brightness_and_around_one() -> None:
    p = _profile([TransformConfig(id="video.color_eq",
                                  params={
                                      "brightness": 0.01, "contrast": 1.02,
                                      "gamma": 0.99, "saturation": 1.03,
                                  })])
    out = scale_profile(p, 2.0)
    e = _get(out, "video.color_eq")
    assert e["brightness"] == pytest.approx(0.02)         # *factor
    assert e["contrast"] == pytest.approx(1.04)            # around-1
    assert e["gamma"] == pytest.approx(0.98)               # around-1
    assert e["saturation"] == pytest.approx(1.06)          # around-1


def test_scale_noise_strength_is_int() -> None:
    p = _profile([TransformConfig(id="video.noise", params={"strength": 4})])
    out = scale_profile(p, 1.75)
    assert _get(out, "video.noise")["strength"] == 7


def test_scale_pitch_tempo() -> None:
    p = _profile([TransformConfig(id="audio.pitch_tempo",
                                  params={
                                      "pitch": 1.012, "tempo": 1.0,
                                      "randomize_within": 0.003,
                                  })])
    out = scale_profile(p, 2.0)
    e = _get(out, "audio.pitch_tempo")
    assert e["pitch"] == pytest.approx(1.024)              # around-1
    assert e["tempo"] == pytest.approx(1.0)                # 1 stays 1
    assert e["randomize_within"] == pytest.approx(0.006)   # *factor


def test_scale_audio_eq_band_gain_only() -> None:
    p = _profile([TransformConfig(id="audio.eq",
                                  params={"bands": [[120.0, -0.6], [4500.0, 0.4]]})])
    out = scale_profile(p, 2.0)
    bands = _get(out, "audio.eq")["bands"]
    assert bands[0][0] == 120.0  # freq unchanged
    assert bands[0][1] == pytest.approx(-1.2)
    assert bands[1][1] == pytest.approx(0.8)


def test_scale_resample_delta_from_target() -> None:
    p = _profile([TransformConfig(id="audio.resample",
                                  params={"intermediate_sr": 47999, "target_sr": 48000})])
    out = scale_profile(p, 3.0)
    # delta -1, * 3 → -3 → intermediate_sr 47997
    assert _get(out, "audio.resample")["intermediate_sr"] == 47997


def test_scale_spectral_smear_intensity() -> None:
    p = _profile([TransformConfig(id="audio.spectral_smear",
                                  params={"intensity": 0.02})])
    out = scale_profile(p, 2.5)
    assert _get(out, "audio.spectral_smear")["intensity"] == pytest.approx(0.05)


def test_scale_clamps_to_field_bounds() -> None:
    # max_strength has le=0.10
    p = _profile([TransformConfig(id="video.crop_resize",
                                  params={"max_strength": 0.06})])
    out = scale_profile(p, 5.0)   # 0.30 → clamp 0.10
    assert _get(out, "video.crop_resize")["max_strength"] == pytest.approx(0.10)


def test_scale_factor_one_is_identity() -> None:
    p = _profile([
        TransformConfig(id="video.crop_resize", params={"max_strength": 0.04}),
        TransformConfig(id="audio.pitch_tempo", params={"pitch": 1.012}),
        TransformConfig(id="audio.eq", params={"bands": [[120.0, -0.6]]}),
    ])
    out = scale_profile(p, 1.0)
    assert _get(out, "video.crop_resize")["max_strength"] == pytest.approx(0.04)
    assert _get(out, "audio.pitch_tempo")["pitch"] == pytest.approx(1.012)
    assert _get(out, "audio.eq")["bands"][0][1] == pytest.approx(-0.6)


def test_scale_loudnorm_unchanged() -> None:
    p = _profile([TransformConfig(id="audio.loudnorm")])
    out = scale_profile(p, 5.0)
    e = _get(out, "audio.loudnorm")
    assert e["integrated"] == -14.0  # target loudness doesn't scale


# ---------------------------------------------------------------------------
# Regression tests use current transform schemas.
# ---------------------------------------------------------------------------


def test_scale_rotate_degrees() -> None:
    p = _profile([TransformConfig(id="video.rotate", params={"degrees": 0.3})])
    out = scale_profile(p, 1.5)
    assert _get(out, "video.rotate")["degrees"] == pytest.approx(0.45)


def test_scale_speed_rate_around_one() -> None:
    p = _profile([TransformConfig(id="video.speed", params={"rate": 1.02})])
    out = scale_profile(p, 2.0)
    assert _get(out, "video.speed")["rate"] == pytest.approx(1.04)


def test_scale_blend_b_opacity_times_factor() -> None:
    p = _profile([TransformConfig(id="video.blend_b", params={"opacity": 0.04})])
    out = scale_profile(p, 2.0)
    assert _get(out, "video.blend_b")["opacity"] == pytest.approx(0.08)


def test_scale_mirror_passes_through_unchanged() -> None:
    p = _profile([TransformConfig(id="video.mirror")])
    out = scale_profile(p, 5.0)
    # Mirror has no intensity knob, so the produced config carries only the
    # explicit `enabled` flag and no params — calling _get checks that the
    # default merge still yields an empty dict.
    assert _get(out, "video.mirror") == {}


def test_scale_haas_stereo_delay_ms() -> None:
    p = _profile([TransformConfig(id="audio.haas_stereo", params={"delay_ms": 10.0})])
    out = scale_profile(p, 1.5)
    assert _get(out, "audio.haas_stereo")["delay_ms"] == pytest.approx(15.0)


def test_scale_compand_ratio_toward_one() -> None:
    p = _profile([TransformConfig(id="audio.compand", params={"ratio": 3.0})])
    assert _get(scale_profile(p, 0.5), "audio.compand")["ratio"] == pytest.approx(2.0)


def test_scale_reverb_intensity() -> None:
    p = _profile([TransformConfig(id="audio.reverb", params={"intensity": 0.1})])
    assert _get(scale_profile(p, 2.0), "audio.reverb")["intensity"] == pytest.approx(0.2)


def test_scale_noise_overlay_linear_amplitude() -> None:
    p = _profile([TransformConfig(id="audio.noise_overlay", params={"noise_db": -20.0})])
    assert _get(scale_profile(p, 2.0), "audio.noise_overlay")["noise_db"] == pytest.approx(-13.9794)


def test_scale_subpixel_sharpen_odd_integer_kernel() -> None:
    p = _profile([TransformConfig(id="video.subpixel_sharpen", params={"radius": 5})])
    assert _get(scale_profile(p, 0.75), "video.subpixel_sharpen")["radius"] == 3
    assert _get(scale_profile(p, 1.5), "video.subpixel_sharpen")["radius"] == 7


def test_scale_temporal_jitter_probabilities() -> None:
    p = _profile([TransformConfig(id="video.temporal_jitter", params={"drop_prob": 0.05})])
    assert _get(scale_profile(p, 2.0), "video.temporal_jitter")["drop_prob"] == pytest.approx(0.1)


def test_scale_tonemap_sdr_is_pass_through() -> None:
    # Tonemap intensity does not scale; the profile must round-trip without
    # numeric changes (algorithm + peak + desat remain at defaults).
    p = _profile([TransformConfig(id="video.tonemap_sdr")])
    out = scale_profile(p, 5.0)
    e = _get(out, "video.tonemap_sdr")
    assert e["algorithm"] == "hable"
    assert e["peak"] == pytest.approx(1000.0)
    assert e["desat"] == pytest.approx(0.0)


def test_scale_clamp_skips_unknown_field_names() -> None:
    # User-provided params that aren't in the transform schema must still
    # round-trip (the schema-clamp loop skips them); the scaling rule
    # itself decides whether to touch the value.
    p = _profile([TransformConfig(id="video.crop_resize",
                                  params={"max_strength": 0.04,
                                          "legacy_extra": 1.0})])
    out = scale_profile(p, 2.0)
    e = _get(out, "video.crop_resize")
    assert e["max_strength"] == pytest.approx(0.08)
    assert e["legacy_extra"] == pytest.approx(1.0)  # untouched by scaling/clamp


def test_scale_clamps_blend_b_opacity_to_upper_bound() -> None:
    # video.blend_b.opacity has le=0.20 in the schema; aggressive scaling
    # must clamp into bounds rather than producing a value the pipeline
    # would later reject at validation time.
    p = _profile([TransformConfig(id="video.blend_b",
                                  params={"opacity": 0.15})])
    out = scale_profile(p, 5.0)
    # 0.15 * 5 = 0.75 → clamped to 0.20
    assert _get(out, "video.blend_b")["opacity"] <= 0.20 + 1e-9
