"""Paired source-cap/CRF experiment using the existing segment command builder.

No production defaults change. Compare each encode with the *same transformed*
lossless SDR reference, isolating encoding loss from intentional transforms.
Small-corpus observations are not approved production quality thresholds.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import statistics
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tools.media_diagnostics import decoded_timeline
from tools.natural_corpus import _capture, _load_json, _psnr, _sha256, load_manifest
from video_uniquifier.core._quality_size_policy import (
    CandidateObservation,
    QualitySizeLimits,
    select_candidate,
)
from video_uniquifier.core.orchestrator import build_plan
from video_uniquifier.core.pipeline import _encoder_args_for, build_video_segment_command
from video_uniquifier.core.probe import probe
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.core.qa.ssim import compute as ssim
from video_uniquifier.core.qa.vmaf import compute as vmaf


def observed_bands(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe observed encoding loss; do not fit a quality gate to unlabeled data."""
    groups: dict[str, Any] = {}
    for policy in sorted({row["policy"] for row in rows}):
        selected = [row for row in rows if row["policy"] == policy]
        metrics = {}
        for metric in ("vmaf", "ssim", "psnr_db", "size_bytes", "wall_sec", "rss_peak_kb"):
            values = [row.get(metric) for row in selected]
            finite = [float(value) for value in values
                      if isinstance(value, (int, float)) and not isinstance(value, bool)
                      and math.isfinite(value)]
            metrics[metric] = {
                "measured": len(finite), "missing": len(values) - len(finite),
                "min": min(finite) if finite else None,
                "median": statistics.median(finite) if finite else None,
                "max": max(finite) if finite else None,
            }
        groups[policy] = {
            "unique_source_files": len({row["source_sha256"] for row in selected}),
            "repeats_are_not_independent_content": True, "observed_bands": metrics,
        }
    return {
        "status": "NOT VERIFIED", "proposed_production_thresholds": None,
        "reason": "No human accept/reject labels or independent held-out titles; "
        "encoding-only scores do not judge the intentional transform or HDR mastering.",
        "groups": groups,
    }


def assess_existing(destination: Path) -> None:
    """Add decoded contracts, empirical bands and an A/B page without re-encoding."""
    report = _load_json(destination / "results.json")
    if not report.get("complete") or not report.get("rows"):
        raise ValueError("experiment must finish before assessment")
    timelines: dict[Path, dict[str, Any]] = {}
    evidence = []
    previews = []
    for row in report["rows"]:
        cell_name = f"{row['case']}__{row['variant']}"
        cell = destination / cell_name
        if not cell.resolve().is_relative_to(destination.resolve()):
            raise ValueError("unsafe cell")
        output = cell / f"{row['policy']}-{row['repeat']}.mp4"
        if not output.resolve().is_relative_to(cell.resolve()):
            raise ValueError("unsafe output")
        reference = cell / "reference.mkv"
        if reference not in timelines:
            timelines[reference] = decoded_timeline(reference)
        timeline = decoded_timeline(output)
        actual, expected = timeline["streams"][0], timelines[reference]["streams"][0]
        good = (actual["frames"] == expected["frames"]
                and not actual["missing_pts_frames"] and not actual["non_increasing_pts_frames"])
        evidence.append({"cell": cell_name, "file": output.name,
                         "frame_pts_contract": "passed" if good else "failed",
                         "timeline": timeline})
        if row["repeat"] == 0:
            relative = html.escape(f"{cell_name}/{output.name}", quote=True)
            previews.append(
                f"<h2>{html.escape(cell_name)} — {html.escape(row['policy'])}</h2>"
                f"<video controls preload='metadata' width='640' src='{relative}'></video>"
                f"<p>VMAF {row['vmaf']}; SSIM {row['ssim']}; bytes {row['size_bytes']}</p>"
            )
    assessment = {"calibration": observed_bands(report["rows"]), "decoded_contracts": evidence}
    with (destination / "assessment.json").open("x", encoding="utf-8") as stream:
        json.dump(assessment, stream, indent=2, allow_nan=False)
    with (destination / "review.html").open("x", encoding="utf-8") as stream:
        stream.write("<!doctype html><meta charset='utf-8'><h1>Encoding-only A/B review</h1>"
                     "<p>No human approval recorded. Same post-transform SDR reference; "
                     "not a comparison of HDR mastering or transform quality.</p>"
                     + "\n".join(previews))


def select_existing(
    destination: Path, output: Path, *, minimum_vmaf: float,
    maximum_size_ratio: float, maximum_average_bitrate_bps: float,
) -> dict[str, Any]:
    """Evaluate retained short encodes only; supplied limits are hypotheses.

    Re-decode and re-score short candidates, pin references, and refuse size
    mismatches. Never encode a candidate or modify production settings here.
    """
    if not math.isfinite(maximum_size_ratio) or maximum_size_ratio <= 0:
        raise ValueError("positive finite size ratio required")
    report = _load_json(destination / "results.json")
    if (not report.get("complete") or not report.get("rows")
            or report.get("method") !=
            "paired encoding-only against identical transformed FFV1 SDR reference"):
        raise ValueError("complete transformed-SDR experiment required")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in report["rows"]:
        groups.setdefault(f"{row['case']}__{row['variant']}", []).append(row)
    cells = []
    for name, rows in sorted(groups.items()):
        cell = destination / name
        if not cell.resolve().is_relative_to(destination.resolve()):
            raise ValueError("unsafe cell")
        reference = cell / "reference.mkv"
        metadata = probe(reference)
        if len(metadata.video) != 1 or metadata.video[0].color.is_hdr:
            raise ValueError("reference must be single-video SDR")
        expected = decoded_timeline(reference)["streams"][0]
        reference_hash = _sha256(reference)
        if not 0 < metadata.duration_sec <= 30:
            raise ValueError("reference exceeds bounded selection scope")
        baseline = [row for row in rows if row["policy"] == "source_cap"]
        if not baseline:
            raise ValueError("source_cap baseline required for each cell")
        limits = QualitySizeLimits(
            reference_hash, "vmaf", "plan_transformed_sdr", minimum_vmaf,
            math.floor(min(row["size_bytes"] for row in baseline) * maximum_size_ratio),
            maximum_average_bitrate_bps,
        )
        candidates = []
        identities = []
        for row in rows:
            path = cell / f"{row['policy']}-{row['repeat']}.mp4"
            if not path.resolve().is_relative_to(cell.resolve()):
                raise ValueError("unsafe candidate path")
            if path.stat().st_size != row["size_bytes"]:
                raise ValueError("candidate size differs from scored evidence")
            if not 0 < row["seconds"] <= 30:
                raise ValueError("selection only supports bounded development clips")
            candidate_meta = probe(path)
            if (not 0 < candidate_meta.duration_sec <= 30 or len(candidate_meta.video) != 1
                    or candidate_meta.video[0].color.is_hdr):
                raise ValueError("candidate must be bounded single-video SDR")
            timeline = decoded_timeline(path)
            streams = timeline["streams"]
            actual = streams[0]
            correct = (
                len(streams) == 1 and actual["kind"] == "video"
                and actual["frames"] == expected["frames"] and actual["frames"] > 0
                and not actual["missing_pts_frames"] and not actual["non_increasing_pts_frames"]
                and not expected["missing_pts_frames"]
                and not expected["non_increasing_pts_frames"]
                and actual["end_sec"] is not None and expected["end_sec"] is not None
                and abs(actual["end_sec"] - expected["end_sec"]) <= 0.001
                and actual["start_sec"] is not None and expected["start_sec"] is not None
                and abs(actual["start_sec"] - expected["start_sec"]) <= 0.001
            )
            duration = (actual["end_sec"] - actual["start_sec"]
                        if actual["end_sec"] is not None and actual["start_sec"] is not None
                        else float("nan"))
            measured = vmaf(reference, path)
            candidates.append(CandidateObservation(
                path.name, reference_hash, "vmaf", "plan_transformed_sdr", measured.score,
                path.stat().st_size, duration, row["wall_sec"], correct,
            ))
            identities.append({"candidate": path.name, "sha256": _sha256(path),
                               "source_sha256": row["source_sha256"], "timeline": timeline,
                               "retained_vmaf": row["vmaf"], "current_vmaf": measured.score,
                               "metric_note": measured.note})
        cells.append({"cell": name, "limits": asdict(limits),
                      "selection": asdict(select_candidate(tuple(candidates), limits)),
                      "identities": identities})
    payload = {
        "experimental": True, "human_acceptance": "NOT VERIFIED",
        "production_defaults_changed": False,
        "limits_origin": "explicit engineering hypotheses; not fitted or accepted bands",
        "score_provenance": "fresh VMAF on pinned retained SDR references and candidates",
        "results_sha256": _sha256(destination / "results.json"),
        "baseline": "smallest retained source_cap output per cell; not source file size",
        "bitrate_scope": "whole-file average; not a peak bitrate or VBV guarantee",
        "maximum_size_ratio": maximum_size_ratio, "cells": cells,
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
    return payload


def without_vbv(args: list[str]) -> list[str]:
    """Remove only maxrate/bufsize, retaining codec, CRF, filters and GOP."""
    result = []
    index = 0
    while index < len(args):
        if args[index] in {"-maxrate", "-bufsize"}:
            if index + 1 == len(args):
                raise ValueError("missing VBV option value")
            index += 2
        else:
            result.append(args[index])
            index += 1
    return result


def scaled_vbv(args: list[str], multiplier: float) -> list[str]:
    """Experimental bounded arm; production encoder defaults are untouched."""
    if not math.isfinite(multiplier) or not 1 < multiplier <= 32:
        raise ValueError("VBV multiplier must be finite and in (1, 32]")
    result = list(args)
    for option in ("-maxrate", "-bufsize"):
        if option not in result:
            raise ValueError(f"bounded experiment requires {option}")
        index = result.index(option) + 1
        if index == len(result):
            raise ValueError("missing VBV option value")
        raw = result[index]
        suffix = raw[-1] if raw[-1:] in {"k", "M"} else ""
        amount = float(raw[:-1] if suffix else raw)
        result[index] = f"{amount * multiplier:g}{suffix}"
    return result


def run(
    manifest_path: Path, destination: Path, *, seconds: float, repeats: int,
    start_sec: float = 0.0, vbv_multipliers: tuple[float, ...] = (),
) -> None:
    if not 0 < seconds <= 30 or not 1 <= repeats <= 5:
        raise ValueError("use 0 < seconds <= 30 and 1 <= repeats <= 5")
    if not math.isfinite(start_sec) or start_sec < 0:
        raise ValueError("start_sec must be finite and nonnegative")
    if len(set(vbv_multipliers)) != len(vbv_multipliers):
        raise ValueError("duplicate VBV multiplier")
    for multiplier in vbv_multipliers:
        scaled_vbv(["-maxrate", "1k", "-bufsize", "2k"], multiplier)
    manifest = load_manifest(manifest_path)
    destination.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    provenance = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        "method": "paired encoding-only against identical transformed FFV1 SDR reference",
        "acceptance": "NOT VERIFIED: no human labels or independent held-out corpus",
        "start_sec": start_sec, "vbv_multipliers": vbv_multipliers,
    }
    for case in manifest.cases:
        for variant in manifest.variants:
            if variant.variant_id not in case.variant_ids:
                continue
            if variant.encoder != "libx264":
                raise ValueError("isolated CRF experiment currently qualifies libx264 only")
            profile = load_profile(variant.profile)
            if profile.keep_hdr:
                raise ValueError("SDR VMAF must not gate preserved HDR")
            plan = build_plan(case.source, profile, encoder_override="libx264")
            plan = plan.model_copy(update={"run_seed": 42})
            video = plan.source.video[0]
            if start_sec + seconds > plan.source.duration_sec:
                raise ValueError("requested window extends beyond source duration")
            duration = seconds
            source_sha256 = _sha256(case.source)
            estimate = video.width * video.height * max(video.fps, 1) * duration * 6
            if shutil.disk_usage(destination).free < estimate + 2_000_000_000:
                raise ValueError("insufficient reference disk budget")
            cell = destination / f"{case.case_id}__{variant.variant_id}"
            cell.mkdir()
            reference = cell / "reference.mkv"
            base = build_video_segment_command(plan, case.source, cell / "output.mp4").args
            # Limit input decoding, keeping the same source clock and filter graph in all arms.
            input_index = base.index("-i")
            base[input_index:input_index] = ["-ss", str(start_sec), "-t", str(duration)]
            encoder_index = base.index("-c:v")
            encoder_length = len(_encoder_args_for(plan))
            reference_cmd = (
                base[:encoder_index] + ["-c:v", "ffv1", "-level", "3"]
                + base[encoder_index + encoder_length:-1] + [str(reference)]
            )
            if _capture(reference_cmd, cell / "reference.log"):
                raise RuntimeError("lossless reference failed")
            reference_timeline = decoded_timeline(reference)
            (cell / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            for repeat in range(repeats):
                # Alternate order to reduce monotonic thermal/cache bias.
                order = ["source_cap", "crf_only"]
                bounded = {f"cap_x{value:g}": value for value in vbv_multipliers}
                order.extend(bounded)
                # Rotate all arms across repetitions, then reverse alternating runs.
                shift = repeat % len(order)
                order = order[shift:] + order[:shift]
                if repeat % 2:
                    order.reverse()
                for policy in order:
                    output = cell / f"{policy}-{repeat}.mp4"
                    command = base[:-1] + [str(output)]
                    if policy == "crf_only":
                        command = without_vbv(command)
                    elif policy in bounded:
                        command = scaled_vbv(command, bounded[policy])
                    log = output.with_suffix(".log")
                    if _capture(command, log):
                        raise RuntimeError(f"encode failed: {output.name}")
                    timeline = decoded_timeline(output)
                    expected = reference_timeline["streams"][0]
                    actual = timeline["streams"][0]
                    if (actual["frames"] != expected["frames"]
                            or actual["missing_pts_frames"] or actual["non_increasing_pts_frames"]):
                        raise RuntimeError("paired encode frame/PTS contract failed")
                    vm, sm = vmaf(reference, output), ssim(reference, output)
                    psnr, psnr_note = _psnr(reference, output)
                    resources = _load_json(log.with_suffix(".resources.json"))
                    rows.append({
                        "case": case.case_id, "variant": variant.variant_id,
                        "policy": policy, "repeat": repeat, "seconds": duration,
                        "start_sec": start_sec,
                        "source_sha256": source_sha256,
                        "rights_reference": case.rights_reference,
                        "vmaf": vm.score, "ssim": sm.score, "psnr_db": psnr,
                        "size_bytes": output.stat().st_size, **resources,
                        "decoded_timeline": timeline,
                        "command": command, "notes": [vm.note, sm.note, psnr_note],
                    })
                    # Incremental evidence survives interruption without claiming full completion.
                    (destination / "results.json").write_text(json.dumps({
                        **provenance, "complete": False, "rows": rows,
                    }, indent=2, allow_nan=False), encoding="utf-8")
    report = {**provenance, "complete": True, "rows": rows, "calibration": observed_bands(rows)}
    (destination / "results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8",
    )
    fields = ["case", "variant", "policy", "repeat", "start_sec", "seconds",
              "vmaf", "ssim", "psnr_db",
              "size_bytes", "wall_sec", "rss_peak_kb"]
    with (destination / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (destination / "results.html").write_text(
        "<!doctype html><meta charset='utf-8'><h1>Paired rate-control experiment</h1><pre>"
        + html.escape(json.dumps(report, indent=2)) + "</pre>", encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--vbv-multiplier", type=float, action="append", default=[])
    parser.add_argument("--assess-existing", action="store_true")
    parser.add_argument("--select-existing", action="store_true")
    parser.add_argument("--minimum-vmaf", type=float)
    parser.add_argument("--maximum-size-ratio", type=float)
    parser.add_argument("--maximum-average-bitrate-mbps", type=float)
    parser.add_argument("--selection-report", type=Path)
    args = parser.parse_args()
    if args.select_existing:
        if args.assess_existing or any(value is None for value in (
            args.minimum_vmaf, args.maximum_size_ratio,
            args.maximum_average_bitrate_mbps, args.selection_report,
        )):
            parser.error("selection needs explicit quality, size, bitrate and report arguments")
        select_existing(args.results, args.selection_report, minimum_vmaf=args.minimum_vmaf,
                        maximum_size_ratio=args.maximum_size_ratio,
                        maximum_average_bitrate_bps=args.maximum_average_bitrate_mbps * 1_000_000)
    elif args.assess_existing:
        assess_existing(args.results)
    elif args.manifest is None:
        parser.error("manifest is required for a new experiment")
    else:
        run(args.manifest, args.results, seconds=args.seconds, repeats=args.repeats,
            start_sec=args.start_sec, vbv_multipliers=tuple(args.vbv_multiplier))
