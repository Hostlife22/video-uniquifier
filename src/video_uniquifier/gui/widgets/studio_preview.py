"""Native, paused-by-default source/result player for the main workspace."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QHideEvent, QShowEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.widgets.sample_timeline import timecode


class StudioPreview(QWidget):
    sample_selected = pyqtSignal(object, float)

    def __init__(self) -> None:
        super().__init__()
        self._paths: list[Path | None] = [None, None]
        self._closed = False
        self._error = False
        self._initial_loaded = False
        self._priming = False
        self._frame = QVideoFrame()
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.75)
        self.player.setAudioOutput(self.audio)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        layout.setSpacing(Space.SM)
        modes = QHBoxLayout()
        self.track = QComboBox()
        self.track.setProperty("compact", True)
        self.track.setAccessibleName(self.tr("Preview track"))
        self.track.addItem(self.tr("Original"), 0)
        self.track.addItem(self.tr("Processed"), 1)
        self.track.currentIndexChanged.connect(self._load_track)
        modes.addWidget(self.track)
        self.select_sample = QPushButton(self.tr("Set sample start"))
        self.select_sample.setAccessibleName(self.tr("Set sample start"))
        self.select_sample.clicked.connect(self._select_sample)
        modes.addWidget(self.select_sample)
        modes.addStretch(1)
        layout.addLayout(modes)
        self.stage = QStackedWidget()
        self.stage.setObjectName("video_stage")
        self.stage.setMinimumHeight(Metrics.PREVIEW_MIN_HEIGHT)
        self.empty = QLabel(self.tr("Choose a video to preview it here."))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName("hint")
        self.video = QVideoWidget()
        self.video.setMinimumSize(0, 0)
        self.video.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.player.setVideoOutput(self.video)
        sink = self.video.videoSink()
        assert sink is not None
        self.sink = sink
        sink.videoFrameChanged.connect(self._video_frame)
        self.stage.addWidget(self.empty)
        self.stage.addWidget(self.video)
        layout.addWidget(self.stage, stretch=1)
        transport = QHBoxLayout()
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_button)
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 0)
        self.seek_bar.setAccessibleName(self.tr("Preview timeline"))
        self.seek_bar.valueChanged.connect(self.player.setPosition)
        transport.addWidget(self.seek_bar, stretch=1)
        self.sound = QCheckBox(self.tr("Sound"))
        self.sound.setAccessibleName(self.tr("Sound"))
        self.sound.setChecked(True)
        self.sound.toggled.connect(
            lambda checked: self.audio.setMuted(
                self._priming or not checked
                or self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState,
            ),
        )
        transport.addWidget(self.sound)
        layout.addLayout(transport)
        self.position = QLabel()
        self.position.setObjectName("timecode")
        self.position.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self.position)
        self.message = QLabel()
        self.message.setObjectName("hint")
        self.message.setWordWrap(True)
        self.message.hide()
        layout.addWidget(self.message)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.positionChanged.connect(self._position_changed)
        self.player.playbackStateChanged.connect(self._playback_changed)
        self.player.errorOccurred.connect(self._failed)
        self._playback_changed(self.player.playbackState())
        self._update_controls()

    @property
    def current_path(self) -> Path | None:
        return self._paths[self.track.currentIndex()]

    def set_source(self, path: Path | None) -> None:
        self._paths = [path, None]
        self._choose_track(0)

    def set_result(self, path: Path | None) -> None:
        self._paths[1] = path
        self._choose_track(1 if path is not None else 0)

    def _choose_track(self, index: int) -> None:
        blocked = self.track.blockSignals(True)
        self.track.setCurrentIndex(index)
        self.track.blockSignals(blocked)
        self._load_track()

    def _load_track(self, _index: int = 0) -> None:
        if self._closed:
            return
        self.pause()
        self._frame = QVideoFrame()
        self._error = False
        self._initial_loaded = False
        self._priming = False
        self.message.hide()
        path = self.current_path
        available = path is not None and path.is_file()
        url = QUrl.fromLocalFile(str(path.resolve())) if available and path is not None else QUrl()
        self.player.setSource(url)
        self.stage.setCurrentIndex(1 if available else 0)
        self.seek_bar.setValue(0)
        self._position_changed(0)
        self._update_controls()

    def _update_controls(self) -> None:
        ready = self.player.duration() > 0 and not self._error and not self._closed
        self.play_button.setEnabled(ready)
        self.seek_bar.setEnabled(ready)
        self.select_sample.setEnabled(ready and self.track.currentIndex() == 0)
        self._position_changed(self.player.position())

    def _video_frame(self, frame: QVideoFrame) -> None:
        if self._closed or not frame.isValid():
            return
        self._frame = QVideoFrame(frame)
        if self._priming:
            self.pause()

    def _media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if (status == QMediaPlayer.MediaStatus.LoadedMedia and not self._closed
                and not self._error and not self._initial_loaded):
            self._initial_loaded = True
            QTimer.singleShot(0, self._initial_still)

    def _initial_still(self) -> None:
        if (self._closed or self._error or not self.isVisible()
                or not self._initial_loaded or self._frame.isValid()
                or self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState):
            return
        # Some native decoders don't produce a stopped/paused seek until playback
        # starts. Decode one muted frame, then pause in _video_frame.
        self._priming = True
        self.audio.setMuted(True)
        self.player.play()

    def _duration_changed(self, duration: int) -> None:
        self.seek_bar.setRange(0, max(0, duration))
        self._update_controls()
        if duration > 0 and not self._initial_loaded:
            self._initial_loaded = True
            QTimer.singleShot(0, self._initial_still)

    def _position_changed(self, position: int) -> None:
        if not self.seek_bar.isSliderDown():
            blocked = self.seek_bar.blockSignals(True)
            self.seek_bar.setValue(position)
            self.seek_bar.blockSignals(blocked)
        self.position.setText(
            f"{timecode(position / 1000)} / {timecode(max(0, self.player.duration()) / 1000)}",
        )

    def _playback_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        title = self.tr(
            "Pause" if state == QMediaPlayer.PlaybackState.PlayingState
            and not self._priming else "Play",
        )
        self.play_button.setText(title)
        self.play_button.setAccessibleName(title)

    def toggle_play(self) -> None:
        if self._priming:
            self._priming = False
            self.audio.setMuted(not self.sound.isChecked())
            self.player.play()
            self._playback_changed(self.player.playbackState())
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        elif self.play_button.isEnabled():
            self.audio.setMuted(not self.sound.isChecked())
            self.player.play()

    def pause(self) -> None:
        self._priming = False
        self.audio.setMuted(True)
        self.player.pause()

    def _select_sample(self) -> None:
        if self.select_sample.isEnabled() and self._paths[0] is not None:
            self.sample_selected.emit(self._paths[0], self.player.position() / 1000)

    def _failed(self, _error: QMediaPlayer.Error, message: str) -> None:
        if self._closed:
            return
        self._error = True
        self.pause()
        self.message.setText(self.tr("Preview unavailable: {error}").format(error=message))
        self.message.show()
        self._update_controls()

    def showEvent(self, event: QShowEvent | None) -> None:
        super().showEvent(event)
        if self._initial_loaded and not self._frame.isValid():
            QTimer.singleShot(0, self._initial_still)

    def hideEvent(self, event: QHideEvent | None) -> None:
        self.pause()
        super().hideEvent(event)

    def shutdown(self) -> None:
        self._closed = True
        self._frame = QVideoFrame()
        self.player.stop()
        self.player.setSource(QUrl())
        self.player.setVideoOutput(None)
        self.player.setAudioOutput(None)

    def changeEvent(self, event: QEvent | None) -> None:
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.track.setItemText(0, self.tr("Original"))
            self.track.setItemText(1, self.tr("Processed"))
            self.track.setAccessibleName(self.tr("Preview track"))
            self.empty.setText(self.tr("Choose a video to preview it here."))
            self.select_sample.setText(self.tr("Set sample start"))
            self.sound.setText(self.tr("Sound"))
            self.sound.setAccessibleName(self.tr("Sound"))
            self.select_sample.setAccessibleName(self.tr("Set sample start"))
            self.seek_bar.setAccessibleName(self.tr("Preview timeline"))
            self._playback_changed(self.player.playbackState())
        super().changeEvent(event)
