"""Isolated, cancellable process around the original PySceneDetect adapter."""

from __future__ import annotations

import sys
from pathlib import Path

from video_uniquifier.core.reels.runtime import atomic_json
from video_uniquifier.core.scene_detect import detect_scene_boundaries


def main() -> None:
    source, threshold, minimum, destination = sys.argv[1:]
    boundaries = detect_scene_boundaries(Path(source), threshold=float(threshold),
                                         min_length_sec=float(minimum))
    atomic_json(Path(destination), boundaries, root=Path(destination).parent)


if __name__ == "__main__":
    main()
