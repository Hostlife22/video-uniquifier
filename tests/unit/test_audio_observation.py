"""PCM measurements distinguish silence, inversion and actual sample overload."""

import json
from dataclasses import asdict

import numpy as np
import pytest

from video_uniquifier.core.qa._audio_observation import observe_pcm


def test_antiphase_audio_cancels_in_mono() -> None:
    wave = np.sin(np.arange(800) * 0.12) * 0.5
    result = observe_pcm(np.column_stack((wave, -wave)), sample_rate=8000)
    assert result.stereo_correlation == pytest.approx(-1)
    assert result.mono_energy_ratio == 0
    assert result.complete_mono_cancellation is True
    assert result.mono_attenuation_db is None
    json.dumps(asdict(result), allow_nan=False)


def test_identical_stereo_preserves_mono_energy() -> None:
    wave = np.sin(np.arange(800) * 0.12) * 0.5
    result = observe_pcm(np.column_stack((wave, wave)), sample_rate=8000)
    assert result.stereo_correlation == pytest.approx(1)
    assert result.mono_energy_ratio == pytest.approx(1)
    assert result.mono_attenuation_db == pytest.approx(0)


def test_silence_is_not_a_phase_measurement() -> None:
    result = observe_pcm(np.zeros((800, 2)), sample_rate=8000)
    assert result.stereo_correlation is None
    assert result.mono_energy_ratio is None
    assert result.complete_mono_cancellation is None
    assert result.channels[0].silence_fraction == 1


def test_native_sample_overload_and_dc_are_not_lost_to_downsampling() -> None:
    signal = np.zeros((800, 1))
    signal[111, 0] = 1.2
    result = observe_pcm(signal, sample_rate=8000)
    assert result.channels[0].sample_peak == 1.2
    assert result.channels[0].samples_at_or_above_full_scale == 1
    assert result.channels[0].dc_offset == pytest.approx(1.2 / 800)


def test_surround_has_channel_observations_without_invented_downmix() -> None:
    result = observe_pcm(np.ones((800, 6)) * 0.1, sample_rate=8000)
    assert len(result.channels) == 6
    assert result.mono_energy_ratio is None
    assert result.stereo_correlation is None


@pytest.mark.parametrize("signal,rate", [
    (np.zeros((0, 2)), 8000), (np.zeros((800,)), 8000),
    (np.zeros((800, 2)), 0), (np.zeros((800, 2)), True),
    (np.zeros((61, 2)), 1), (np.full((800, 2), np.nan), 8000),
    (np.full((800, 2), np.inf), 8000),
])
def test_invalid_pcm_rejected(signal, rate) -> None:
    with pytest.raises(ValueError):
        observe_pcm(signal, sample_rate=rate)
