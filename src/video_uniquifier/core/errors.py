"""Typed exceptions used across the core."""


class VideoUniquifierError(Exception):
    """Base for all video-uniquifier errors."""


class ProbeError(VideoUniquifierError):
    """ffprobe failed or returned data we cannot interpret."""


class EncoderError(VideoUniquifierError):
    """Encoder detection or selection failed."""


class FfmpegNotFoundError(VideoUniquifierError):
    """ffmpeg or ffprobe binary is not on PATH."""


class PipelineError(VideoUniquifierError):
    """Filter graph construction or ffmpeg run failed."""


class CheckpointError(VideoUniquifierError):
    """Checkpoint state is corrupt or incompatible."""


class PreflightFailure(VideoUniquifierError):
    """A preflight finding with severity=fail was raised."""
