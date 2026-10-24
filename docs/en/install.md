# Installation and launch

This guide covers the 2.2.0 desktop release and installation from source. Process only videos that you own or are licensed to modify and distribute. Before the release is published, use source installation; download links below refer to v2.2.0.

## Desktop downloads

Get files from [GitHub Releases](https://github.com/Hostlife22/video-uniquifier/releases). Each release includes checksums, a CycloneDX software inventory (SBOM) and cosign verification bundles.

| Platform | Archive | FFmpeg |
|---|---|---|
| Linux x86_64 | `video-uniq-gui-2.2.0-x86_64.AppImage` | Bundled static FFmpeg/FFprobe |
| macOS Apple Silicon | `video-uniq-gui-macOS.zip` | Install separately |
| Windows 10/11 | `video-uniq-gui-Windows.zip` | Install separately |

The macOS release is built for Apple Silicon. For Intel Macs and other architectures, install from source or build locally. The Linux tar archive is also available; unlike the AppImage, it needs system FFmpeg.

### Linux

```bash
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-2.2.0-x86_64.AppImage
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
chmod +x video-uniq-gui-2.2.0-x86_64.AppImage
./video-uniq-gui-2.2.0-x86_64.AppImage
```

### macOS

```bash
brew install ffmpeg
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-macOS.zip
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
shasum -a 256 video-uniq-gui-macOS.zip
unzip video-uniq-gui-macOS.zip
mv video-uniq-gui.app /Applications/
open /Applications/video-uniq-gui.app
```

Compare the printed hash with the archive's entry in `SHA256SUMS` before unpacking. The app has an ad-hoc signature, without Apple Developer ID notarization. If Gatekeeper blocks a verified download, use the macOS Privacy & Security settings to approve that app. The workflow does not promise an Intel or universal binary.

### Windows

```powershell
choco install ffmpeg
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-Windows.zip -OutFile video-uniq-gui-Windows.zip
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS -OutFile SHA256SUMS
Get-FileHash video-uniq-gui-Windows.zip -Algorithm SHA256
Expand-Archive video-uniq-gui-Windows.zip -DestinationPath .
.\video-uniq-gui\video-uniq-gui.exe
```

Compare the printed hash with `SHA256SUMS` before extracting. Windows builds are unsigned. If SmartScreen blocks a verified download, review the publisher/source before approving it; an organization's AppLocker or WDAC policy may require administrator approval.

### Verify the release

Do not run an archive whose checksum differs from `SHA256SUMS`. Install cosign separately if you also want to check the GitHub Actions signing identity:

```bash
cosign verify-blob \
  --bundle video-uniq-gui-2.2.0-x86_64.AppImage.cosign.bundle \
  --certificate-identity-regexp 'https://github\.com/Hostlife22/video-uniquifier/' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  video-uniq-gui-2.2.0-x86_64.AppImage
```

Use the matching `.cosign.bundle` for other assets. The release workflow verifies these signatures before creating its draft. `sbom.cdx.json` and the per-bundle SBOM files describe the packaged components; they do not certify the absence of vulnerabilities.

## System requirements

Source installation needs Python 3.11 or newer, FFmpeg and FFprobe on `PATH`. CI tests Python 3.11 and 3.12 on Linux, macOS and Windows. Encoding time, memory and working disk depend on duration, resolution, codec and enabled transforms.

Install FFmpeg with Homebrew on macOS (`brew install ffmpeg`), APT on Debian/Ubuntu (`sudo apt install ffmpeg`) or Chocolatey on Windows (`choco install ffmpeg`). Check the actual build:

```bash
ffmpeg -version
ffprobe -version
ffmpeg -filters
```

Optional capabilities include `libvmaf` for registered-reference quality measurements, `zscale` for HDR processing, `rubberband` for the corresponding audio transform, and Chromaprint's `fpcalc` for audio fingerprints. A missing required filter must be resolved or the corresponding transform disabled.

## Install from source

```bash
git clone https://github.com/Hostlife22/video-uniquifier.git
cd video-uniquifier
```

On macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,gui]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,gui]"
```

For CLI-only use, install `-e .`. The `[gui]` extra adds PyQt6 and WebEngine; `[dev,gui]` also installs the developer tools. Optional `[web]`, `[ml]` and `[scene]` extras enable the HTTP interface, SSCD and scene detection respectively.

```bash
video-uniq --version
video-uniq probe --encoders
video-uniq-gui --version
```

Both version commands should report `2.2.0` for this release checkout. Encoder discovery performs real capability probes; the first call can take several seconds.

## First CLI run

Start with a short authorized clip and a conservative profile:

```bash
video-uniq probe /path/to/master.mp4
video-uniq preflight /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml
video-uniq run /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml \
  --out /tmp/derivative.mp4 --encoder libx264
```

Review the output and its QA report. Profiles live in `src/video_uniquifier/profiles/`; Reels business-rule examples live in `examples/facebook_reels/`. See the [CLI quick start](getting-started.md) and [Reels guide](facebook-reels.md).

## First desktop run

```bash
video-uniq-gui
```

Choose a source, destination and profile, run preflight, then process the clip. Review playback and the QA report before using the result. The **Video delivery** workspace provides the Reels source → settings → result workflow. See the [desktop walkthrough](gui-walkthrough.md) for all eleven screens.

## Tests and local builds

The Makefile is the canonical developer interface. Integration tests use real FFmpeg; the full suite can take tens of minutes depending on the installed extras and hardware.

```bash
make lint
make typecheck
make test-unit
make test-integration
make check
```

Build the Python wheel or desktop bundle:

```bash
make build-wheel
make build
```

The wheel is written to `dist/`. Desktop outputs are `dist/video-uniq-gui.app` on macOS, `dist/video-uniq-gui/video-uniq-gui.exe` on Windows and `dist/video-uniq-gui/video-uniq-gui` on Linux. Build on the target operating system.

To preview all three documentation languages:

```bash
python -m pip install -e ".[docs,docs-test]"
make docs-build
make docs-serve
```

## Update and uninstall

Update a clean source checkout:

```bash
git pull --ff-only
python -m pip install -e ".[dev,gui]" --upgrade
```

Remove the Python package from its active environment:

```bash
python -m pip uninstall video-uniquifier
```

You can then remove that project's `.venv` if it is no longer needed. Keep exports, profiles and corpus data that you want to retain.

## Shared resource admission

CLI, GUI, web and queue workers coordinate estimated encoder slots and disk demand through a shared writable directory. For cooperating processes, choose one absolute path and use the same service account:

```bash
export VIDEO_UNIQ_RESOURCE_LOCK_DIR=/shared/video-work/resource-admission
```

Docker defaults to `/data/work/.resource-admission`; cooperating containers need the same `/data/work` mount. Do not delete the registry during encoding. Stop all workers before resetting it after hardware or capacity changes. This is admission control based on estimates; use filesystem quotas when a hard disk limit is required. Network filesystems, different UIDs and mixed `CUDA_VISIBLE_DEVICES` configurations remain unverified.

The FFmpeg no-output watchdog defaults to 600 seconds. `VIDEO_UNIQ_STALL_TIMEOUT_SEC=0` disables it; `VIDEO_UNIQ_WALL_TIMEOUT_SEC` can add a hard per-process time limit and is disabled by default.

## Troubleshooting

- **FFmpeg not found:** check `PATH`, or set the absolute `VIDEO_UNIQ_FFMPEG` and `VIDEO_UNIQ_FFPROBE` paths.
- **PyQt6 missing:** install the `[gui]` extra in the environment used to launch the app.
- **Embedded QA viewer unavailable:** use **Open in browser**; WebEngine is optional in headless runs.
- **Linux xcb plugin missing:** install the required system libraries:

```bash
sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
  libxkbcommon-x11-0 libgl1
```

- **HDR/rubberband filter missing on Homebrew:** inspect the installed filters. A full build can be selected explicitly:

```bash
brew install ffmpeg-full
export VIDEO_UNIQ_FFMPEG="$(brew --prefix ffmpeg-full)/bin/ffmpeg"
export VIDEO_UNIQ_FFPROBE="$(brew --prefix ffmpeg-full)/bin/ffprobe"
```

- **Wayland drag-and-drop unavailable:** use **Browse…** or launch with `QT_QPA_PLATFORM=xcb` when XWayland is available.
- **Encoder discovery needs a refresh:** use **Settings → Reset encoder cache** after changing the FFmpeg build or GPU environment.

See [profiles](profiles.md), [security](security.md) and the [documentation index](documentation.md) for further configuration.
