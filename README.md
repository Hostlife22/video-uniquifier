# video-uniquifier

Video processing and re-encoding for content you own or are licensed to use.
Preview changes, compare the result with the original, and process individual
videos or batches through a desktop app, CLI, or web interface.

**Source version: 2.1.2** ·
[Downloads](https://github.com/Hostlife22/video-uniquifier/releases) ·
[Documentation](https://hostlife22.github.io/video-uniquifier/) ·
[Release notes](./CHANGELOG.md)

![Video Uniquifier — dark studio desktop interface](./docs/screenshots/run-screen-en.png)

## Features

### Desktop workspace

- Large video player with playback, seeking, sound controls, and switching between
  the source and completed output. Source details include resolution, frame rate,
  duration, codec, and HDR status.
- A settings inspector beside the preview, with compact Gentle / Medium / Strong
  profile cards and expandable descriptions of their picture and sound changes.
- Resizable preview, settings, result, and log panels. Panel sizes and table layouts
  are remembered between sessions; primary processing actions stay visible.
- Stage-specific progress, elapsed time, and remaining-time estimates when enough
  measurements are available. A global activity banner lets you follow active tasks
  while visiting other pages.
- Dark studio and light themes, English and Russian localization, keyboard
  navigation, and a reduced-motion setting. Each page includes contextual help
  through **How to use** or **F1**.

### Samples and before/after comparison

- Process a 10, 15, or 20-second SDR sample before committing to a full encode.
  Choose its start on a thumbnail timeline, enter a timecode, or use the current
  playback position. Save the processed sample as a separate MP4.
- Compare source and result side by side, show either one alone, or drag a divider
  across an SDR frame to inspect differences in the same viewing area.
- Shared playback and seeking, frame stepping, soundtrack selection, synchronized
  zoom/pan, and a 100% view for checking detail at native pixel size.
- Comparison can synchronize by time or map playback by duration for constant
  speed changes. HDR uses native video panels; the SDR sample workflow and raster
  divider are unavailable for HDR sources.

See the [GUI guide](./docs/gui.md) for workspace and comparison controls.

### Video processing

- **Geometry:** controlled crop/rescale, small rotations, optional horizontal
  mirroring, and aspect-ratio fitting through cropping, black padding, or a blurred
  background. Custom canvas fitting avoids source upscaling by default.
- **Picture adjustments:** brightness, contrast, gamma, saturation, added noise,
  and mild sharpening. Each transform has its own validated parameters.
- **Composition:** blend a second owned or licensed video layer, or burn an existing
  subtitle file into the picture. Optional SRT generation uses a separately
  installed `whisper.cpp` executable and model.
- **Timing:** playback-rate changes with matching audio tempo. Experimental
  timestamp-based blackout/drop effects are available for deliberate editorial
  experiments and remain outside the quality-first defaults.
- Transforms are composed into FFmpeg filter graphs. Compatibility checks validate
  their order and reject unsupported combinations before a long encode.

The [transform reference](./docs/transform_reference.md) covers parameters,
ordering, quality costs, and HDR/timing compatibility.

### Audio processing

- Pitch and tempo adjustment, with an optional Rubber Band backend for
  formant-preserving processing when FFmpeg includes `librubberband`.
- Parametric EQ, intermediate resampling, dynamic-range compression, reverb,
  chorus/phaser-style spectral modulation, and generated white, pink, or brown
  noise overlays.
- Stereo widening through a channel delay, with stereo-layout validation.
  Review phase and mono compatibility when using this effect.
- Two-pass EBU R128 loudness normalization with configurable integrated loudness,
  true peak, and loudness range. Normalization runs last in the audio chain.
- Select the first audio track, all tracks, or explicit stream indices. The first
  selected track receives the profile's audio effects; additional tracks are
  preserved or transcoded according to the container and timing requirements.

### Profiles and reproducible variants

- Ready-made Gentle, Medium, and Strong recipes, plus HDR, landscape, vertical,
  square, and AV1 delivery profiles. Output codecs include H.264, HEVC, and AV1;
  supported containers include MP4, MOV, and MKV.
- A desktop profile editor for toggling transforms, editing their JSON parameters,
  inspecting the YAML, and saving a custom recipe. Invalid parameters prevent save;
  overwriting a profile creates a backup.
- Four seed strategies: fixed, per-run, input-path-derived, and per-segment video
  variation. Saved run seeds preserve the chosen random parameters during resume;
  `--new-variant` requests a fresh realization for applicable strategies.
- Community profile browsing and installation through HTTPS, SHA-256 verification,
  and schema validation. Optional Ed25519 signature enforcement adds a catalog
  signing requirement.

See [Profiles](./docs/profiles.md), [Seed strategies](./docs/seed_strategy.md),
and the [community catalog](./docs/marketplace.md).

### Encoders, HDR, and media preservation

- Detect software encoders (`libx264`, `libx265`, `libaom-av1`, `libsvtav1`) and
  hardware candidates from NVIDIA NVENC, Intel QSV, AMD AMF, and Apple VideoToolbox.
  Actual availability depends on the device, drivers, codec, and FFmpeg build;
  detection includes a real encode probe.
- Automatic encoder selection defaults to a quality policy. Explicit balanced and
  speed policies provide alternative priorities; a manually selected encoder is
  validated and fails clearly when unsupported.
- Preserve PQ/HLG HDR through supported 10-bit HEVC workflows, using a linear-light
  wrapper for applicable picture adjustments, or explicitly tonemap HDR to SDR.
  Full static HDR metadata verification is currently limited to `libx265`.
- Preserve supported subtitle streams, audio-track metadata, and chapters according
  to the selected container. Supported speed changes also retime SRT subtitles and
  chapters; incompatible subtitle/data formats are rejected.

See [Profiles](./docs/profiles.md) and
[hardware qualification](./docs/hardware_qualification.md) for requirements and
device-specific validation limits.

### Preflight checks and resumable processing

- Inspect the source and validate the profile, encoder capabilities, stream/container
  mapping, HDR mode, and audio/video timing before processing.
- Split long videos at keyframes, process segments with bounded encoder parallelism,
  and join the result. Optional scene-aware segmentation uses PySceneDetect and
  aligns detected boundaries to keyframes.
- Pause, resume, or cancel a desktop run. Checkpoint files retain completed segment
  state and seeds so interrupted work can resume with the same processing plan.
- Coordinate encoder slots and estimated temporary-disk use across local processes
  sharing the resource registry. This schedules encodes; hard CPU/RAM limits remain
  an operating-system or container setting.
- Validate the final stream/timestamp/color contract and decode the complete primary
  video and all audio streams before publishing the completed output. This final
  correctness check also runs when optional QA reports are disabled.

### Quality reports and local reference matching

- Automatic HTML and JSON reports beside the output, plus standalone comparison of
  an existing source/result pair without another encode. Open reports inside the
  desktop viewer or in a browser.
- Separate assessments for media correctness, perceptual quality, and diagnostic
  similarity. Missing measurements are reported explicitly.
- Visual measurements include sampled perceptual hashes, SSIM, optional VMAF through
  FFmpeg's `libvmaf`, and optional SSCD image embeddings with the ML dependencies.
  Audio diagnostics use Chromaprint when `fpcalc` is installed.
- With the completed processing plan, registered metrics compare the output against
  a lossless replay of the intended transforms, separating encoding loss from
  deliberate picture/timing changes. Reference generation requires temporary space;
  registered VMAF is unavailable for preserved HDR.
- Optional full-track LUFS/true-peak scans and operator-selected VMAF/SSIM quality
  gates. Compatible profiles can also request bounded per-segment VMAF retries.
- A local reference library stores fingerprints in SQLite and supports comparison
  against indexed videos, helping inspect similarities between authorized variants.

See [Quality reports](./docs/qa_report.md), [SSCD](./docs/sscd.md), and
[Reference corpus](./docs/corpus.md). Similarity measurements are local diagnostics;
they do not predict external rights-management decisions or replace viewing and
listening to the output.

### Experimental automatic tuning

- Search a base profile's intensity across representative beginning, middle, and
  end samples, using separate similarity and quality constraints.
- A bounded search keeps the seed and quality backend consistent across trials,
  caches completed measurements, and can reuse them after interruption.
- Inspect trial results in the desktop Auto-tune screen and save the selected recipe.
  If no candidate satisfies both constraints, the result is explicitly marked as
  not converged; full-file processing and review are still required.

See the [calibration workflow](./docs/calibrate.md).

### Batch processing, history, and distributed queues

- Process a directory or selected files, with a choice to continue or stop after an
  individual failure. Follow each file's pending/running/completed/failed status.
- Search history, batch, and queue tables by file/path; filter by status, sort,
  resize/reorder columns, and select visible rows using shared checkbox controls.
- Open files, containing folders, and history reports through row actions or context
  menus. Copy selected paths and revisit completed runs through saved history.
- Run multiple workers against a shared-filesystem queue with atomic leasing,
  heartbeats, stale-job recovery, and fenced result publication. Queue management
  is available through the CLI and desktop dashboard.
- Distributed operation needs a filesystem with the required atomic operations and
  qualification on the actual deployment; it does not require Redis or an external
  queue database.

See [Distributed batch](./docs/distributed.md).

### CLI, web interface, and integrations

- Script source probing, preflight checks, individual/batch encodes, QA, calibration,
  reference-library management, queues, profiles, and subtitle generation through
  `video-uniq`. Each command exposes its options through `--help`.
- Use the optional FastAPI web interface for single-video processing on a local
  server or NAS. It offers profile selection, live progress events, cancellation,
  and HTML/JSON report access through browser and API routes.
- Docker and Compose definitions provide FFmpeg, persistent media/work mounts,
  and configurable resource limits. The web interface covers a smaller workflow
  than the desktop app; see [Web UI & Docker](./docs/web.md).
- Extend video/audio transforms through Python plugins without modifying the core.
  Plugin manifests, capability checks, allowlists, and disable controls are described
  in [Plugins](./docs/plugins.md).
- Configure optional completion/failure notifications through Discord, Slack,
  Telegram, generic webhooks, or SMTP email, with a test action in desktop Settings.
- Optional local telemetry records a summary event per completed or failed run.
  It starts disabled, stays on the device, and offers event export and deletion;
  see [Telemetry](./docs/telemetry.md).

## Install

### Desktop downloads

Choose a published build from
[GitHub Releases](https://github.com/Hostlife22/video-uniquifier/releases).
Desktop bundles include Python and the GUI dependencies.

| Platform | Download | FFmpeg |
| --- | --- | --- |
| Linux x86_64 | AppImage | Included |
| macOS Apple Silicon | macOS ZIP containing the app | Install separately |
| Windows | Windows ZIP containing the executable | Install separately |

See the [installation guide](./docs/install.md) for setup, checksum verification,
first-launch instructions, and installation on Intel Macs.

### From source

Requires Python 3.11+ and `ffmpeg` / `ffprobe` on `PATH`.
On macOS or Linux with `make`:

```bash
git clone https://github.com/Hostlife22/video-uniquifier.git
cd video-uniquifier
make dev PYTHON=python3
make gui
```

Use a Python 3.11+ interpreter for `PYTHON`. Windows setup and optional
dependencies are covered in the [installation guide](./docs/install.md).

## First video

1. Open **Process video**, choose an input, and select where to save the result.
2. Start with **Gentle** and click **Process sample** to review a short fragment.
   Use **Before / after** to compare picture, sound, and synchronization.
3. Click **Start processing** for the full video, then open the result and its
   quality report.

The default sample is 15 seconds; you can choose its start and a 10, 15, or
20-second duration. Sample processing is available for SDR sources.
Each page's **How to use** button, or **F1**, opens its quick guide.
See the [GUI guide](./docs/gui.md) for the full workflow.

### CLI example

From the source checkout on macOS/Linux:

```bash
.venv/bin/video-uniq run input.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml \
  --out output.mp4
```

The run also writes `output.mp4.qa.html` and `output.mp4.qa.json`.
Open the HTML report in a browser to inspect the measurements.
Use `make cli` for available commands, or add `--help` to a command for its options.

## Profiles

| Desktop choice | YAML profile | Use |
| --- | --- | --- |
| Gentle | `soft.yaml` | Mild changes; a starting point for review |
| Medium | `medium.yaml` | More noticeable processing |
| Strong | `aggressive.yaml` | Experimental processing requiring careful review |

Shipped recipes also cover HDR and common delivery formats, including vertical
and square video. See [Profiles](./docs/profiles.md) for the complete list,
transform settings, and instructions for creating your own recipe.

Quality depends on the source and selected transforms. Review a sample and the
full output; diagnostic scores complement visual and listening checks.

## Documentation

- [Web UI & Docker](./docs/web.md) — browser access and container deployment.
- [Quality reports](./docs/qa_report.md) — measurements and their interpretation.
- [Distributed batch](./docs/distributed.md) — processing across multiple machines.
- [Plugins](./docs/plugins.md) — extending the transform registry.
- [API contracts and naming migration](./docs/api-contracts.md) — Python integration
  and compatibility details.
- [Security policy](./SECURITY.md) — reporting vulnerabilities.

The [documentation site](https://hostlife22.github.io/video-uniquifier/)
contains the full reference and workflow guides.

## Development

```bash
make check        # lint, strict type checking, and tests
make test-unit    # fast unit tests
make build        # desktop bundle
make build-wheel  # Python wheel
```

See [Contributing](./CONTRIBUTING.md) for the development workflow, test
requirements, and contribution guidelines. Run `make help` for all targets.

## License

MIT — see [LICENSE](./LICENSE).
