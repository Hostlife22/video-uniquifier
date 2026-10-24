#!/bin/sh
# Run from any directory: sh /path/to/repository/tools/install_reels.sh
set -eu
REELS_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REELS_PROJECT_DIR"
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "Install FFmpeg with libx264, loudnorm and zscale first (macOS: brew install ffmpeg)." >&2
    exit 1
fi
if command -v uv >/dev/null 2>&1; then
    if [ ! -x .venv/bin/python ]; then
        uv venv --python 3.11 .venv
    fi
    uv pip install --python .venv/bin/python -e '.[scene,web]'
else
    REELS_PYTHON=${REELS_PYTHON:-python3}
    "$REELS_PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "Python >=3.11 required"'
    if [ ! -x .venv/bin/python ]; then
        "$REELS_PYTHON" -m venv .venv
    fi
    .venv/bin/python -m pip install -e '.[scene,web]'
fi
.venv/bin/video-reels validate examples/facebook_reels/reels_business_rules.yaml
echo "Ready: .venv/bin/video-reels run input.mp4 --rules examples/facebook_reels/reels_business_rules.yaml"
