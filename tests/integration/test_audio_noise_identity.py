"""Noise overlay must preserve speaker signals and replay the fixed run seed."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from video_uniquifier.core.models import EncoderCandidate, Plan, Profile, TransformConfig
from video_uniquifier.core.pipeline import build_main_audio_command, compute_plan_hash
from video_uniquifier.core.probe import probe
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin


@pytest.mark.integration
@pytest.mark.parametrize("layout,channels", [("stereo", 2), ("5.1", 6)])
def test_noise_preserves_distinct_speaker_signals_and_fixed_seed(
    tmp_path: Path, layout: str, channels: int,
) -> None:
    source = tmp_path / "speakers.mkv"
    frequencies = [400, 600, 800, 80, 1000, 1200][:channels]
    expressions = "|".join(f"0.2*sin(2*PI*{frequency}*t)" for frequency in frequencies)
    subprocess.run([
        ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i",
        f"aevalsrc='{expressions}':s=48000:d=2:c={layout}",
        "-c:a", "flac", str(source),
    ], check=True, capture_output=True, timeout=30)
    metadata = probe(source)
    profile = Profile(name="noise-identity", seed_strategy="fixed", seed=11, transforms=[
        TransformConfig(id="audio.noise_overlay", params={"noise_db": -20.0}),
    ])
    encoder = EncoderCandidate(name="libx264", vendor="x264", codec="h264", works=True)
    plan = Plan(source=metadata, profile=profile, encoder=encoder,
                plan_hash=compute_plan_hash(metadata, profile, encoder), run_seed=11)
    decoded = []
    for number in range(2):
        output = tmp_path / f"output-{number}.m4a"
        command, _ = build_main_audio_command(plan, output)
        subprocess.run(command.args, check=True, capture_output=True, timeout=30)
        result = subprocess.run([
            ffmpeg_bin(), "-v", "error", "-i", str(output), "-t", "1.5",
            "-c:a", "pcm_f32le", "-f", "f32le", "-",
        ], check=True, capture_output=True, timeout=30)
        data = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, channels)
        spectrum = np.abs(np.fft.rfft(data, axis=0))
        frequency_grid = np.fft.rfftfreq(len(data), 1 / 48000)
        peaks = frequency_grid[spectrum.argmax(axis=0)]
        assert peaks.tolist() == pytest.approx(frequencies, abs=2)
        assert probe(output).audio[0].channel_layout == layout
        decoded.append(data)
    # Same seed means identical generated noise and encoded speaker samples.
    assert np.array_equal(decoded[0], decoded[1])
