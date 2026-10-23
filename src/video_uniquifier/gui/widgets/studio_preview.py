"""Native, paused-by-default source/result player for the main workspace."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QFontDatabase,
    QHideEvent,
    QResizeEvent,
    QShowEvent,
)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.theme import tokens_for
from video_uniquifier.gui.widgets.navigation import outline_icon
from video_uniquifier.gui.widgets.sample_timeline import timecode

if TYPE_CHECKING:
    from video_uniquifier.gui.state import AppState


class StudioPreview(QWidget):
    sample_selected = pyqtSignal(object, float)
    choose_requested = pyqtSignal()
    source_dropped = pyqtSignal(object)

    def __init__(self, state: AppState | None = None) -> None:
        super().__init__()
        self.setObjectName("preview_panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
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
        self.mode_bar = QWidget()
        self.mode_bar.setObjectName("preview_controls")
        modes = QHBoxLayout(self.mode_bar)
        modes.setContentsMargins(0, 0, 0, 0)
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
        layout.addWidget(self.mode_bar)
        self.stage = QStackedWidget()
        self.stage.setObjectName("video_stage")
        self.stage.setMinimumHeight(Metrics.PREVIEW_MIN_HEIGHT)
        self.empty = QWidget()
        self.empty.setObjectName("import_empty")
        self.empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        empty_layout.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        empty_layout.setSpacing(Space.SM)
        empty_layout.addStretch(1)
        self.import_icon = QLabel()
        self.import_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.import_icon)
        self.empty_title = QLabel(self.tr("Add a video to begin"))
        self.empty_title.setObjectName("empty_title")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        self.empty_hint = QLabel(self.tr(
            "Drop a video here, or choose a file. Your original is kept.",
        ))
        self.empty_hint.setObjectName("hint")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_hint)
        self.import_button = QPushButton(self.tr("Choose video…"))
        self.import_button.setProperty("variant", "primary")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setAccessibleName(self.tr("Choose video…"))
        self.import_button.clicked.connect(self.choose_requested)
        empty_layout.addWidget(self.import_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.formats = QLabel("MP4 · MOV · MKV · WebM")
        self.formats.setObjectName("eyebrow")
        self.formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.formats)
        empty_layout.addStretch(1)
        self.set_theme(state.theme if state is not None else "dark")
        if state is not None:
            state.theme_changed.connect(self.set_theme)
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
        self.transport_bar = QWidget()
        self.transport_bar.setObjectName("preview_controls")
        transport = QHBoxLayout(self.transport_bar)
        transport.setContentsMargins(0, 0, 0, 0)
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setProperty("variant", "quiet")
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
        layout.addWidget(self.transport_bar)
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

    def set_theme(self, theme: str) -> None:
        self.import_icon.setPixmap(
            outline_icon("import", tokens_for(theme)["accent"], 40).pixmap(40, 40),
        )

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None or not self.import_button.isEnabled():
            return
        data = event.mimeData()
        if data is not None and any(
            url.isLocalFile() and Path(url.toLocalFile()).is_file() for url in data.urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is None or not self.import_button.isEnabled():
            return
        data = event.mimeData()
        if data is None:
            return
        for url in data.urls():
            path = Path(url.toLocalFile())
            if url.isLocalFile() and path.is_file():
                self.source_dropped.emit(path)
                event.acceptProposedAction()
                return

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
        available = any(path is not None and path.is_file() for path in self._paths)
        self.mode_bar.setVisible(available)
        self.transport_bar.setVisible(available)
        self.position.setVisible(available)
        self.track.setEnabled(any(path is not None for path in self._paths))
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

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        compact = self.height() < 300
        self.import_icon.setVisible(not compact)
        self.formats.setVisible(not compact)
        inset = Space.SM if compact else Space.LG
        self.empty.layout().setContentsMargins(inset, inset, inset, inset)

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
            self.empty_title.setText(self.tr("Add a video to begin"))
            self.empty_hint.setText(self.tr(
                "Drop a video here, or choose a file. Your original is kept.",
            ))
            self.import_button.setText(self.tr("Choose video…"))
            self.import_button.setAccessibleName(self.tr("Choose video…"))
            self.select_sample.setText(self.tr("Set sample start"))
            self.sound.setText(self.tr("Sound"))
            self.sound.setAccessibleName(self.tr("Sound"))
            self.select_sample.setAccessibleName(self.tr("Set sample start"))
            self.seek_bar.setAccessibleName(self.tr("Preview timeline"))
            self._playback_changed(self.player.playbackState())
        super().changeEvent(event)
