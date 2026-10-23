"""Refresh catalogue-backed widget captions without rebuilding a screen.

Only presentation properties are touched. Editor contents, table cells, item
data and selection stay intact. Remember English sources so switching back to
English also works for legacy controls constructed without ``tr()``.
"""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QObject, QSignalBlocker
from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from video_uniquifier.gui.i18n.translations import SOURCE_KEYS, TRANSLATIONS

_SOURCES = frozenset(SOURCE_KEYS)
_REVERSE = {value: key for table in TRANSLATIONS.values() for key, value in table.items()}


def _text(owner: QObject, prop: str, current: str) -> str:
    bindings: dict[str, tuple[str, str]] = getattr(owner, "_i18n_captions", {})
    previous = bindings.get(prop)
    if previous is not None and current == previous[1]:
        source = previous[0]
    else:
        # Forms often append a colon outside tr(). Keep punctuation attached
        # to the caption without requiring duplicate catalogue entries.
        source = current if current in _SOURCES else _REVERSE.get(current, current)
        if source not in _SOURCES and source.endswith((":", "：")):
            stem = source[:-1]
            stem = _REVERSE.get(stem, stem)
            if stem in _SOURCES:
                source = stem + ":"
        if source not in _SOURCES and not (source.endswith(":") and source[:-1] in _SOURCES):
            bindings.pop(prop, None)
            return current
    translated = QCoreApplication.translate("Desktop", source)
    if source.endswith(":") and source not in _SOURCES:
        from video_uniquifier.gui.i18n import active_locale

        suffix = "：" if active_locale() == "zh_CN" else ":"
        translated = QCoreApplication.translate("Desktop", source[:-1]) + suffix
    bindings[prop] = (source, translated)
    owner._i18n_captions = bindings  # type: ignore[attr-defined]
    return translated


def retranslate_widgets(root: QWidget) -> None:
    """Translate known captions on a page, preserving its live state."""
    for widget in (root, *root.findChildren(QWidget)):
        # Changing a combo's display labels must not fire application handlers.
        blocker = QSignalBlocker(widget)
        for prop in ("toolTip", "statusTip", "accessibleName", "accessibleDescription"):
            current = str(widget.property(prop) or "")
            translated = _text(widget, prop, current)
            if translated != current:
                widget.setProperty(prop, translated)
        if isinstance(widget, (QLabel, QAbstractButton)):
            current = widget.text()
            translated = _text(widget, "text", current)
            if translated != current:
                widget.setText(translated)
        elif isinstance(widget, QGroupBox):
            widget.setTitle(_text(widget, "title", widget.title()))
        elif isinstance(widget, (QLineEdit, QPlainTextEdit, QTextEdit)):
            widget.setPlaceholderText(_text(widget, "placeholder", widget.placeholderText()))
        elif isinstance(widget, QComboBox) and not widget.isEditable():
            for index in range(widget.count()):
                widget.setItemText(index, _text(widget, f"item:{index}", widget.itemText(index)))
        elif isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                widget.setTabText(index, _text(widget, f"tab:{index}", widget.tabText(index)))
        elif isinstance(widget, QTableWidget):
            for index in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(index)
                if item is not None:
                    item.setText(_text(widget, f"header:{index}", item.text()))
        del blocker
