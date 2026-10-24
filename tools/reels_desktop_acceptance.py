#!/usr/bin/env python3
"""Capture real Qt delivery pages after a source -> sample -> export acceptance.

Run from the repository root with the GUI and scene extras installed:
  .venv/bin/python tools/reels_desktop_acceptance.py
Uses isolated desktop preferences and synthetic, repository-owned footage.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget

from video_uniquifier.core.reels.runtime import json_object
from video_uniquifier.gui import state as state_module
from video_uniquifier.gui.app_pyqt import MainWindow
from video_uniquifier.gui.i18n import install_translator
from video_uniquifier.gui.widgets.encoder_selector import EncoderSelector


def wait_for(app: QApplication, predicate, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError("Desktop acceptance timed out")
        app.processEvents()
        time.sleep(.02)
    app.processEvents()


def capture(app: QApplication, window: QWidget, path: Path) -> None:
    for _ in range(12):
        app.processEvents()
        time.sleep(.025)
    assert window.grab().save(str(path)), path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("out/reels-acceptance-20261023/source-10s.mp4"))
    parser.add_argument("--out", type=Path, default=Path("out/reels-desktop-acceptance"))
    parser.add_argument("--screenshots", type=Path, default=Path("docs/screenshots"))
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error("Generate synthetic footage first: tools/reels_acceptance.py")
    args.out.mkdir(parents=True, exist_ok=True)
    args.screenshots.mkdir(parents=True, exist_ok=True)
    preferences = args.out / "preferences"
    state_module.CONFIG_DIR = preferences
    state_module.STATE_PATH = preferences / "state.json"
    state_module.HISTORY_PATH = preferences / "history.json"
    EncoderSelector._start_detection = lambda self: None
    app = QApplication([])
    install_translator(app, "zh_CN")
    window = MainWindow()
    window.state.set_theme("dark")
    window.resize(1180, 800)
    window._navigate_to("Reels")
    window.show()
    page = window.stack.currentWidget()
    try:
        page.input_picker.set_path(args.source.resolve())
        wait_for(app, lambda: page.probe_worker is None)
        assert page.source_meta is not None
        page.output_folder.setText(str((args.out / "exports").resolve()))
        page.options.resolution.setCurrentIndex(1)
        capture(app, window, args.screenshots / "delivery-source-zh.png")
        page.navigation.setCurrentIndex(1)
        capture(app, window, args.screenshots / "delivery-settings-zh.png")
        for mode in ("preflight", "sample", "export"):
            page._start(mode)
            wait_for(app, lambda: page.worker is None)
            assert window.stack.currentWidget() is page, "Background work changed the route"
            assert not page.feedback.property("error"), page.details_text.toPlainText()
            if mode == "sample":
                page.safe_btn.click()
                capture(app, window, args.screenshots / "delivery-preview-zh.png")
        assert page.result_directory is not None
        report = json_object(page.result_directory / "report.json")
        assert report["quality_check"]["status"] == "passed"
        assert page.scene_table.rowCount() > 0
        review = page._compare_dialog
        assert review is not None and review.isVisible()
        wait_for(app, lambda: all(frame.isValid() for frame in review._frames))
        review.seek(1000)
        wait_for(app, lambda: all(stamp >= 950000 for stamp in review._frame_times))
        capture(app, review, args.screenshots / "delivery-comparison-zh.png")
        page.open_video_btn.click()
        playback = page._compare_dialog
        assert playback is not None and playback is not review
        wait_for(app, lambda: playback._frames[1].isValid())
        assert playback.players[0].source().isEmpty()
        capture(app, playback, args.screenshots / "delivery-playback-zh.png")
        assert page._close_comparison()
        page.open_report_btn.click()
        quality_dialog = page._report_dialog
        assert quality_dialog is not None and quality_dialog.isVisible()
        assert quality_dialog.comparison.rowCount() == 10
        capture(app, quality_dialog, args.screenshots / "delivery-quality-comparison-zh.png")
        quality_dialog.tabs.setCurrentIndex(1)
        capture(app, quality_dialog, args.screenshots / "delivery-quality-checks-zh.png")
        quality_dialog.close()
        capture(app, window, args.screenshots / "delivery-result-zh.png")
        window.resize(980, 640)
        capture(app, window, args.screenshots / "delivery-small-zh.png")
        window.state.set_theme("light")
        page.navigation.setCurrentIndex(1)
        capture(app, window, args.screenshots / "delivery-light-zh.png")
        window.state.set_theme("dark")
        window.resize(1180, 800)
        window._navigate_to("Run")
        capture(app, window, args.screenshots / "processing-source-zh.png")
        window.stack.currentWidget().workflow_navigation.setCurrentIndex(1)
        capture(app, window, args.screenshots / "processing-settings-zh.png")
        evidence = {"output": str(page.result_directory), "platform": QApplication.platformName(),
                    "quality": report["quality_check"], "scenes": page.scene_table.rowCount(),
                    "screenshots": str(args.screenshots.resolve())}
        (args.out / "acceptance.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        window.close()
        app.processEvents()


if __name__ == "__main__":
    main()
