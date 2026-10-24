"""Focused delivery/audio/branding forms backed by the strict business schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from video_uniquifier.core.reels.config import ReelsRules, resolve_asset
from video_uniquifier.gui.design import Space
from video_uniquifier.gui.widgets.sample_timeline import TimecodeSpinBox


class AssetPicker(QWidget):
    changed = pyqtSignal()

    def __init__(self, caption: str, file_filter: str) -> None:
        super().__init__()
        self.caption = caption
        self.file_filter = file_filter
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.path = QLineEdit()
        self.path.setPlaceholderText(self.tr("Choose a local file…"))
        self.path.setAccessibleName(self.tr(caption))
        self.path.textChanged.connect(self.changed)
        row.addWidget(self.path, stretch=1)
        self.browse = QPushButton(self.tr("Choose…"))
        self.browse.setAccessibleName(self.tr(caption))
        self.browse.clicked.connect(self._choose)
        row.addWidget(self.browse)

    def _choose(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, self.tr(self.caption), "", self.file_filter)
        if selected:
            self.path.setText(selected)


class ReelsOptions(QTabWidget):
    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("reels_options")
        self.base_rules = ReelsRules()
        video = self._page("Video delivery")
        output = self._group(video, "Output format")
        self.resolution = self._combo(output, "Resolution", [
            ("1080 × 1920 · Full HD", (1080, 1920)), ("720 × 1280 · HD", (720, 1280)),
        ])
        self.crf = QSpinBox()
        self.crf.setRange(18, 23)
        output.addRow(self.tr("Picture quality (CRF)"), self.crf)
        self.preset = self._combo(output, "Encoding speed", [
            ("Fast · veryfast", "veryfast"), ("Balanced · medium", "medium"),
        ])
        self.fps = self._combo(output, "Frame rate", [
            ("Auto · preserve common CFR", "auto"), ("Always 30 fps", "cfr30"),
        ])
        self._hint(video, "H.264 MP4 · Rec.709 · faststart. Lower CRF keeps more detail.")
        geometry = self._group(video, "Framing & color")
        self.geometry_mode = self._combo(geometry, "Non-vertical video", [
            ("Blurred background · keep full frame", "pad_blur"),
            ("Black padding · keep full frame", "fit"),
            ("Center crop · manual choice", "crop"),
        ])
        self.hdr = self._combo(geometry, "HDR source", [
            ("Stop and show advice", "fail_with_advice"),
            ("Convert HDR to SDR", "tonemap_sdr"),
        ])
        self._hint(video, "Vertical video keeps its frame. Upscaling does not add detail.")
        video.addStretch(1)

        audio_page = self._page("Audio & timeline")
        audio = self._group(audio_page, "Dialogue & loudness")
        self.normalize = QCheckBox(self.tr("Normalize dialogue loudness"))
        audio.addRow(self.normalize)
        self.lufs = self._number(audio, "Integrated loudness (LUFS)", -30, -10)
        self.peak = self._number(audio, "True peak ceiling (dBTP)", -6, -1)
        self.lra = self._number(audio, "Loudness range (LU)", 1, 20)
        self._hint(audio_page, "Original pitch and speed · AAC 48 kHz stereo · no noise added.")
        timeline = self._group(audio_page, "Timeline")
        self.trim_start = TimecodeSpinBox()
        self.trim_end = TimecodeSpinBox()
        for label, spin in (("Trim from start", self.trim_start), ("Trim from end", self.trim_end)):
            spin.setRange(0, 14400)
            spin.setDecimals(2)
            timeline.addRow(self.tr(label), spin)
        self.detect_scenes = QCheckBox(self.tr("Detect shots · keep original order"))
        self.detect_black = QCheckBox(self.tr("Report black frames"))
        self.detect_silence = QCheckBox(self.tr("Report silence"))
        for control in (self.detect_scenes, self.detect_black, self.detect_silence):
            timeline.addRow(control)
        self._hint(audio_page,
                   "Trim applies to picture and sound together. Detection never removes scenes.")
        audio_page.addStretch(1)

        branding = self._page("Title & logo")
        title = self._group(branding, "Human-written title", checkable=True)
        self.title_group = title.parentWidget()
        assert isinstance(self.title_group, QGroupBox)
        self.title_text = QPlainTextEdit()
        self.title_text.setPlaceholderText(self.tr("Enter the programme title or episode number…"))
        self.title_text.setMaximumHeight(80)
        self.title_text.setAccessibleName(self.tr("Title text"))
        title.addRow(self.title_text)
        self.font_picker = AssetPicker("Choose title font", "Fonts (*.ttf *.otf *.ttc)")
        title.addRow(self.tr("Font file"), self.font_picker)
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 160)
        title.addRow(self.tr("Font size (px)"), self.font_size)
        self.title_position = self._combo(title, "Title position", [
            ("Top safe area", "top_safe"), ("Center safe area", "center_safe"),
            ("Bottom safe area", "bottom_safe"),
        ])
        self.title_start = self._number(title, "Title starts at (s)", 0, 14400)
        self.title_end = self._number(title, "Title ends at (s)", 0, 14400)
        self.title_end.setSpecialValueText(self.tr("Until video ends"))
        logo = self._group(branding, "Brand logo", checkable=True)
        self.logo_group = logo.parentWidget()
        assert isinstance(self.logo_group, QGroupBox)
        self.logo = AssetPicker("Choose PNG logo", "PNG (*.png)")
        logo.addRow(self.tr("Logo file"), self.logo)
        self.logo_width = QSpinBox()
        self.logo_width.setRange(8, 1080)
        logo.addRow(self.tr("Logo width (px)"), self.logo_width)
        self.logo_anchor = self._combo(logo, "Logo position", [
            ("Top right", "top_right"), ("Top left", "top_left"),
            ("Bottom right", "bottom_right"), ("Bottom left", "bottom_left"),
        ])
        self.logo_x = QSpinBox()
        self.logo_y = QSpinBox()
        for label, margin_spin in (("Horizontal margin (px)", self.logo_x),
                            ("Vertical margin (px)", self.logo_y)):
            margin_spin.setRange(0, 1920)
            logo.addRow(self.tr(label), margin_spin)
        self._hint(branding,
                   "Title and logo are optional. The bottom subtitle zone stays protected.")
        branding.addStretch(1)
        self.set_rules(self.base_rules)
        for combo in self.findChildren(QComboBox):
            combo.currentIndexChanged.connect(self.changed)
        for number in self.findChildren(QSpinBox):
            number.valueChanged.connect(self.changed)
        for decimal in self.findChildren(QDoubleSpinBox):
            decimal.valueChanged.connect(self.changed)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.toggled.connect(self.changed)
        self.title_group.toggled.connect(self.changed)
        self.logo_group.toggled.connect(self.changed)
        self.title_text.textChanged.connect(self.changed)
        self.font_picker.changed.connect(self.changed)
        self.logo.changed.connect(self.changed)
        for field, caption in (
            (self.crf, "Picture quality (CRF)"), (self.trim_start, "Trim from start"),
            (self.trim_end, "Trim from end"), (self.font_size, "Font size (px)"),
            (self.logo_width, "Logo width (px)"), (self.logo_x, "Horizontal margin (px)"),
            (self.logo_y, "Vertical margin (px)"),
        ):
            field.setAccessibleName(self.tr(caption))

    def _page(self, label: str) -> QVBoxLayout:
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.LG)
        layout.setSpacing(Space.LG)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.addTab(scroll, self.tr(label))
        return layout

    def _group(self, layout: QVBoxLayout, title: str, *, checkable: bool = False) -> QFormLayout:
        group = QGroupBox(self.tr(title))
        group.setCheckable(checkable)
        if checkable:
            group.setChecked(False)
        form = QFormLayout(group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        form.setSpacing(Space.MD)
        layout.addWidget(group)
        return form

    def _combo(self, form: QFormLayout, label: str,
               items: list[tuple[str, Any]]) -> QComboBox:
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(14)
        for title, data in items:
            combo.addItem(self.tr(title), data)
        combo.setAccessibleName(self.tr(label))
        form.addRow(self.tr(label), combo)
        return combo

    def _number(self, form: QFormLayout, label: str, low: float, high: float) -> QDoubleSpinBox:
        number = QDoubleSpinBox()
        number.setRange(low, high)
        number.setDecimals(1)
        number.setAccessibleName(self.tr(label))
        form.addRow(self.tr(label), number)
        return number

    def _hint(self, layout: QVBoxLayout, text: str) -> None:
        hint = QLabel(self.tr(text))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def set_rules(self, rules: ReelsRules, asset_root: Path | None = None) -> None:
        self.base_rules = rules.model_copy(deep=True)
        video, audio, scenes, packaging = rules.video, rules.audio, rules.scenes, rules.packaging
        values = ((self.resolution, (video.width, video.height)), (self.preset, video.preset),
                  (self.fps, video.fps_mode),
                  (self.geometry_mode, video.geometry.nonvertical_source),
                  (self.hdr, video.hdr_policy), (self.title_position, packaging.title.position),
                  (self.logo_anchor, packaging.logo.anchor))
        for combo, value in values:
            combo.setCurrentIndex(max(0, combo.findData(value)))
        numbers: tuple[tuple[QSpinBox | QDoubleSpinBox, float], ...] = (
                            (self.crf, video.crf), (self.lufs, audio.loudnorm.integrated_lufs),
                            (self.peak, audio.loudnorm.true_peak_dbtp),
                            (self.lra, audio.loudnorm.lra),
                            (self.trim_start, scenes.trim_start_sec),
                            (self.trim_end, scenes.trim_end_sec),
                            (self.font_size, packaging.title.font_size_px),
                            (self.title_start, packaging.title.start_sec),
                            (self.title_end, packaging.title.end_sec or 0),
                            (self.logo_width, packaging.logo.width_px),
                            (self.logo_x, packaging.logo.margin_x_px),
                            (self.logo_y, packaging.logo.margin_y_px))
        for spin, number_value in numbers:
            if isinstance(spin, QSpinBox):
                spin.setValue(int(number_value))
            else:
                spin.setValue(number_value)
        self.normalize.setChecked(audio.enabled and audio.loudnorm.enabled)
        self.detect_scenes.setChecked(scenes.detect_enabled)
        self.detect_black.setChecked(scenes.blackdetect_enabled)
        self.detect_silence.setChecked(scenes.silence_detect_enabled)
        assert isinstance(self.title_group, QGroupBox)
        assert isinstance(self.logo_group, QGroupBox)
        self.title_group.setChecked(packaging.enabled and packaging.title.enabled)
        self.logo_group.setChecked(packaging.enabled and packaging.logo.enabled)
        self.title_text.setPlainText(packaging.title.text or "")
        self.font_picker.path.clear()
        self.logo.path.clear()
        if asset_root is not None:
            for picker, relative in ((self.font_picker, packaging.title.font_path),
                                     (self.logo, packaging.logo.source)):
                if relative:
                    picker.path.setText(str(resolve_asset(asset_root, relative)))

    def configuration(self) -> tuple[ReelsRules, dict[str, Path]]:
        raw = self.base_rules.model_dump(mode="python")
        video, audio, scenes, packaging = (raw[key] for key in (
            "video", "audio", "scenes", "packaging"))
        video["width"], video["height"] = self.resolution.currentData()
        video.update(crf=self.crf.value(), preset=self.preset.currentData(),
                     fps_mode=self.fps.currentData(), hdr_policy=self.hdr.currentData())
        mode = self.geometry_mode.currentData()
        video["geometry"].update(nonvertical_source=mode, allow_center_crop=mode == "crop")
        audio["enabled"] = True
        audio["loudnorm"].update(enabled=self.normalize.isChecked(),
                                integrated_lufs=self.lufs.value(),
                                true_peak_dbtp=self.peak.value(), lra=self.lra.value())
        scenes.update(trim_start_sec=self.trim_start.value(), trim_end_sec=self.trim_end.value(),
                      detect_enabled=self.detect_scenes.isChecked(),
                      blackdetect_enabled=self.detect_black.isChecked(),
                      silence_detect_enabled=self.detect_silence.isChecked())
        assert isinstance(self.title_group, QGroupBox)
        assert isinstance(self.logo_group, QGroupBox)
        title_enabled, logo_enabled = self.title_group.isChecked(), self.logo_group.isChecked()
        packaging.update(enabled=title_enabled or logo_enabled, safe_area_preview_enabled=True)
        packaging["title"].update(enabled=title_enabled, text=self.title_text.toPlainText() or None,
                                  font_path="title-font.ttf" if title_enabled else None,
                                  font_size_px=self.font_size.value(),
                                  position=self.title_position.currentData(),
                                  start_sec=self.title_start.value() if title_enabled else 0,
                                  end_sec=(self.title_end.value() or None)
                                  if title_enabled else None)
        packaging["logo"].update(enabled=logo_enabled, source="logo.png" if logo_enabled else None,
                                 width_px=self.logo_width.value(),
                                 anchor=self.logo_anchor.currentData(),
                                 margin_x_px=self.logo_x.value(), margin_y_px=self.logo_y.value())
        assets = {}
        for enabled, name, picker in ((title_enabled, "title-font.ttf", self.font_picker),
                                      (logo_enabled, "logo.png", self.logo)):
            if enabled:
                value = picker.path.text().strip()
                if not value or not Path(value).expanduser().is_file():
                    raise ValueError(self.tr("Choose an existing local logo/font file."))
                assets[name] = Path(value).expanduser()
        return ReelsRules.model_validate(raw), assets
