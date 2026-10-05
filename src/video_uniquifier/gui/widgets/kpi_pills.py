"""KpiPills — horizontal chips showing KPI values from a qa.json."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from video_uniquifier.gui.design import Metrics, Space
from video_uniquifier.gui.theme import tokens_for

# Threshold bands per KPI: (green_max, yellow_max). Beyond → red.
# Values use the "lower is better" convention where applicable
# (pHash, cid_predict). For "higher is better" KPIs (VMAF, Hamming)
# we flip the comparison in _pill_color_key.
_KPI_BANDS = {
    "phash_worst":   ("lower", 0.75, 0.85),
    "vmaf_mean":     ("higher", 85.0, 75.0),
    "audio_hamming": ("higher", 18.0, 10.0),
    "cid_predict":   ("lower", 0.2, 0.4),
}


def _pill_color_key(name: str, value: float | None) -> str:
    """Return the token key (`kpi_red`/`kpi_yellow`/`kpi_green`/`kpi_neutral`).

    Decoupled from the actual color string so the same logic resolves
    differently per theme (R1/E4 — was returning hex codes directly,
    which leaked dark-theme palette into light-theme renders).
    """
    if value is None:
        return "kpi_neutral"
    direction, green_thr, yellow_thr = _KPI_BANDS.get(name, ("lower", 0.5, 0.8))
    if direction == "lower":
        if value < green_thr:
            return "kpi_green"
        if value < yellow_thr:
            return "kpi_yellow"
        return "kpi_red"
    # higher
    if value >= green_thr:
        return "kpi_green"
    if value >= yellow_thr:
        return "kpi_yellow"
    return "kpi_red"


class KpiPills(QWidget):
    """Horizontal row of colored chips for QA KPIs.

    Empty when no qa.json is set. Renders 4 pills:
    pHash worst chunk, VMAF, Audio FP Hamming, local maximum similarity.

    Pass `state` to subscribe to `theme_changed` so the pills repaint
    on theme switch. Construction without `state` keeps the widget
    usable in tests; pills will use the dark theme until
    `set_theme()` is called explicitly.
    """

    def __init__(self, state: object | None = None) -> None:
        super().__init__()
        self._theme: str = "dark"
        self._last_qa: dict[str, object] | None = None
        self._build_ui()
        if state is not None:
            theme = getattr(state, "theme", None)
            if isinstance(theme, str):
                self._theme = theme
            sig = getattr(state, "theme_changed", None)
            if sig is not None:
                sig.connect(self.set_theme)

    def _build_ui(self) -> None:
        self._pills: list[QLabel] = []
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, Space.XS, 0, Space.XS)
        self._layout.setSpacing(Space.SM)

    def set_theme(self, theme: str) -> None:
        """Repaint pills with the new theme's tokens. Idempotent."""
        if theme == self._theme:
            return
        self._theme = theme
        if self._last_qa is not None:
            self.set_qa(self._last_qa)

    def clear(self) -> None:
        self._last_qa = None
        self._clear_pills()

    def _clear_pills(self) -> None:
        self._pills = []
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def set_qa(self, qa: dict[str, object]) -> None:
        """Populate from a QA dict (decoded qa.json)."""
        self._last_qa = qa
        self._clear_pills()

        # Compute worst chunk pHash.
        chunks_raw = qa.get("chunk_similarities") or []
        chunks: list[dict[str, float]] = chunks_raw if isinstance(chunks_raw, list) else []
        phash_fallback = qa.get("phash_similarity")
        phash_default = phash_fallback if isinstance(phash_fallback, (int, float)) else None
        if qa.get("phash_samples") == 0:
            phash_default = None
        worst_phash: float | None = max(
            (
                float(c.get("combined", c.get("visual", 0.0)))
                for c in chunks if isinstance(c, dict)
            ),
            default=phash_default,
        )

        def _opt_float(key: str) -> float | None:
            v = qa.get(key)
            return float(v) if isinstance(v, (int, float)) else None

        pills = [
            ("pHash worst", worst_phash, "phash_worst", "{:.3f}"),
            ("VMAF", _opt_float("vmaf_mean"), "vmaf_mean", "{:.1f}"),
            (
                "Audio Hamming",
                _opt_float("audio_fp_hamming_per_frame"),
                "audio_hamming",
                "{:.1f}b",
            ),
            ("Similarity max", _opt_float("cid_predict_self"), "cid_predict", "{:.2f}"),
        ]
        for label, value, band_key, fmt in pills:
            self._pills.append(self._pill(label, value, band_key, fmt))
        self._reflow()

    def _reflow(self) -> None:
        columns = 4 if self.width() >= Metrics.GRID_WIDE else 2
        for index, pill in enumerate(self._pills):
            self._layout.addWidget(pill, index // columns, index % columns)
        for column in range(4):
            self._layout.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._reflow()

    def _pill(
        self, label: str, value: float | None, band_key: str, fmt: str,
    ) -> QLabel:
        tokens = tokens_for(self._theme)
        # R7 / WCAG-AA: per-band fg lookup so yellow / green / neutral
        # pills carry dark text (white at 4.5:1 on those fills fails AA).
        # Falls back to `kpi_fg` for any future band that hasn't published
        # an explicit pair.
        color_key = _pill_color_key(band_key, value)
        color = tokens[color_key]
        fg = tokens.get(f"{color_key}_fg", tokens["kpi_fg"])
        text = fmt.format(value) if value is not None else "n/a"
        pill = QLabel(f"<b>{label}</b>  {text}")
        pill.setAccessibleName(f"{label}: {text}")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setStyleSheet(
            f"background: {color}; color: {fg}; "
            f"padding: {Space.SM}px {Space.MD}px; "
            f"border-radius: {Metrics.CONTROL_RADIUS}px; font-weight: 600;"
        )
        return pill
