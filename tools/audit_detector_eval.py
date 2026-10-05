"""Freeze local thresholds on development, then evaluate a separate title family.

Labels mean same source window versus a different non-overlapping source window.
They are not rights labels, human semantic judgements or platform outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import imagehash

from tools.benchmark import _ProcessTreeMemorySampler
from tools.natural_corpus import _sha256, _toolchain, load_manifest
from video_uniquifier.core.qa import audio_fp, phash, sscd
from video_uniquifier.core.scene_detect import detect_scene_boundaries


def assess(rows: list[dict[str, Any]], metric: str, threshold: float) -> dict[str, Any]:
    tp = fp = tn = fn = missing = 0
    for row in rows:
        score = row["scores"].get(metric)
        if score is None:
            missing += 1
        predicted = score is not None and score >= threshold
        positive = row["positive"]
        tp += int(predicted and positive)
        fp += int(predicted and not positive)
        tn += int(not predicted and not positive)
        fn += int(not predicted and positive)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.
    return {"threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1, "unavailable": missing}


def choose_threshold(rows: list[dict[str, Any]], metric: str) -> float:
    if any(row.get("split") != "development" for row in rows):
        raise ValueError("threshold selection requires development rows only")
    scores = [row["scores"].get(metric) for row in rows]
    finite = [float(value) for value in scores if value is not None and math.isfinite(value)]
    if not finite:
        raise ValueError(f"no development measurement for {metric}")
    thresholds = sorted(set([0., 1., *finite]))
    return max(thresholds, key=lambda t: (assess(rows, metric, t)["f1"], t))


def _scene_score(source: Path, output: Path) -> tuple[float | None, list[float], str | None]:
    duration = min(phash._probe_duration(source), phash._probe_duration(output))
    try:
        boundaries = [0., *detect_scene_boundaries(source), duration]
        scenes = [(left, right) for left, right in zip(boundaries, boundaries[1:], strict=False)
                  if 0 <= left < right <= duration]
        chosen = sorted(scenes, key=lambda span: span[1] - span[0], reverse=True)[:4]
        timestamps = sorted((left + right) / 2 for left, right in chosen)
        values = []
        for timestamp in timestamps:
            a = phash.sample_frames_range(source, timestamp, min(.1, duration - timestamp), 1)
            b = phash.sample_frames_range(output, timestamp, min(.1, duration - timestamp), 1)
            try:
                if a and b:
                    values.append(1 - int(imagehash.phash(a[0]) - imagehash.phash(b[0])) / 64)
            finally:
                for frame in [*a, *b]:
                    frame.close()
        return (sum(values) / len(values) if values else None), timestamps, None
    except Exception as exc:  # noqa: BLE001 - retained experiment failure
        return None, [], str(exc)


def run(manifest_path: Path, outputs: Path, destination: Path) -> None:
    manifest = load_manifest(manifest_path)
    destination.mkdir(parents=True, exist_ok=False)
    # Load official pinned weights once, and declare the CPU budget.
    import torch

    torch.set_num_threads(2)
    model = sscd._default_model_loader()
    sampler = _ProcessTreeMemorySampler()
    sampler.start()
    rows: list[dict[str, Any]] = []
    frozen: dict[str, float] = {}
    started = time.monotonic()
    split_results = {}
    for split in ("development", "holdout"):
        cases = [case for case in manifest.cases if case.split == split]
        for index, case in enumerate(cases):
            # A disjoint window from the same title supplies a harder negative
            # when possible; the generation manifest records exact temporal bounds.
            family_cases = [other for other in cases if other.family_id == case.family_id]
            negative_case = family_cases[(family_cases.index(case) + 1) % len(family_cases)]
            if negative_case == case:
                negative_case = cases[(index + 1) % len(cases)]
            for positive, candidate_case in ((True, case), (False, negative_case)):
                variant = candidate_case.variant_ids[0]
                output = outputs / f"{candidate_case.case_id}__{variant}" / "output.mp4"
                scores: dict[str, float | None] = {}
                notes = []
                timing = {}
                t0 = time.monotonic()
                if output.is_file():
                    for name in ("phash", "sscd", "audio"):
                        t1 = time.monotonic()
                        try:
                            if name == "phash":
                                measurement = phash.compare(case.source, output, n=4)
                                scores[name] = (
                                    measurement.similarity if measurement.samples else None
                                )
                            elif name == "sscd":
                                scores[name] = sscd.compute_sscd(
                                    case.source, output, frame_count=4, model_loader=lambda: model,
                                ).mean_similarity
                            else:
                                measurement_audio = audio_fp.analyze_pair(case.source, output)
                                scores[name] = measurement_audio.similarity.similarity
                                if measurement_audio.similarity.note:
                                    notes.append(measurement_audio.similarity.note)
                        except Exception as exc:  # noqa: BLE001 - missing stays explicit
                            scores[name] = None
                            notes.append(f"{name}: {exc}")
                        timing[name] = time.monotonic() - t1
                    t1 = time.monotonic()
                    scene_score, timestamps, scene_note = _scene_score(case.source, output)
                    scores["scene_phash"] = scene_score
                    timing["scene_phash"] = time.monotonic() - t1
                    if scene_note:
                        notes.append(scene_note)
                else:
                    scores = {name: None for name in ("phash", "sscd", "audio", "scene_phash")}
                    timestamps = []
                    notes.append("candidate output missing")
                rows.append({
                    "split": split, "case": case.case_id, "candidate_case": candidate_case.case_id,
                    "positive": positive, "source_sha256": _sha256(case.source),
                    "output_sha256": _sha256(output) if output.is_file() else None,
                    "family_id": case.family_id, "scores": scores, "notes": notes,
                    "wall_sec": time.monotonic() - t0, "metric_wall_sec": timing,
                    "scene_requested_timestamps": timestamps,
                })
                print(f"measured {split} {case.case_id} positive={positive}", flush=True)
        selected = [row for row in rows if row["split"] == split]
        if split == "development":
            for metric in ("phash", "sscd", "audio", "scene_phash"):
                frozen[metric] = choose_threshold(selected, metric)
            (destination / "frozen-thresholds.json").write_text(json.dumps(frozen, indent=2))
        split_results[split] = {metric: assess(selected, metric, threshold)
                                for metric, threshold in frozen.items()}
    rss, rss_method = sampler.stop()
    scene_delta = (
        split_results["holdout"]["scene_phash"]["f1"]
        - split_results["holdout"]["phash"]["f1"]
    )
    report = {
        "manifest_sha256": _sha256(manifest_path), "frozen_thresholds": frozen,
        "results": split_results, "rows": rows, "sscd_model_sha256": sscd._MODEL_SHA256,
        "sscd_sampling": "4 normalized midpoint pairs, 288 RGB, official ImageNet/L2 recipe",
        "torch_threads": 2, "toolchain": _toolchain(), "wall_sec": time.monotonic() - started,
        "rss_peak_kb": rss, "rss_method": rss_method,
        "labels": "same excerpt vs different non-overlapping excerpt; shared imagery possible",
        "uncertainty": "Only 2 development titles and 1 holdout title; pairs are clustered, "
                       "not independent IID examples. No population/platform estimate.",
        "segment_localization": "NOT VERIFIED: independent segment labels absent",
        "scene_experiment": {
            "budget": "up to 4 longest-scene midpoint pairs; threshold 27; no production change",
            "holdout_f1_delta": scene_delta,
            "decision": "retain fixed sampling; no adoption without broader independent recall "
                        "and decoder-budget evidence, especially for short inserts",
        },
    }
    (destination / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    run(args.manifest, args.outputs, args.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
