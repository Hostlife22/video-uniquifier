# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for video-uniq-gui (v0.5.4).
#
# Build:
#   pip install pyinstaller
#   pyinstaller pyinstaller/video-uniq-gui.spec --clean
#
# Output:
#   dist/video-uniq-gui.app          (macOS bundle)
#   dist/video-uniq-gui/             (Windows / Linux dir distribution)
#
# Caveats:
# - Unsigned. macOS Gatekeeper / Windows SmartScreen will warn on first launch.
# - PyQt6-WebEngine pulls ~150 MB of Chromium; resulting bundle is large.
# - Optional ML/web/scene/observability stacks are deliberately excluded. Their
#   availability in a developer venv must not change the release artifact.
# - If your platform fails, fall back to: pipx install 'video-uniquifier[gui]'

import sys
from importlib.metadata import version
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

APP_VERSION = version("video-uniquifier")

# Bundle GUI resources, including the offline catalog and verification keys.
datas = []
datas += copy_metadata("video-uniquifier")
for subdir in ("profiles", "core/qa/templates", "marketplace", "keys", "gui/assets"):
    datas += collect_data_files("video_uniquifier", subdir=subdir, include_py_files=False)

# Transforms self-register on import via core/transforms/__init__.py. The
# init imports every submodule by name so PyInstaller should follow them,
# but be explicit so an empty registry — which would crash any encode
# with "unknown transform" — can never happen.
hiddenimports = []
hiddenimports += collect_submodules("PyQt6")
hiddenimports += collect_submodules("video_uniquifier.core.transforms")
hiddenimports += collect_submodules("video_uniquifier.gui")

# Note: PyInstaller >= 6 removed the `block_cipher` / `cipher=` parameters.
# Pass nothing rather than `None` so the spec is forward-compatible.
a = Analysis(
    ["../src/video_uniquifier/gui/app_pyqt.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[
        "tests",
        "torch",
        "torchvision",
        "scipy",
        "cv2",
        "scenedetect",
        "fastapi",
        "uvicorn",
        "opentelemetry",
        "mkdocs",
        "pytest",
    ],
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="video-uniq-gui",
    console=False,
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False,
    name="video-uniq-gui",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="video-uniq-gui.app",
        icon=None,
        bundle_identifier="com.video-uniquifier.gui",
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
        },
    )
