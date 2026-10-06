# video-uniquifier — headless web UI image (v0.9.0 R4 / F13).
#
# Two-stage build keeps the runtime layer free of Python build toolchains.
# FFmpeg comes from the same Debian release as the Python runtime, avoiding
# cross-libc copies while retaining native amd64/arm64 package support.
#
# Build:
#   docker build -t video-uniquifier:2.1.2 .
#
# Run (LAN-trusted; no auth):
#   docker run --rm -p 8080:8080 \
#       -v $PWD/input:/data/input:ro \
#       -v $PWD/output:/data/output \
#       -v $PWD/work:/data/work \
#       video-uniquifier:2.1.2
#
# Run (with basic auth):
#   docker run --rm -p 8080:8080 \
#       -e VIDEO_UNIQ_WEB_USER=alice -e VIDEO_UNIQ_WEB_PASS=hunter2 \
#       -v $PWD/input:/data/input:ro \
#       -v $PWD/output:/data/output \
#       video-uniquifier:2.1.2
#
# The [ml] / [scene] extras are deliberately NOT installed here —
# torch alone would push the image past 1 GB. Bake your own image
# with `pip install video-uniquifier[ml]` inside the runtime stage if
# you need SSCD/PySceneDetect on the container.

# v1.1.0 Task 12: multi-arch image. The official Python base resolves to
# linux/amd64 and linux/arm64. Debian installs the matching FFmpeg package
# for each Buildx platform leg.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ---- Build stage: wheels only, no system tools in final layer ----
FROM ${PYTHON_IMAGE} AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip wheel && \
    pip wheel --wheel-dir /wheels '.[web]'

# ---- Runtime stage ---------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# Install FFmpeg and its shared libraries from the runtime distribution.
# This is architecture-correct on both Buildx targets and avoids mixing
# Alpine/musl binaries with Debian/glibc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libssl3 ca-certificates curl tini && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --shell /usr/sbin/nologin --uid 1000 videouniq && \
    mkdir -p /data/input /data/output /data/work /data/profiles && \
    chown -R videouniq:videouniq /data

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels 'video-uniquifier[web]' && \
    rm -rf /wheels && \
    ffmpeg -version >/dev/null && \
    ffprobe -version >/dev/null && \
    python -c "import fastapi, uvicorn; from video_uniquifier.web.app import build_app"

USER videouniq
WORKDIR /home/videouniq

ENV VIDEO_UNIQ_WEB_HOST=0.0.0.0 \
    VIDEO_UNIQ_WEB_PORT=8080 \
    VIDEO_UNIQ_WEB_WORK_DIR=/data/work \
    VIDEO_UNIQ_WEB_OUTPUT_DIR=/data/output \
    VIDEO_UNIQ_WEB_INPUT_ROOT=/data/input \
    VIDEO_UNIQ_RESOURCE_LOCK_DIR=/data/work/.resource-admission \
    PYTHONUNBUFFERED=1

VOLUME ["/data/input", "/data/output", "/data/work"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent --show-error http://localhost:8080/healthz || exit 1

# tini reaps zombie ffmpeg subprocesses if the container is killed
# mid-encode; without it Docker prints "Cannot kill container" warnings.
ENTRYPOINT ["/usr/bin/tini", "--", "video-uniq-web"]
