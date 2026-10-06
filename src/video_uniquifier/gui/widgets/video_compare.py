"""Native media comparison with a shared transport and pixel-size inspection."""

from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QPointF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QFontDatabase,
    QImage,
    QMouseEvent,
    QStandardItemModel,
    QTransform,
)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoFrameFormat
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.a11y import mark
from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.widgets.processing_status import format_duration
from video_uniquifier.gui.widgets.wipe_compare import WipeCompare
from video_uniquifier.gui.workers.frame_step_worker import FrameStepWorker

_QT_MAX_WIDGET_SIZE = 16_777_215


class VideoCompareDialog(QDialog):
    """Two native players; only the selected audio is heard at any moment.

    Time sync preserves presentation time. Duration sync additionally maps
    positions/rates by clip duration for constant-tempo changes. Neither mode
    claims semantic registration across edits or arbitrary temporal transforms.
    """

    sample_selected = pyqtSignal(float)

    def __init__(
        self, source: Path, candidate: Path | None = None, *, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Before / after"))
        self.resize(Metrics.REVIEW_WIDTH, Metrics.REVIEW_HEIGHT)
        self.setMinimumSize(Metrics.REVIEW_MIN_WIDTH, Metrics.REVIEW_MIN_HEIGHT)
        self._playing = False
        self._position = 0
        self._durations = [0, 0]
        self._frame_times = [0, 0]
        self._sizes = [QSize(), QSize()]
        self._paths = [source, candidate]
        self._closed = False
        self._close_requested = False
        self._step_worker: FrameStepWorker | None = None
        self._frame_window: tuple[float, ...] = ()
        self._step_direction = 1
        self._step_position = 0.0
        self._has_error = False
        self._initial_loaded = [False, False]
        self._frames = [QVideoFrame(), QVideoFrame()]
        self._wipe_stamps: tuple[int, int] | None = None
        self._syncing_scroll = False
        self._pan_side: int | None = None
        self._pan_last = QPointF()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        layout.setSpacing(Space.LG)
        title = QLabel(self.tr("Before / after"))
        title.setObjectName("title")
        layout.addWidget(title)
        self.context = QLabel(source.name)
        self.context.setObjectName("hint")
        self.context.setWordWrap(True)
        layout.addWidget(self.context)

        options = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItem(self.tr("Side by side"), "both")
        self.view_combo.addItem(self.tr("Original only"), "source")
        self.view_combo.addItem(self.tr("Result only"), "candidate")
        if candidate is not None:
            self.view_combo.addItem(self.tr("Draggable divider"), "wipe")
        mark(self.view_combo, "Comparison layout", "Choose which video panels are visible.")
        options.addWidget(self.view_combo)
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItem(self.tr("Fit to window"), "fit")
        self.zoom_combo.addItem("100%", "pixels")
        for zoom in (50, 200, 400):
            self.zoom_combo.addItem(f"{zoom}%", zoom / 100)
        mark(self.zoom_combo, "Video zoom",
             "Fit the image or inspect one video pixel per screen pixel.")
        options.addWidget(self.zoom_combo)
        self.sync_combo = QComboBox()
        self.sync_combo.addItem(self.tr("Sync by time"), "time")
        self.sync_combo.addItem(self.tr("Sync by duration"), "duration")
        mark(self.sync_combo, "Timeline synchronization",
             "Use shared time or match clip durations.")
        options.addWidget(self.sync_combo)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem(self.tr("Listen to original"), 0)
        self.audio_combo.addItem(self.tr("Listen to result"), 1)
        mark(self.audio_combo, "Comparison audio", "Listen to one soundtrack at a time.")
        self.audio_combo.setCurrentIndex(1 if candidate is not None else 0)
        options.addWidget(self.audio_combo)
        layout.addLayout(options)

        self.image_stack = QStackedWidget()
        pair = QWidget()
        images = QHBoxLayout(pair)
        images.setContentsMargins(0, 0, 0, 0)
        images.setSpacing(Space.LG)
        self.players: list[QMediaPlayer] = []
        self.outputs: list[QAudioOutput] = []
        self.videos: list[QVideoWidget] = []
        self.panels: list[QWidget] = []
        self.areas: list[QScrollArea] = []
        self.frame_labels: list[QLabel] = []
        for index, name in enumerate(("Original", "Processed")):
            panel = QWidget()
            column = QVBoxLayout(panel)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(Space.SM)
            heading = QLabel(self.tr(name))
            heading.setObjectName("section_title")
            column.addWidget(heading)
            area = QScrollArea()
            area.setAlignment(Qt.AlignmentFlag.AlignCenter)
            area.setWidgetResizable(True)
            area.setMinimumHeight(Metrics.REVIEW_VIDEO_HEIGHT)
            video = QVideoWidget()
            video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            video.setAccessibleName(self.tr(name))
            area.setWidget(video)
            video.installEventFilter(self)
            viewport = area.viewport()
            if viewport is not None:
                viewport.installEventFilter(self)
            for bar in (area.horizontalScrollBar(), area.verticalScrollBar()):
                if bar is not None:
                    bar.valueChanged.connect(lambda _value, side=index: self._sync_pan(side))
            column.addWidget(area, stretch=1)
            frame_label = QLabel()
            frame_label.setObjectName("hint")
            column.addWidget(frame_label)
            images.addWidget(panel, stretch=1)
            player = QMediaPlayer(self)
            audio = QAudioOutput(self)
            audio.setMuted(True)
            audio.setVolume(0.8)
            player.setAudioOutput(audio)
            player.setVideoOutput(video)
            player.durationChanged.connect(
                lambda duration, side=index: self._duration(side, duration),
            )
            player.mediaStatusChanged.connect(
                lambda status, side=index: self._media_status(side, status),
            )
            player.errorOccurred.connect(
                lambda _error, message, side=index: self._error(side, message),
            )
            sink = video.videoSink()
            if sink is not None:
                sink.videoFrameChanged.connect(lambda frame, side=index: self._frame(side, frame))
            self.players.append(player)
            self.outputs.append(audio)
            self.videos.append(video)
            self.panels.append(panel)
            self.areas.append(area)
            self.frame_labels.append(frame_label)
        self.image_stack.addWidget(pair)
        self.wipe = WipeCompare()
        self.image_stack.addWidget(self.wipe)
        layout.addWidget(self.image_stack, stretch=1)

        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.setAccessibleName(self.tr("Shared timeline"))
        self.timeline.sliderMoved.connect(self.seek)
        self.timeline.valueChanged.connect(self._slider_changed)
        layout.addWidget(self.timeline)
        transport = QHBoxLayout()
        self.play_btn = QPushButton(self.tr("Play"))
        self.play_btn.clicked.connect(self.toggle_play)
        mark(self.play_btn, "Play or pause comparison",
             "Play both panels from the shared timeline.")
        transport.addWidget(self.play_btn)
        self.previous_btn = QPushButton(self.tr("Previous frame"))
        self.previous_btn.clicked.connect(lambda: self.step_frame(-1))
        mark(self.previous_btn, "Previous frame", "Pause and move back by one frame interval.")
        transport.addWidget(self.previous_btn)
        self.next_btn = QPushButton(self.tr("Next frame"))
        self.next_btn.clicked.connect(lambda: self.step_frame(1))
        mark(self.next_btn, "Next frame", "Pause and move forward by one frame interval.")
        transport.addWidget(self.next_btn)
        self.select_sample_btn = QPushButton(self.tr("Use this time for sample"), self)
        self.select_sample_btn.clicked.connect(
            lambda: self.sample_selected.emit(self._position / 1000),
        )
        self.select_sample_btn.setVisible(candidate is None)
        self.position_label = QLabel()
        self.position_label.setObjectName("hint")
        self.position_label.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont),
        )
        transport.addWidget(self.position_label)
        transport.addStretch(1)
        layout.addLayout(transport)
        if candidate is None:
            selection = QHBoxLayout()
            selection.addWidget(self.select_sample_btn)
            selection.addStretch(1)
            layout.addLayout(selection)
        self.message = QLabel(self.tr("Loading video…"))
        self.message.setObjectName("hint")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.view_combo.currentIndexChanged.connect(self._view_changed)
        self.zoom_combo.currentIndexChanged.connect(self._zoom_changed)
        self.audio_combo.currentIndexChanged.connect(self._audio_changed)
        self.sync_combo.currentIndexChanged.connect(self._sync_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(Metrics.REVIEW_SYNC_INTERVAL_MS)
        self.timer.timeout.connect(self._sync_tick)
        self.timer.start()
        self.wipe_timer = QTimer(self)
        self.wipe_timer.setInterval(Metrics.WIPE_REFRESH_MS)
        self.wipe_timer.timeout.connect(self._refresh_wipe)
        self.wipe_timer.start()
        if candidate is None:
            self.view_combo.setCurrentIndex(1)
            self.view_combo.setEnabled(False)
            self.sync_combo.setEnabled(False)
            self.audio_combo.setEnabled(False)
        self._view_changed()
        self._update_transport()
        for player, path in zip(self.players, self._paths, strict=True):
            if path is not None:
                player.setSource(QUrl.fromLocalFile(str(path.resolve())))

    @property
    def master_index(self) -> int:
        return 1 if self._paths[1] is not None else 0

    def _limit(self) -> int:
        if self.master_index == 0:
            return self._durations[0]
        if self.sync_combo.currentData() == "duration":
            return self._durations[1]
        return min(self._durations)

    def _reference_position(self, position: int) -> int:
        if self.sync_combo.currentData() == "duration" and self._durations[1] > 0:
            return round(position * self._durations[0] / self._durations[1])
        return position

    def _duration(self, side: int, duration: int) -> None:
        self._durations[side] = duration
        self.timeline.setRange(0, self._limit())
        self._sync_changed()
        self._update_transport()

    def _media_status(self, side: int, status: QMediaPlayer.MediaStatus) -> None:
        if self._closed:
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if self._initial_loaded[side]:
                return
            self._initial_loaded[side] = True
            if self._playing:
                self.players[side].play()
            else:
                # A paused seek decodes a still without queued playback frames
                # advancing the two panels by different amounts at startup.
                QTimer.singleShot(0, lambda: self._initial_still(side))
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.pause()

    def _initial_still(self, side: int) -> None:
        if self._closed or self._playing:
            return
        self.players[side].pause()
        self.players[side].setPosition(1)

    def _frame(self, side: int, frame: QVideoFrame) -> None:
        if self._closed or not frame.isValid():
            return
        self._frame_times[side] = max(0, frame.startTime())
        self._frames[side] = QVideoFrame(frame)
        if frame.surfaceFormat().colorTransfer() in (
            QVideoFrameFormat.ColorTransfer.ColorTransfer_ST2084,
            QVideoFrameFormat.ColorTransfer.ColorTransfer_STD_B67,
        ):
            model = self.view_combo.model()
            if isinstance(model, QStandardItemModel):
                item = model.item(self.view_combo.findData("wipe"))
                if item is not None:
                    item.setEnabled(False)
                    item.setToolTip(self.tr("Use native video panels for HDR comparison."))
            if self.view_combo.currentData() == "wipe":
                self.view_combo.setCurrentIndex(0)
                self.message.setText(self.tr("Use native video panels for HDR comparison."))
        size = frame.size()
        if size != self._sizes[side]:
            self._sizes[side] = size
            self._zoom_changed()
        self.frame_labels[side].setText(
            f"{size.width()} × {size.height()}  ·  "
            f"{format_duration(frame.startTime() / 1_000_000)}."
            f"{max(0, frame.startTime()) // 1000 % 1000:03d}",
        )
        if not self._playing:
            self.players[side].pause()

    def _error(self, side: int, message: str) -> None:
        if self._closed:
            return
        self._has_error = True
        self.pause()
        self.message.setText(self.tr("Could not play {video}: {error}").format(
            video=self.tr("Original" if side == 0 else "Processed"), error=message,
        ))

    def _update_transport(self) -> None:
        ready = self._limit() > 0 and self._step_worker is None and not self._has_error
        for button in (self.play_btn, self.previous_btn, self.next_btn):
            button.setEnabled(ready)
        self.timeline.setEnabled(ready)
        self.select_sample_btn.setEnabled(ready)
        self.position_label.setText(
            f"{format_duration(self._position / 1000)} / {format_duration(self._limit() / 1000)}",
        )

    def _slider_changed(self, value: int) -> None:
        if not self.timeline.isSliderDown():
            self.seek(value)

    def seek(self, position: int) -> None:
        self._position = min(max(position, 0), self._limit())
        self.players[self.master_index].setPosition(self._position)
        if self.master_index == 1:
            self.players[0].setPosition(self._reference_position(self._position))
        previous = self.timeline.blockSignals(True)
        self.timeline.setValue(self._position)
        self.timeline.blockSignals(previous)
        self._update_transport()

    def toggle_play(self) -> None:
        if self._playing:
            self.pause()
            return
        if self._limit() <= 0:
            return
        if self._position >= self._limit() - 1:
            self.seek(0)
        self._playing = True
        self.play_btn.setText(self.tr("Pause"))
        self._audio_changed()
        for player, path in zip(self.players, self._paths, strict=True):
            if path is not None:
                player.play()

    def pause(self) -> None:
        self._playing = False
        for player in self.players:
            player.pause()
        self.play_btn.setText(self.tr("Play"))
        self._audio_changed()

    def step_frame(self, direction: int) -> None:
        self.pause()
        if self._step_worker is not None or direction not in (-1, 1):
            return
        self._step_direction = direction
        self._step_position = self._frame_times[self.master_index] / 1_000_000
        if self._step_from_window():
            return
        path = self._paths[self.master_index]
        if path is None:
            return
        self._step_worker = FrameStepWorker(path, self._step_position)
        self._step_worker.finished_ok.connect(self._step_ready)
        self._step_worker.failed.connect(self._step_failed)
        self._step_worker.finished.connect(self._retry_close)
        self.message.setText(self.tr("Finding the adjacent frame…"))
        self._step_worker.start()
        self._update_transport()

    def _step_from_window(self) -> bool:
        if (not self._frame_window
                or self._step_position < self._frame_window[0] - 0.001
                or self._step_position > self._frame_window[-1] + 0.001):
            return False
        matches = [stamp for stamp in self._frame_window
                   if (stamp - self._step_position) * self._step_direction > 0.000005]
        if not matches:
            return False
        target = min(matches) if self._step_direction > 0 else max(matches)
        # Seek inside the frame: Qt may present the previous frame at an exact
        # millisecond boundary (e.g. seeking 500 ms presents 458.333 ms).
        self.seek(math.floor(target * 1000) + 1)
        return True

    def _release_step_worker(self) -> None:
        if self._step_worker is not None:
            self._step_worker.wait()
            self._step_worker = None

    def _step_ready(self, frames: object) -> None:
        self._release_step_worker()
        if self._close_requested:
            return
        if isinstance(frames, tuple):
            self._frame_window = tuple(
                float(value) for value in frames
                if isinstance(value, (int, float)) and math.isfinite(value)
            )
        self._step_from_window()
        self._update_transport()
        self.message.setText(self.tr("Frame ready"))

    def _step_failed(self, message: str) -> None:
        self._release_step_worker()
        if not self._close_requested:
            self.message.setText(self.tr("Frame step unavailable: {error}").format(error=message))
            self._update_transport()

    def _retry_close(self) -> None:
        if self._close_requested:
            self.close()

    def _sync_tick(self) -> None:
        if not self._playing or self._closed:
            return
        position = self.players[self.master_index].position()
        if position >= self._limit():
            self.pause()
            return
        self._position = position
        if self.master_index == 1:
            expected = self._reference_position(position)
            if abs(self.players[0].position() - expected) > Metrics.REVIEW_SYNC_TOLERANCE_MS:
                self.players[0].setPosition(expected)
        if not self.timeline.isSliderDown():
            previous = self.timeline.blockSignals(True)
            self.timeline.setValue(position)
            self.timeline.blockSignals(previous)
        self._update_transport()

    def _view_changed(self) -> None:
        mode = self.view_combo.currentData()
        self.image_stack.setCurrentIndex(1 if mode == "wipe" else 0)
        self.panels[0].setVisible(mode in ("source", "both"))
        self.panels[1].setVisible(mode in ("candidate", "both") and self._paths[1] is not None)
        self._refresh_wipe()

    def _zoom_changed(self) -> None:
        mode = self.zoom_combo.currentData()
        factor = (1.0 if mode == "pixels" else float(mode)
                  if isinstance(mode, (int, float)) else None)
        pixels = factor is not None
        for video, area, size in zip(self.videos, self.areas, self._sizes, strict=True):
            area.setWidgetResizable(not pixels)
            if pixels and not size.isEmpty():
                ratio = video.devicePixelRatioF()
                video.setFixedSize(
                    max(1, round(size.width() * (factor or 1) / ratio)),
                    max(1, round(size.height() * (factor or 1) / ratio)),
                )
            else:
                video.setMinimumSize(0, 0)
                video.setMaximumSize(_QT_MAX_WIDGET_SIZE, _QT_MAX_WIDGET_SIZE)
        self.wipe.set_zoom(factor)

    def _refresh_wipe(self) -> None:
        if self._closed or self.view_combo.currentData() != "wipe":
            return
        if not all(frame.isValid() for frame in self._frames):
            return
        stamps = (self._frames[0].startTime(), self._frames[1].startTime())
        if stamps == self._wipe_stamps:
            return
        self._wipe_stamps = stamps
        # Convert only the displayed inspection mode, at a bounded refresh rate.
        images = [self._inspection_image(frame) for frame in self._frames]
        if any(image.isNull() for image in images):
            self.view_combo.setCurrentIndex(0)
            self.message.setText(self.tr("Image comparison unavailable; use side by side."))
            return
        self.wipe.set_images(*images)

    @staticmethod
    def _inspection_image(frame: QVideoFrame) -> QImage:
        image = frame.toImage()
        # QVideoFrame.toImage excludes presentation rotation and mirroring.
        rotation = {
            QVideoFrame.RotationAngle.Rotation0: 0,
            QVideoFrame.RotationAngle.Rotation90: 90,
            QVideoFrame.RotationAngle.Rotation180: 180,
            QVideoFrame.RotationAngle.Rotation270: 270,
        }[frame.rotationAngle()]
        if rotation:
            image = image.transformed(QTransform().rotate(rotation))
        if frame.mirrored():
            image = image.mirrored(True, False)
        return image

    def _sync_pan(self, side: int) -> None:
        if self._syncing_scroll or self.master_index == 0:
            return
        self._syncing_scroll = True
        try:
            source, target = self.areas[side], self.areas[1 - side]
            for first, second in (
                (source.horizontalScrollBar(), target.horizontalScrollBar()),
                (source.verticalScrollBar(), target.verticalScrollBar()),
            ):
                if first is not None and second is not None:
                    second.setValue(
                        round(first.value() / max(first.maximum(), 1) * second.maximum()),
                    )
        finally:
            self._syncing_scroll = False

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if isinstance(event, QMouseEvent) and self.zoom_combo.currentData() != "fit":
            for side, (video, area) in enumerate(zip(self.videos, self.areas, strict=True)):
                if obj not in (video, area.viewport()):
                    continue
                if (event.type() == QEvent.Type.MouseButtonPress
                        and event.button() == Qt.MouseButton.LeftButton):
                    self._pan_side = side
                    self._pan_last = event.globalPosition()
                    return True
                if event.type() == QEvent.Type.MouseMove and self._pan_side == side:
                    delta = event.globalPosition() - self._pan_last
                    self._pan_last = event.globalPosition()
                    for bar, distance in ((area.horizontalScrollBar(), delta.x()),
                                          (area.verticalScrollBar(), delta.y())):
                        if bar is not None:
                            bar.setValue(bar.value() - round(distance))
                    return True
                if event.type() == QEvent.Type.MouseButtonRelease:
                    self._pan_side = None
                    return True
        return super().eventFilter(obj, event)

    def _audio_changed(self) -> None:
        selected = self.audio_combo.currentData()
        for side, output in enumerate(self.outputs):
            output.setMuted(not self._playing or selected != side)

    def _sync_changed(self) -> None:
        ratio = 1.0
        if (self.sync_combo.currentData() == "duration"
                and all(duration > 0 for duration in self._durations)):
            ratio = self._durations[0] / self._durations[1]
        self.players[0].setPlaybackRate(ratio)
        self.timeline.setRange(0, self._limit())
        if not self._has_error:
            self.message.setText(self.tr(
                "Shared time; choose duration sync when the clip tempo changes.",
            ))
        self.seek(self._position)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if self._closed:
            super().closeEvent(event)
            return
        self._close_requested = True
        if self._step_worker is not None:
            self._step_worker.request_cancel()
            if not self._step_worker.wait(1000):
                if event is not None:
                    event.ignore()
                return
            self._step_worker = None
        self._closed = True
        # Children emit widget events during destruction. Detach panning
        # filters before Qt tears down the Python-backed dialog callbacks.
        for video, area in zip(self.videos, self.areas, strict=True):
            video.removeEventFilter(self)
            viewport = area.viewport()
            if viewport is not None:
                viewport.removeEventFilter(self)
        for player, video in zip(self.players, self.videos, strict=True):
            player.durationChanged.disconnect()
            player.mediaStatusChanged.disconnect()
            player.errorOccurred.disconnect()
            sink = video.videoSink()
            if sink is not None:
                sink.videoFrameChanged.disconnect()
        self.timer.stop()
        self.wipe_timer.stop()
        self._frames = [QVideoFrame(), QVideoFrame()]
        self.pause()
        for player in self.players:
            player.stop()
            player.setSource(QUrl())
            player.setVideoOutput(None)
            player.setAudioOutput(None)
        super().closeEvent(event)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.setWindowTitle(self.tr("Before / after"))
            if hasattr(self, "play_btn"):
                self.play_btn.setText(self.tr("Pause" if self._playing else "Play"))
                self.previous_btn.setText(self.tr("Previous frame"))
                self.next_btn.setText(self.tr("Next frame"))
                self.select_sample_btn.setText(self.tr("Use this time for sample"))
                for index, source in enumerate((
                    "Side by side", "Original only", "Result only", "Draggable divider",
                )):
                    if index < self.view_combo.count():
                        self.view_combo.setItemText(index, self.tr(source))
                self.zoom_combo.setItemText(0, self.tr("Fit to window"))
                for index, source in enumerate(("Sync by time", "Sync by duration")):
                    self.sync_combo.setItemText(index, self.tr(source))
                for index, source in enumerate(("Listen to original", "Listen to result")):
                    self.audio_combo.setItemText(index, self.tr(source))
        super().changeEvent(event)
