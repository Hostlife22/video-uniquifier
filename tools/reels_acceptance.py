"""Generate and process reproducible 10/30/90-second synthetic acceptance media.

Run: .venv/bin/python tools/reels_acceptance.py --root /tmp/reels-acceptance
Synthetic tones/patterns test the technical contract, not dialogue or artistic quality.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from video_uniquifier.core.reels.config import ReelsRules, load_rules
from video_uniquifier.core.reels.processor import process_video
from video_uniquifier.core.reels.runtime import atomic_json
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin


def run_acceptance(root: Path, rules: ReelsRules) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    cases = [(10, "180x320", "30"), (30, "320x180", "30000/1001"),
             (90, "180x320", "24000/1001")]
    results = []
    for seconds, size, rate in cases:
        source = root / f"source-{seconds}s.mp4"
        if not source.exists():
            subprocess.run([
                ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i",
                f"testsrc2=size={size}:rate={rate}:duration={seconds}",
                "-f", "lavfi", "-i",
                f"sine=frequency=440:sample_rate=48000:duration={seconds}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(source),
            ], check=True, capture_output=True, timeout=120)
        destination = root / "jobs" / "results" / f"acceptance-{seconds}s"
        if not destination.exists():
            destination = process_video(source, rules, root / "jobs",
                                        job_id=f"acceptance-{seconds}s")
        report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
        if report["quality_check"]["status"] != "passed":
            raise RuntimeError(f"Acceptance failed: {destination}")
        results.append({"input_seconds": seconds, "source": str(source.resolve()),
                        "artifacts": str(destination.resolve()),
                        "output_seconds": report["output"]["duration_sec"],
                        "delivery_fps": report["delivery_fps"],
                        "elapsed_sec": report["elapsed_sec"],
                        "quality_check": report["quality_check"]})
        print(f"{seconds}s passed: {destination}", flush=True)
    summary: dict[str, object] = {"status": "passed", "synthetic_media": True,
                                 "manual_dialogue_review": "still_required", "cases": results}
    atomic_json(root / "acceptance.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rules", type=Path)
    options = parser.parse_args()
    run_acceptance(options.root, load_rules(options.rules) if options.rules else ReelsRules())
