"""Private experimental selector; no application defaults or accepted thresholds.

Every limit is supplied explicitly. Metric domain and reference identity must
match, and feasibility never overrides failed correctness or missing evidence.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

Metric = Literal["vmaf", "ssim"]
Domain = Literal["plan_transformed_sdr", "coded_hdr"]


@dataclass(frozen=True)
class QualitySizeLimits:
    reference_sha256: str
    metric: Metric
    domain: Domain
    minimum_quality: float
    maximum_bytes: int
    maximum_average_bitrate_bps: float
    maximum_encode_wall_sec: float | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.reference_sha256):
            raise ValueError("a pinned reference SHA-256 is required")
        if self.metric not in {"vmaf", "ssim"} or self.domain not in {
            "plan_transformed_sdr", "coded_hdr",
        }:
            raise ValueError("unknown metric or domain")
        if self.metric == "vmaf" and self.domain != "plan_transformed_sdr":
            raise ValueError("SDR VMAF cannot qualify coded HDR")
        ceiling = 100 if self.metric == "vmaf" else 1
        if not _finite_number(self.minimum_quality) or not 0 <= self.minimum_quality <= ceiling:
            raise ValueError("quality limit outside metric units")
        if (isinstance(self.maximum_bytes, bool) or not isinstance(self.maximum_bytes, int)
                or self.maximum_bytes <= 0):
            raise ValueError("positive integer byte limit required")
        if (not _finite_number(self.maximum_average_bitrate_bps)
                or self.maximum_average_bitrate_bps <= 0):
            raise ValueError("positive finite average bitrate required")
        if self.maximum_encode_wall_sec is not None and (
            not _finite_number(self.maximum_encode_wall_sec) or self.maximum_encode_wall_sec <= 0
        ):
            raise ValueError("positive finite wall limit required")


@dataclass(frozen=True)
class CandidateObservation:
    candidate_id: str
    reference_sha256: str
    metric: Metric
    domain: Domain
    quality: float | None
    size_bytes: int
    duration_sec: float
    encode_wall_sec: float | None
    correctness_passed: bool


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    feasible: bool
    reasons: tuple[str, ...]
    average_bitrate_bps: float | None


@dataclass(frozen=True)
class SelectionResult:
    status: Literal["SELECTED", "NO_FEASIBLE_CANDIDATE"]
    selected_candidate_id: str | None
    evaluations: tuple[CandidateEvaluation, ...]
    human_acceptance: str = "NOT VERIFIED"


def _finite_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def select_candidate(
    candidates: tuple[CandidateObservation, ...], limits: QualitySizeLimits,
) -> SelectionResult:
    """Select highest quality within budgets, then smallest size, then stable ID.

    Average bitrate includes the container and audio. It is not a VBV/peak
    bitrate guarantee. No feasible candidate means refusal, not relaxed limits.
    """
    identifiers = [candidate.candidate_id for candidate in candidates]
    if len(set(identifiers)) != len(identifiers) or any(not key for key in identifiers):
        raise ValueError("candidate identifiers must be unique and nonempty")
    evaluations = []
    feasible: list[CandidateObservation] = []
    for candidate in candidates:
        reasons = []
        if candidate.correctness_passed is not True:
            reasons.append("correctness_not_passed")
        if (candidate.reference_sha256 != limits.reference_sha256
                or candidate.metric != limits.metric or candidate.domain != limits.domain):
            reasons.append("reference_or_metric_domain_mismatch")
        ceiling = 100 if limits.metric == "vmaf" else 1
        if (not _finite_number(candidate.quality) or candidate.quality is None
                or not 0 <= candidate.quality <= ceiling):
            reasons.append("quality_unavailable_or_outside_units")
        elif candidate.quality < limits.minimum_quality:
            reasons.append("quality_below_limit")
        valid_size = (isinstance(candidate.size_bytes, int)
                      and not isinstance(candidate.size_bytes, bool) and candidate.size_bytes > 0)
        valid_duration = (_finite_number(candidate.duration_sec) and candidate.duration_sec > 0)
        bitrate = candidate.size_bytes * 8 / candidate.duration_sec if (
            valid_size and valid_duration
        ) else None
        if not valid_size or not valid_duration or bitrate is None or not math.isfinite(bitrate):
            reasons.append("size_or_duration_unavailable")
            bitrate = None
        else:
            if candidate.size_bytes > limits.maximum_bytes:
                reasons.append("size_exceeds_limit")
            if bitrate > limits.maximum_average_bitrate_bps:
                reasons.append("average_bitrate_exceeds_limit")
        if limits.maximum_encode_wall_sec is not None:
            if (candidate.encode_wall_sec is None or not _finite_number(candidate.encode_wall_sec)
                    or candidate.encode_wall_sec <= 0):
                reasons.append("encode_wall_unavailable")
            elif candidate.encode_wall_sec > limits.maximum_encode_wall_sec:
                reasons.append("encode_wall_exceeds_limit")
        evaluations.append(CandidateEvaluation(candidate.candidate_id, not reasons,
                                                tuple(reasons), bitrate))
        if not reasons:
            feasible.append(candidate)
    selected = min(feasible, key=lambda candidate: (
        -(candidate.quality if candidate.quality is not None else 0),
        candidate.size_bytes, candidate.candidate_id,
    )) if feasible else None
    return SelectionResult("SELECTED" if selected else "NO_FEASIBLE_CANDIDATE",
                           selected.candidate_id if selected else None, tuple(evaluations))
