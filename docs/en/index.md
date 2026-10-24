# video-uniquifier

Process and re-encode video that you own or are licensed to use. Preview changes, compare source and output, and process single files or batches through a desktop application, CLI or local web interface.

## Start here

- [Install](install.md): Python, native desktop packages, FFmpeg and first launch.
- [Getting started](getting-started.md): inspect a source, validate a profile and encode.
- [Desktop walkthrough](gui-walkthrough.md): sources, samples, settings and results.
- [Video delivery / Reels](facebook-reels.md): a four-step vertical delivery workflow, CLI and HTTP worker, scene timelines and technical quality reports.
- [Web UI and Docker](web.md): run a local browser interface or a container.

```sh
pip install "video-uniquifier[gui] @ git+https://github.com/Hostlife22/video-uniquifier.git@v2.2.0"
python -c "from importlib.resources import files; from pathlib import Path; Path('review-soft.yaml').write_bytes(files('video_uniquifier').joinpath('profiles/soft.yaml').read_bytes())"
video-uniq-gui
video-uniq probe input.mp4
video-uniq preflight input.mp4 --profile review-soft.yaml
video-uniq run input.mp4 --profile review-soft.yaml --out output.mp4
```

Python 3.11+ and FFmpeg/FFprobe on PATH are required for source installs. Optional features need their documented dependencies, including `[scene]` for scene detection.

## Processing and review

- [Profiles](profiles.md) and the [transform reference](transform_reference.md) describe geometry, picture/audio changes, HDR compatibility and validated parameters.
- [Architecture](architecture.md) explains segment-based resume, bounded processing and the shared core used by desktop, CLI and web frontends.
- [Quality reports](qa_report.md) distinguish technical correctness, perceptual measurements and diagnostic similarity. Review the delivered picture and sound.
- [Distributed batch](distributed.md) covers workers sharing an explicitly qualified filesystem; [hardware qualification](hardware_qualification.md) documents device limits.

The application supports English, Russian and Simplified Chinese. The documentation has the same languages: use the selector in the header. See [documentation languages](documentation.md) for source layout and contribution checks.

!!! warning "Authorized content"
    Use your own or licensed media. Local similarity measurements do not predict
    external rights-management decisions. The project does not provide guarantees
    of Content ID evasion, platform originality classification or publishing reach.
