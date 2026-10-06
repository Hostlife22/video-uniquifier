"""QSS theme tokens + builder. Dark default; light + system future-ready."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from video_uniquifier.gui.design import Metrics, Space, Type

ThemeName = Literal["dark", "light", "system"]


DARK_TOKENS = {
    "bg":             "#101419",
    "bg_alt":         "#191F27",
    "bg_deep":        "#0C1015",
    "fg":             "#F2F5F7",
    "fg_dim":         "#A0ADBD",
    "accent":         "#6BD9BD",
    "accent_hover":   "#8DE5CE",
    "accent_warm":    "#9FE8D4",
    "danger":         "#a83b3b",
    "danger_hover":   "#F18D92",
    "success":        "#3ba85c",
    "warning":        "#d1a93b",
    "border":         "#303A46",
    # Semantic tokens for status badges + KPI pills (R1/E4 — was hard-coded
    # in widgets/preflight_panel.py and widgets/kpi_pills.py, leaking across
    # theme switches). bg + fg are paired so a token swap repaints both at once.
    # R7 / WCAG-AA: per-band fg colours so yellow / green / neutral pills
    # use dark text (light fills can't carry white at 4.5:1).
    "badge_fail_bg":  "#a83b3b",
    "badge_fail_fg":  "#ffffff",
    "badge_warn_bg":  "#d1a93b",
    "badge_warn_fg":  "#16161e",
    "badge_ok_bg":    "#3ba85c",
    "badge_ok_fg":    "#16161e",
    "kpi_red":        "#a83b3b",
    "kpi_yellow":     "#d1a93b",
    "kpi_green":      "#3ba85c",
    "kpi_neutral":    "#9b9ba8",
    "kpi_red_fg":     "#ffffff",
    "kpi_yellow_fg":  "#16161e",
    "kpi_green_fg":   "#16161e",
    "kpi_neutral_fg": "#16161e",
    # Legacy single token kept for back-compat / fallback; per-band fg
    # is preferred by widgets/kpi_pills.py (R7 WCAG-AA fix).
    "kpi_fg":         "#ffffff",
    "chart_intensity": "#E5BC71",
    "chart_similarity": "#F18D92",
    "chart_quality": "#6BD9BD",
    "accent_fg": "#10261F",
    "selected_bg": "#203C34",
    "selected_fg": "#C4F9EA",
    "disabled_bg": "#252C35",
    "disabled_fg": "#8592A3",
    "hover": "#252E39",
}

LIGHT_TOKENS = {
    "bg":             "#F3F5F7",
    "bg_alt":         "#FFFFFF",
    "bg_deep":        "#E9EDF2",
    "fg":             "#15202B",
    # R7 / WCAG-AA: was #6a6a78 — failed 3.93:1 on sidebar (bg_deep).
    # Darkened to #5a5a68 → 5.09:1 on bg_deep, 5.74:1 on bg.
    "fg_dim":         "#526173",
    "accent":         "#176A56",
    "accent_hover":   "#125644",
    "accent_warm":    "#176A56",
    "danger":         "#a83b3b",
    "danger_hover":   "#B02D3A",
    "success":        "#2c8c4a",
    "warning":        "#b8902f",
    "border":         "#CBD3DD",
    # Light-theme semantic tokens — darker fills for AA contrast against
    # a near-white background; readable fg on each fill. R7 / WCAG-AA
    # forced dark fg on yellow + green fills (white was 4.13:1 / 3.86:1).
    "badge_fail_bg":  "#a83b3b",
    "badge_fail_fg":  "#ffffff",
    "badge_warn_bg":  "#b8902f",
    "badge_warn_fg":  "#1f1f2b",
    # R7 / WCAG-AA: success green was #2c8c4a (4.24:1 white, 3.85:1 dark).
    # Darkened to #1c6e30 so white passes 6.3:1; visually still a clear
    # "success / green" hue on a light backdrop.
    "badge_ok_bg":    "#1c6e30",
    "badge_ok_fg":    "#ffffff",
    "kpi_red":        "#a83b3b",
    "kpi_yellow":     "#b8902f",
    "kpi_green":      "#1c6e30",
    "kpi_neutral":    "#5a5a68",
    "kpi_red_fg":     "#ffffff",
    "kpi_yellow_fg":  "#1f1f2b",
    "kpi_green_fg":   "#ffffff",
    "kpi_neutral_fg": "#ffffff",
    "kpi_fg":         "#ffffff",
    "chart_intensity": "#8E601B",
    "chart_similarity": "#B02D3A",
    "chart_quality": "#176A56",
    "accent_fg": "#FFFFFF",
    "selected_bg": "#DBEFE7",
    "selected_fg": "#145040",
    "disabled_bg": "#E7EBF0",
    "disabled_fg": "#657286",
    "hover": "#E9EEF3",
}


def tokens_for(theme: str) -> dict[str, str]:
    """Return the token dict for the given theme name.

    Accepts a plain `str` (not just `ThemeName`) so widgets that hold
    `self._theme: str` from `AppState.theme()` can call this without
    casting. Any non-"light" value resolves to dark — same fallback as
    `qss_for`, matching the v0.5 behaviour until explicit OS detection
    lands in v0.6.
    """
    return LIGHT_TOKENS if theme == "light" else DARK_TOKENS


def qss_for(theme: str) -> str:
    """Return the full QSS stylesheet for the given theme.

    `system` falls back to dark (MVP — explicit OS detection is v0.6).
    """
    return _QSS_TEMPLATE.format(
        **tokens_for(theme), body=Type.BODY, caption=Type.CAPTION, label=Type.LABEL,
        title=Type.TITLE, section=Type.SECTION, brand=Type.BRAND,
        sm=Space.SM, md=Space.MD, lg=Space.LG, xl=Space.XL,
        radius=Metrics.RADIUS, control_radius=Metrics.CONTROL_RADIUS,
        profile_card_height=Metrics.PROFILE_CARD_HEIGHT,
        arrow=(Path(__file__).parent / "assets" /
               f"chevron-{'light' if theme == 'light' else 'dark'}.svg").as_posix(),
    )


_QSS_TEMPLATE = """
QWidget {{ background: {bg}; color: {fg}; font-size: {body}px; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QWidget#disclosure_content {{ background: transparent; }}
QWidget#sidebar_shell, QListWidget#sidebar {{ background: {bg_deep}; }}
QWidget#sidebar_shell {{ border-right: 1px solid {border}; }}
QListWidget#sidebar {{ border: none; outline: none; }}
QListWidget#sidebar::item {{ border: none; }}
QLabel#brand {{ font-size: {brand}px; font-weight: bold; }}
QLabel#eyebrow {{ color: {fg_dim}; font-size: {caption}px; }}
QLabel#title {{ font-size: {title}px; font-weight: bold; background: transparent; }}
QLabel#section_title {{ font-size: {section}px; font-weight: bold; }}
QLabel#hint, QLabel#status, QLabel#subtitle {{ color: {fg_dim}; }}
QLabel#subtitle {{ font-size: {label}px; }}
QLabel#field_label {{ font-weight: bold; color: {fg}; }}
QLabel#path {{ color: {fg}; background: transparent; }}
QLabel#source_metadata {{ color: {fg_dim}; }}
QLabel#status_badge {{
    background: {selected_bg}; color: {selected_fg}; border-radius: {control_radius}px;
    padding: {sm}px {md}px; font-weight: bold;
}}
QFrame#section_card {{
    background: {bg_alt}; border: 1px solid {border}; border-radius: {radius}px;
}}
QPushButton#profile_card {{
    padding: 0px; text-align: left; min-height: {profile_card_height}px;
}}
QPushButton#profile_card:checked {{ border-color: {accent}; background: {selected_bg}; }}
QPushButton#profile_card QLabel {{ background: transparent; }}
QWidget#action_bar {{ background: {bg_deep}; border-top: 1px solid {border}; }}
QWidget#field_surface {{
    background: {bg}; border: 1px solid {border}; border-radius: {control_radius}px;
}}
QWidget#field_surface[dragActive="true"] {{ border: 2px solid {accent}; }}
QPushButton {{
    background: {bg_alt}; color: {fg}; padding: {sm}px {lg}px;
    border: 2px solid {border}; border-radius: {control_radius}px; min-height: 20px;
    font-weight: 500;
}}
QPushButton:hover:!disabled {{ background: {hover}; }}
QPushButton:pressed:!disabled {{ background: {selected_bg}; }}
QPushButton#page_help:checked {{
    background: {selected_bg}; color: {selected_fg}; border-color: {accent};
}}
QPushButton:disabled {{
    background: {disabled_bg}; color: {disabled_fg}; border-color: {disabled_bg};
}}
QPushButton#run, QPushButton[variant="primary"] {{
    background: {accent}; color: {accent_fg}; border-color: {accent}; font-weight: bold;
}}
QPushButton#run:hover:!disabled, QPushButton[variant="primary"]:hover:!disabled {{
    background: {accent_hover}; border-color: {accent_hover};
}}
QPushButton#run:disabled, QPushButton[variant="primary"]:disabled {{
    background: {disabled_bg}; color: {disabled_fg}; border-color: {disabled_bg};
}}
QPushButton#cancel:enabled {{ color: {danger_hover}; }}
QPushButton#cancel:hover:enabled {{ background: {danger}; color: {badge_fail_fg}; }}
QPushButton#disclosure {{
    color: {fg_dim}; border: 2px solid transparent; background: transparent;
    padding-left: 0px; text-align: left;
}}
QPushButton#disclosure:hover {{ color: {fg}; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {bg_alt}; color: {fg}; padding: {sm}px {md}px;
    border-radius: {control_radius}px; border: 2px solid {border}; min-height: 20px;
    selection-background-color: {selected_bg}; selection-color: {selected_fg};
}}
QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled {{
    color: {disabled_fg}; background: {disabled_bg};
}}
QComboBox::drop-down {{ width: 24px; border: none; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{
    background: {bg_alt}; color: {fg}; padding: {sm}px;
    selection-background-color: {selected_bg}; selection-color: {selected_fg};
    border: 1px solid {border};
}}
QProgressBar {{
    background: {disabled_bg}; border: none; border-radius: 5px;
    text-align: center; color: {fg}; height: 10px;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 5px; }}
QTextEdit, QPlainTextEdit {{
    background: {bg_deep}; color: {fg};
    font-family: "Menlo", "Consolas", monospace; font-size: {caption}px;
    border: 1px solid {border}; border-radius: {control_radius}px; padding: {sm}px;
    selection-background-color: {selected_bg}; selection-color: {selected_fg};
}}
QTableWidget {{
    background: {bg_alt}; alternate-background-color: {bg}; gridline-color: {border};
    border: 1px solid {border}; border-radius: {control_radius}px;
    selection-background-color: {selected_bg}; selection-color: {selected_fg};
}}
QTableWidget::item {{ padding: {sm}px; }}
QHeaderView::section {{
    background: {bg_alt}; color: {fg_dim}; padding: {md}px {sm}px;
    border: none; border-bottom: 1px solid {border}; font-weight: bold;
}}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: {control_radius}px; }}
QTabBar::tab {{
    background: transparent; padding: {md}px {lg}px; color: {fg_dim};
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {fg}; border-bottom: 2px solid {accent}; }}
QTabBar::tab:hover {{ background: {hover}; }}
QGroupBox {{
    background: {bg_alt}; border: 1px solid {border}; border-radius: {radius}px;
    margin-top: {xl}px; padding: {lg}px; padding-top: {xl}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: {lg}px; padding: 0 {sm}px;
    color: {fg}; font-size: {section}px; font-weight: bold;
}}
QCheckBox, QRadioButton {{ spacing: {sm}px; min-height: 24px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ border: none; background: {bg}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; min-height: 32px; border-radius: 5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QStatusBar {{ background: {bg_deep}; color: {fg_dim}; font-size: {caption}px; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background: {bg_alt}; color: {fg}; border: 1px solid {border}; padding: {sm}px; }}
/* Border is the Qt Widgets focus indicator; outline also documents the focus contract. */
QPushButton:focus, QLineEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QCheckBox:focus, QRadioButton:focus,
QListWidget:focus, QTreeWidget:focus, QTableWidget:focus, QTabBar::tab:focus {{
    border: 2px solid {accent_warm}; outline: 2px solid {accent_warm};
}}
"""
