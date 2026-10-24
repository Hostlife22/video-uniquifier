"""Thin cancellable desktop adapter to the same Reels core used by CLI/API."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from PyQt6.QtCore import pyqtSignal

from video_uniquifier.core.reels.config import ReelsRules
from video_uniquifier.core.reels.native import default_profile_path, validate_native_profile
from video_uniquifier.core.reels.packaging import render_layers
from video_uniquifier.core.reels.processor import inspect_source, prepare_plan, process_video
from video_uniquifier.core.reels.runtime import ReelsError, check_cancel, json_object
from video_uniquifier.gui.workers.base import WorkerBase

ReelsMode = Literal["preflight", "sample", "export"]


class ReelsWorker(WorkerBase):
    cancelled = pyqtSignal()
    problem = pyqtSignal(str, str)

    def __init__(self, source: Path, rules: ReelsRules, root: Path, *,
                 mode: ReelsMode = "export", assets: dict[str, Path] | None = None) -> None:
        super().__init__()
        self.source = source
        self.rules = rules.model_copy(deep=True)
        self.root = root
        self.mode = mode
        self.assets = dict(assets or {})

    def run(self) -> None:
        self.started_.emit()
        try:
            with TemporaryDirectory(prefix="reels_gui_assets_") as temporary:
                asset_root = Path(temporary)
                for name, source in self.assets.items():
                    check_cancel(self.cancel_token)
                    # Names are supplied by the desktop form, never by an API upload.
                    if Path(name).name != name or not source.is_file():
                        raise ReelsError("asset_path", "Choose an existing local logo/font file.")
                    if source.stat().st_size > 32 * 1024 * 1024:
                        raise ReelsError("asset_size", "Logo/font exceeds 32 MiB.")
                    shutil.copyfile(source, asset_root / name)
                if self.mode == "preflight":
                    self.progress.emit(0.05, "probing")
                    source_meta = inspect_source(self.source, self.rules)
                    check_cancel(self.cancel_token)
                    _, findings = prepare_plan(source_meta, self.rules, validate_native_profile(
                        default_profile_path()), asset_root)
                    duration = (source_meta.duration_sec - self.rules.scenes.trim_start_sec
                                - self.rules.scenes.trim_end_sec)
                    _, _, warnings = render_layers(self.rules, asset_root, asset_root,
                                                    duration, self.cancel_token)
                    check_cancel(self.cancel_token)
                    self.finished_ok.emit({"mode": self.mode, "findings": findings,
                                           "warnings": warnings, "source": source_meta})
                    return
                effective = self.rules
                sample_warnings: list[str] = []
                if self.mode == "sample":
                    source_meta = inspect_source(self.source, self.rules)
                    raw = self.rules.model_dump(mode="python")
                    duration = (source_meta.duration_sec - self.rules.scenes.trim_start_sec
                                - self.rules.scenes.trim_end_sec)
                    length = min(10.0, duration)
                    raw["scenes"]["trim_end_sec"] += duration - length
                    title = raw["packaging"]["title"]
                    if title["enabled"] and title["start_sec"] >= length:
                        title["enabled"] = False
                        sample_warnings.append(
                            "Title starts after this sample; inspect the full output.",
                        )
                    effective = ReelsRules.model_validate(raw)
                result = process_video(
                    self.source, effective, self.root, asset_root=asset_root,
                    cancel_token=self.cancel_token,
                    on_status=lambda status, fraction: self.progress.emit(fraction, status),
                )
                self.finished_ok.emit({"mode": self.mode, "directory": result,
                                       "report": json_object(result / "report.json"),
                                       "warnings": sample_warnings})
        except Exception as exc:
            if self.cancel_token.is_cancelled() or (
                isinstance(exc, ReelsError) and exc.code == "cancelled"
            ):
                self.cancelled.emit()
            else:
                code = exc.code if isinstance(exc, ReelsError) else "processing_failed"
                self.problem.emit(code, str(exc))
                self.failed.emit(str(exc))
