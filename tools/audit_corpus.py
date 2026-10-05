"""Prepare a small, family-separated engineering corpus using pinned open sources.

Uses the existing natural_corpus runner; this is not a second encode pipeline.
Derived HDR, rescaled cadence and muted clips are labelled as such. No generated
clip is claimed to be a native-camera master or independent work.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

from tools.natural_corpus import REPO, _sha256, load_manifest
from video_uniquifier.core.models import TransformConfig
from video_uniquifier.core.profile_loader import dump_profile, load_profile

TOS_RIGHTS = "https://commons.wikimedia.org/wiki/File:Tears_of_Steel_in_4k_-_Official_Blender_Foundation_release.webm"
MERIDIAN_RIGHTS = "https://opencontent.netflix.com/"
BBB_RIGHTS = "https://commons.wikimedia.org/wiki/File:Big_Buck_Bunny_4K.webm"


def prepare(root: Path) -> None:
    root = root.resolve()
    destination = root / "corpus"
    destination.mkdir(parents=True, exist_ok=False)
    media = destination / "media"
    media.mkdir()
    profiles = destination / "profiles"
    profiles.mkdir()
    variants = []
    for name in ("soft", "medium", "aggressive"):
        for hdr in (False, True):
            for seed in (11, 22, 33):
                identifier = f"{name}-{'tonemap-' if hdr else ''}{seed}"
                profile = load_profile(REPO / "src/video_uniquifier/profiles" / f"{name}.yaml")
                transforms = list(profile.transforms)
                if hdr:
                    transforms.insert(0, TransformConfig(id="video.tonemap_sdr"))
                profile = profile.model_copy(update={
                    "name": identifier, "seed_strategy": "fixed", "seed": seed,
                    "skip_watermark_check": True, "transforms": transforms,
                })
                path = profiles / f"{identifier}.yaml"
                dump_profile(profile, path)
                variants.append({"id": identifier, "profile": f"profiles/{path.name}",
                                 "encoder": "libx264"})
    masters = [
        ("tears-of-steel", "tears-of-steel-1080p.webm", TOS_RIGHTS, "development"),
        ("meridian", "meridian-uhd-hdr-p3pq.mp4", MERIDIAN_RIGHTS, "development"),
        ("big-buck-bunny", "big-buck-bunny-480p.webm", BBB_RIGHTS, "holdout"),
    ]
    cases = []
    derivations = []
    pilot_ids = {"tears-of-steel-00", "tears-of-steel-03", "tears-of-steel-07",
                 "meridian-01", "meridian-04", "meridian-07"}
    for family, filename, rights, split in masters:
        source = root / "media" / filename
        source_hash = _sha256(source)
        for index in range(10):
            identifier = f"{family}-{index:02d}"
            path = media / f"{identifier}.mkv"
            hdr = family == "meridian" and index == 4
            muted = family == "meridian" and index == 7
            vfr = family == "meridian" and index == 1
            rate = [24, 30, 60][index % 3]
            filters = []
            if family == "meridian":
                if hdr:
                    filters.append(
                        "zscale=pin=smpte432:tin=smpte2084:min=bt709:rin=limited:"
                        "p=bt2020:t=smpte2084:m=bt2020nc:r=limited"
                    )
                else:
                    filters.extend([
                        "zscale=pin=smpte432:tin=smpte2084:min=bt709:rin=limited:"
                        "p=bt709:t=linear:m=gbr:r=full:npl=100:w=320:h=180",
                        "format=gbrpf32le", "tonemap=hable:desat=0",
                        "zscale=p=bt709:t=bt709:m=bt709:r=limited",
                    ])
            filters.extend(["scale=320:180", f"fps={rate}"])
            if vfr:
                filters.append("select='if(lt(t,4),not(mod(n,2)),1)'")
            command = ["ffmpeg", "-v", "error", "-nostdin", "-n", "-threads", "1",
                       "-ss", str(30 + index * 40), "-i", str(source), "-t", "8",
                       "-map", "0:v:0", "-vf", ",".join(filters), "-fps_mode", "vfr",
                       "-c:v", "libx265" if hdr else "libx264", "-preset", "ultrafast",
                       "-crf", "18", "-pix_fmt", "yuv420p10le" if hdr else "yuv420p",
                       "-force_key_frames", "expr:gte(t,n_forced*1)"]
            if hdr:
                command.extend(["-color_primaries", "bt2020", "-color_trc", "smpte2084",
                                "-colorspace", "bt2020nc", "-x265-params",
                                "pools=1:frame-threads=1:hdr10=1:repeat-headers=1:"
                                "master-display=G(13250,34500)B(7500,3000)R(34000,16000)"
                                "WP(15635,16450)L(10000000,1):max-cll=1000,400"])
            if muted:
                command.append("-an")
            else:
                command.extend(["-map", "0:a:0?", "-c:a", "flac", "-ar", "48000"])
            command.append(str(path))
            subprocess.run(command, check=True, capture_output=True, timeout=180)
            selected = [variant["id"] for variant in variants
                        if ("tonemap" in variant["id"]) == hdr]
            cases.append({
                "id": identifier, "source": f"media/{path.name}", "rights_status": "licensed",
                "rights_reference": rights, "media_class": "hdr10" if hdr else "sdr",
                "family_id": family, "split": split, "variants": selected,
                "review_cues": ["8-second excerpt; motion/text/gradients and sync require review",
                                "derived HDR, not native" if hdr else "rescaled engineering clip"],
            })
            derivations.append({
                "id": identifier, "master_sha256": source_hash, "sha256": _sha256(path),
                "commands": [command], "rights_reference": rights,
                "family_id": family, "split": split, "start_sec": 30 + index * 40,
                "duration_sec": 8, "hdr_derived": hdr, "muted": muted, "vfr_derived": vfr,
                "native_hdr": False, "independent_event_labels": None,
            })
            print(f"prepared {identifier}", flush=True)
    matrix = {"schema_version": 1, "matrix": {"workers": 1, "variants": variants}}
    for name, selected in (
        ("corpus", cases),
        ("pilot", [dict(case, split="pilot") for case in cases if case["id"] in pilot_ids]),
    ):
        manifest = destination / f"{name}.yaml"
        manifest.write_text(yaml.safe_dump({**matrix, "cases": selected}, sort_keys=False))
        load_manifest(manifest)
    (destination / "derivations.json").write_text(json.dumps(derivations, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory containing fetched master media/")
    args = parser.parse_args()
    prepare(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
