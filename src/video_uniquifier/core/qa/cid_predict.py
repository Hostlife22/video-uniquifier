"""Legacy chunked source/candidate similarity heuristic.

This module does not model or predict any external rights-management system.
It measures pHash samples and aggregate prefix Chromaprint Jaccard. The raw
common-prefix visual domain is bounded to 600 seconds; the rest is unmeasured.
Audio codes are not assigned invented per-chunk timestamps. Window maxima expose
sampled visual collisions; the overall score also includes available prefix audio.

``match_probability_self`` is a compatibility field name.  Its value is an
uncalibrated maximum similarity heuristic, not a probability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from video_uniquifier.core.errors import PipelineError
from video_uniquifier.core.qa import audio_fp, phash
from video_uniquifier.core.qa.corpus import Corpus, CorpusMatch
from video_uniquifier.core.qa.utils import _decode_chromaprint


@dataclass(frozen=True)
class ChunkSimilarity:
    start_sec: float
    end_sec: float
    visual_similarity: float    # 0..1
    audio_similarity: float | None  # unavailable or not localized, never a fabricated zero
    combined: float             # max of the two


@dataclass(frozen=True)
class CIDPredictResult:
    match_probability_self: float | None
    chunks: list[ChunkSimilarity]
    weakest_chunk: ChunkSimilarity | None
    corpus_matches: list[CorpusMatch]
    notes: tuple[str, ...] = ()
    audio_available: bool = False


def predict(
    input_path: Path,
    output_path: Path,
    *,
    chunk_sec: float = 4.0,
    corpus: Corpus | None = None,
    corpus_threshold: float = 0.3,
) -> CIDPredictResult:
    """Compute per-chunk similarity input↔output, plus optional corpus search."""
    if not math.isfinite(chunk_sec) or chunk_sec <= 0:
        raise ValueError("chunk_sec must be finite and positive")
    source_duration = phash._probe_duration(input_path)
    candidate_duration = phash._probe_duration(output_path)
    duration = min(source_duration, candidate_duration, 600.0)
    if duration <= 0:
        return CIDPredictResult(None, [], None, [], ("similarity: empty timeline",))

    notes = [
        f"similarity: raw common-prefix domain [0, {duration:.3f}]s; "
        "sampled visual evidence, not continuous coverage or lip-sync evidence"
    ]
    if max(source_duration, candidate_duration) > duration:
        notes.append("similarity: remaining tail unmeasured (600s budget or unequal durations)")

    n_chunks = max(1, min(150, math.ceil(duration / chunk_sec)))
    window_sec = duration / n_chunks

    # ---- visual: sample multiple frames per chunk; per-chunk visual = MAX over
    # samples in that window. Single-sample-per-chunk (legacy) rounded
    # soft/medium/aggressive profiles into the same bucket — CRIT-3 from the
    # 2026-05-30 test report. 4× oversample gives enough resolution to
    # distinguish subtle transforms without blowing up cost.
    samples_per_chunk = 4
    total_samples = max(n_chunks * samples_per_chunk, 16)
    try:
        in_phashes = phash._sample_hashes_range(input_path, 0.0, duration, total_samples)
        out_phashes = phash._sample_hashes_range(output_path, 0.0, duration, total_samples)
    except PipelineError as exc:
        in_phashes, out_phashes = [], []
        notes.append(f"similarity: visual extraction error: {exc}")
    actual_samples = min(len(in_phashes), len(out_phashes))

    # ---- audio: bounded aggregate prefix, without invented interval timestamps ----
    in_fp = _full_fingerprint(input_path)
    out_fp = _full_fingerprint(output_path)
    audio_available = bool(in_fp and out_fp)
    if abs(min(source_duration, 600.) - min(candidate_duration, 600.)) > .5:
        audio_available = False
        notes.append("similarity: aggregate audio unavailable for unequal prefix spans; "
                     "raw fingerprints are not automatically retimed")
    audio_score = _jaccard(set(in_fp), set(out_fp)) if audio_available else None
    notes.append(
        "similarity: audio is aggregate prefix Jaccard only; no interval localization"
        if audio_available else "similarity: audio unavailable (fpcalc missing, extraction error, "
        "no track or empty/silent fingerprint); no audio score assigned"
    )

    chunks: list[ChunkSimilarity] = []
    for i in range(n_chunks):
        # The fps grid uses the same common span for both files. Missing
        # decoded samples never stretch the surviving hashes over the tail.
        lo = math.ceil(i * total_samples / n_chunks)
        hi = min(math.ceil((i + 1) * total_samples / n_chunks), actual_samples)
        if lo >= hi:
            continue
        else:
            # Retain the maximum to expose local self-collisions that a mean
            # would hide.
            vis = max(
                _phash_pair_similarity(in_phashes[j], out_phashes[j])
                for j in range(lo, hi)
            )
        aud = audio_score if n_chunks == 1 else None
        combined = max(vis, aud) if aud is not None else vis
        chunks.append(ChunkSimilarity(
            start_sec=i * window_sec,
            end_sec=min((i + 1) * window_sec, duration),
            visual_similarity=vis,
            audio_similarity=aud,
            combined=combined,
        ))

    if not chunks:
        match_prob = audio_score
        weakest: ChunkSimilarity | None = None
    else:
        match_prob = max(c.combined for c in chunks)
        if audio_score is not None:
            match_prob = max(match_prob, audio_score)
        # ``weakest_chunk`` is a compatibility name for the most-similar
        # source/candidate window. It is argmax, not argmin.
        weakest = max(chunks, key=lambda c: c.combined)

    corpus_matches: list[CorpusMatch] = []
    if corpus is not None:
        corpus_matches = corpus.search_match(output_path, threshold=corpus_threshold)

    return CIDPredictResult(
        match_probability_self=match_prob,
        chunks=chunks,
        weakest_chunk=weakest,
        corpus_matches=corpus_matches,
        notes=tuple(notes),
        audio_available=audio_available,
    )


# ---- helpers --------------------------------------------------------------

def _phash_pair_similarity(a: int, b: int) -> float:
    dist = bin(a ^ b).count("1")
    return max(0.0, 1.0 - dist / 64.0)


def _full_fingerprint(path: Path) -> list[int]:
    if not audio_fp.fpcalc_available():
        return []
    raw = audio_fp._run_fpcalc(path)
    if not raw or "fingerprint" not in raw:
        return []
    try:
        return _decode_chromaprint(str(raw["fingerprint"]))
    except ValueError:
        return []


def _jaccard(s1: set[int], s2: set[int]) -> float:
    union = len(s1 | s2)
    return len(s1 & s2) / union if union else 0.0
