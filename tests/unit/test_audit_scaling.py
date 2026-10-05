"""Regression checks using the actual shipped profiles and transform schemas."""

from pathlib import Path

import pytest

from video_uniquifier.core.calibration.intensity import scale_profile
from video_uniquifier.core.models import Profile, TransformConfig
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.core.transforms import get

PROFILES = Path(__file__).parents[2] / "src/video_uniquifier/profiles"


@pytest.mark.parametrize("path", sorted(PROFILES.glob("*.yaml")), ids=lambda p: p.stem)
@pytest.mark.parametrize("factor", [0.25, 0.7, 0.75, 1.0, 1.5, 4.0])
def test_shipped_scaled_candidates_validate(path: Path, factor: float) -> None:
    original = load_profile(path)
    candidate = scale_profile(original, factor)
    for tc in candidate.transforms:
        if tc.enabled:
            spec = get(tc.id)
            spec.schema.model_validate({**spec.defaults, **tc.params})
    assert original == load_profile(path)


@pytest.mark.parametrize(
    "identifier,params,key,values",
    [
        ("video.subpixel_sharpen", {"luma_amount": 0.05}, "luma_amount", [.0125, .05, .2]),
        ("video.temporal_jitter", {"blackout_prob": .04}, "blackout_prob", [.01, .04, .16]),
        ("audio.compand", {"ratio": 3.0}, "ratio", [1.5, 3.0, 9.0]),
        ("audio.reverb", {"intensity": .10}, "intensity", [.025, .10, .4]),
        ("audio.eq", {"jitter_db": 1.0}, "jitter_db", [.25, 1.0, 4.0]),
        ("audio.haas_stereo", {"randomize_within_ms": 2.0}, "randomize_within_ms", [.5, 2., 8.]),
        ("audio.noise_overlay", {"noise_db": -12.0}, "noise_db", [-24.0412, -12., -3.]),
    ],
)
def test_actual_intensity_parameters(identifier, params, key, values) -> None:
    profile = Profile(name="regression", transforms=[TransformConfig(id=identifier, params=params)])
    for factor, expected in zip([.25, 1., 4.], values, strict=True):
        tc = scale_profile(profile, factor).transforms[0]
        assert tc.params[key] == pytest.approx(expected, abs=1e-4)


def test_disabled_effect_remains_unchanged() -> None:
    tc = TransformConfig(id="video.subpixel_sharpen", enabled=False, params={"radius": 5})
    profile = Profile(name="disabled", transforms=[tc])
    assert scale_profile(profile, .7).transforms[0] == tc


@pytest.mark.parametrize("factor", [-1.0, float("nan"), float("inf")])
def test_invalid_factors_rejected(factor: float) -> None:
    with pytest.raises(ValueError, match="factor"):
        scale_profile(Profile(name="invalid"), factor)
