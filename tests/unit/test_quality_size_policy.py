"""Budget selection never promotes missing metrics or wrong-domain evidence."""

from dataclasses import replace

import pytest

from video_uniquifier.core._quality_size_policy import (
    CandidateObservation,
    QualitySizeLimits,
    select_candidate,
)

REFERENCE = "a" * 64
LIMITS = QualitySizeLimits(REFERENCE, "vmaf", "plan_transformed_sdr", 95, 2000, 8000, 10)
GOOD = CandidateObservation("good", REFERENCE, "vmaf", "plan_transformed_sdr",
                            96, 1000, 2, 5, True)


def test_quality_then_bytes_then_stable_id_independent_of_input_order() -> None:
    best = replace(GOOD, candidate_id="best", quality=97)
    larger = replace(best, candidate_id="larger", size_bytes=1500)
    tied = replace(best, candidate_id="zzz")
    for candidates in ((GOOD, larger, tied, best), (best, tied, larger, GOOD)):
        result = select_candidate(candidates, LIMITS)
        assert result.selected_candidate_id == "best"
        assert result.human_acceptance == "NOT VERIFIED"


@pytest.mark.parametrize("changes,reason", [
    ({"quality": None}, "quality_unavailable_or_outside_units"),
    ({"quality": float("nan")}, "quality_unavailable_or_outside_units"),
    ({"quality": float("inf")}, "quality_unavailable_or_outside_units"),
    ({"quality": True}, "quality_unavailable_or_outside_units"),
    ({"quality": 101}, "quality_unavailable_or_outside_units"),
    ({"quality": 0}, "quality_below_limit"),
    ({"correctness_passed": False}, "correctness_not_passed"),
    ({"reference_sha256": "b" * 64}, "reference_or_metric_domain_mismatch"),
    ({"domain": "coded_hdr"}, "reference_or_metric_domain_mismatch"),
    ({"metric": "ssim"}, "reference_or_metric_domain_mismatch"),
    ({"size_bytes": 2100}, "size_exceeds_limit"),
    ({"duration_sec": 0.1}, "average_bitrate_exceeds_limit"),
    ({"duration_sec": float("nan")}, "size_or_duration_unavailable"),
    ({"size_bytes": 0}, "size_or_duration_unavailable"),
    ({"size_bytes": True}, "size_or_duration_unavailable"),
    ({"encode_wall_sec": 11}, "encode_wall_exceeds_limit"),
    ({"encode_wall_sec": None}, "encode_wall_unavailable"),
])
def test_infeasible_evidence_has_explicit_reasons(changes, reason) -> None:
    result = select_candidate((replace(GOOD, **changes),), LIMITS)
    assert result.status == "NO_FEASIBLE_CANDIDATE"
    assert result.selected_candidate_id is None
    assert reason in result.evaluations[0].reasons


def test_empty_or_all_failed_does_not_relax_limits() -> None:
    assert select_candidate((), LIMITS).status == "NO_FEASIBLE_CANDIDATE"
    failed = replace(GOOD, quality=94)
    assert select_candidate((failed,), LIMITS).selected_candidate_id is None


def test_zero_quality_is_a_real_measurement_if_explicitly_allowed() -> None:
    result = select_candidate((replace(GOOD, quality=0),), replace(LIMITS, minimum_quality=0))
    assert result.selected_candidate_id == "good"


def test_ssim_uses_own_units_and_rejects_vmaf_score() -> None:
    limits = replace(LIMITS, metric="ssim", minimum_quality=0.95)
    invalid = replace(GOOD, metric="ssim")
    assert select_candidate((invalid,), limits).status == "NO_FEASIBLE_CANDIDATE"
    valid = replace(invalid, quality=0.98)
    assert select_candidate((valid,), limits).status == "SELECTED"


@pytest.mark.parametrize("changes", [
    {"domain": "coded_hdr"}, {"reference_sha256": "unknown"},
    {"minimum_quality": float("nan")}, {"minimum_quality": True},
    {"minimum_quality": 101}, {"maximum_bytes": 0}, {"maximum_bytes": True},
    {"maximum_average_bitrate_bps": float("inf")}, {"maximum_average_bitrate_bps": 0},
    {"maximum_encode_wall_sec": -1},
])
def test_invalid_or_wrong_domain_limits_rejected(changes) -> None:
    with pytest.raises(ValueError):
        replace(LIMITS, **changes)


def test_duplicate_ids_rejected() -> None:
    with pytest.raises(ValueError):
        select_candidate((GOOD, GOOD), LIMITS)


def test_optional_wall_limit_does_not_require_wall_observation() -> None:
    result = select_candidate((replace(GOOD, encode_wall_sec=None),),
                              replace(LIMITS, maximum_encode_wall_sec=None))
    assert result.status == "SELECTED"
