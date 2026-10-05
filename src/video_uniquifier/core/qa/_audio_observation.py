"""Experimental PCM observations; no listening verdict or speaker identity claim."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


@dataclass(frozen=True)
class ChannelObservation:
    sample_peak: float
    rms: float
    dc_offset: float
    samples_at_or_above_full_scale: int
    silence_fraction: float


@dataclass(frozen=True)
class AudioObservation:
    sample_rate: int
    samples: int
    channels: tuple[ChannelObservation, ...]
    stereo_correlation: float | None
    mono_energy_ratio: float | None
    mono_attenuation_db: float | None
    complete_mono_cancellation: bool | None
    scope: str = "PCM window only; sample peak is not true peak or a listening verdict"


def observe_pcm(data: NDArray[np.float64], *, sample_rate: int) -> AudioObservation:
    """Observe at native sample rate; accept at most sixty seconds of finite PCM.

    Only two-channel signals use equal-weight mono summation. Multichannel
    downmix requires known speaker labels and weights, unavailable here.
    """
    import numpy as np

    if (isinstance(sample_rate, bool) or sample_rate <= 0 or data.ndim != 2
            or not 0 < len(data) <= sample_rate * 60 or not 1 <= data.shape[1] <= 32):
        raise ValueError("invalid bounded PCM window")
    if not np.isfinite(data).all():
        raise ValueError("nonfinite PCM")
    channels = tuple(
        ChannelObservation(
            sample_peak=float(np.max(np.abs(channel))),
            rms=float(np.sqrt(np.mean(channel ** 2))),
            dc_offset=float(np.mean(channel)),
            samples_at_or_above_full_scale=int(np.count_nonzero(np.abs(channel) >= 1)),
            silence_fraction=float(np.mean(np.abs(channel) <= 1e-6)),
        )
        for channel in data.T
    )
    correlation: float | None = None
    ratio: float | None = None
    attenuation: float | None = None
    cancellation: bool | None = None
    if data.shape[1] == 2:
        left, right = data.T
        if float(np.std(left)) > 1e-9 and float(np.std(right)) > 1e-9:
            correlation = float(np.clip(np.corrcoef(left, right)[0, 1], -1, 1))
        input_energy = sum(channel.rms ** 2 for channel in channels) / 2
        if input_energy > 1e-18:
            ratio = float(np.mean(((left + right) / 2) ** 2)) / input_energy
            cancellation = ratio == 0
            attenuation = 10 * math.log10(ratio) if ratio > 0 else None
    return AudioObservation(sample_rate, len(data), channels, correlation, ratio,
                            attenuation, cancellation)
