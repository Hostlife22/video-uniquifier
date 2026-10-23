"""Local human-written title/PNG layers. User text never enters a filter expression."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from video_uniquifier.core.reels.config import ReelsRules, TitleRules, resolve_asset
from video_uniquifier.core.reels.runtime import ReelsError, check_cancel, execute
from video_uniquifier.core.runner import CancelToken
from video_uniquifier.core.utils.ffmpeg_paths import ffmpeg_bin

Layer = tuple[Path, float, float | None]
Box = tuple[int, int, int, int]


def safe_box(rules: ReelsRules) -> Box:
    safe = rules.packaging.safe_area
    width, height = rules.video.width, rules.video.height
    return (math.ceil(width * safe.left_fraction), math.ceil(height * safe.top_fraction),
            math.floor(width * (1 - safe.right_fraction)),
            math.floor(height * (1 - safe.bottom_fraction)))


def _check_box(box: Box, rules: ReelsRules, name: str, warnings: list[str]) -> None:
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > rules.video.width or y1 > rules.video.height:
        raise ReelsError("packaging_bounds", f"{name} does not fit the output canvas.")
    subtitle_top = rules.video.height * (1 - rules.packaging.subtitle_zone.bottom_fraction)
    if rules.packaging.protect_existing_hard_subtitles and y1 > subtitle_top:
        raise ReelsError("subtitle_zone_conflict", f"{name} overlaps the protected subtitle zone. "
                         "Move it or explicitly change subtitle protection after preview review.")
    left, top, right, bottom = safe_box(rules)
    if x0 < left or y0 < top or x1 > right or y1 > bottom:
        warnings.append(f"{name} extends outside the internal safe area; review on a real device.")


def _wrap_title(text: str, font: ImageFont.FreeTypeFont, title: TitleRules, width: int) -> str:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for char in paragraph:
            candidate = line + char
            if font.getlength(candidate) + 2 * title.outline_px > width:
                if not line:
                    raise ReelsError("title_width", "Title glyph exceeds the available width.")
                lines.append(line)
                line = char
            else:
                line = candidate
        lines.append(line)
    if len(lines) > title.max_lines:
        raise ReelsError("title_lines", "Title exceeds max_lines at this font size; "
                         "shorten the text or reduce the font size.")
    return "\n".join(lines)


def render_layers(
    rules: ReelsRules, asset_root: Path, work: Path, duration: float, token: CancelToken,
) -> tuple[list[Layer], list[dict[str, Any]], list[str]]:
    """Render transparent layers with Pillow; composition is fused into the native encode."""
    layers: list[Layer] = []
    metadata: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not rules.packaging.enabled:
        return layers, metadata, warnings
    check_cancel(token)
    canvas_size = (rules.video.width, rules.video.height)
    logo = rules.packaging.logo
    if logo.enabled and logo.source is not None:
        source = resolve_asset(asset_root, logo.source)
        with Image.open(source) as image:
            if image.format != "PNG" or image.width * image.height > 16_000_000:
                raise ReelsError("logo_format", "Logo must be a PNG image within 16 megapixels.")
            height = max(1, round(image.height * logo.width_px / image.width))
            resized = image.convert("RGBA").resize(
                (logo.width_px, height), Image.Resampling.LANCZOS)
        resized.putalpha(resized.getchannel("A").point(
            [round(i * logo.opacity) for i in range(256)]))
        x = (rules.video.width - logo.margin_x_px - logo.width_px
             if logo.anchor.endswith("right") else logo.margin_x_px)
        y = (rules.video.height - logo.margin_y_px - height
             if logo.anchor.startswith("bottom") else logo.margin_y_px)
        box = (x, y, x + logo.width_px, y + height)
        _check_box(box, rules, "Logo", warnings)
        canvas = Image.new("RGBA", canvas_size)
        canvas.alpha_composite(resized, (x, y))
        destination = work / "logo-layer.png"
        canvas.save(destination)
        layers.append((destination, 0.0, None))
        metadata.append({"kind": "logo", "box": box, "source": logo.source})
    title = rules.packaging.title
    if title.enabled and title.text and title.font_path:
        if title.start_sec >= duration:
            raise ReelsError("title_timing", "Title starts after the output video ends.")
        font = ImageFont.truetype(str(resolve_asset(asset_root, title.font_path)),
                                  title.font_size_px)
        if not isinstance(font, ImageFont.FreeTypeFont):
            raise ReelsError("font_invalid", "A local TrueType/OpenType font is required.")
        left, top, right, bottom = safe_box(rules)
        text = _wrap_title(title.text, font, title, right - left)
        canvas = Image.new("RGBA", canvas_size)
        draw = ImageDraw.Draw(canvas)
        bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=8,
                                         stroke_width=title.outline_px, align="center")
        width = math.ceil(bounds[2] - bounds[0])
        height = math.ceil(bounds[3] - bounds[1])
        x = left + (right - left - width) // 2
        y = {"top_safe": top + 8, "center_safe": top + (bottom - top - height) // 2,
             "bottom_safe": bottom - height - 8}[title.position]
        box = (x, y, x + width, y + height)
        _check_box(box, rules, "Title", warnings)
        draw.multiline_text((x - bounds[0], y - bounds[1]), text, font=font,
                            fill=title.color, stroke_width=title.outline_px,
                            stroke_fill="#000000", align="center", spacing=8)
        destination = work / "title-layer.png"
        canvas.save(destination)
        end = min(title.end_sec, duration) if title.end_sec is not None else None
        layers.append((destination, title.start_sec, end))
        metadata.append({"kind": "title", "box": box, "text": text,
                         "start_sec": title.start_sec, "end_sec": end})
    if len(metadata) == 2:
        a, b = (entry["box"] for entry in metadata)
        if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
            warnings.append("Title and logo overlap; review or adjust the template "
                            "before delivery.")
    if metadata:
        warnings.append("Internal safe areas are heuristic. Check hard subtitles and actual "
                        "Facebook UI on a phone; no OCR or automatic subtitle guarantee "
                        "is provided.")
    check_cancel(token)
    return layers, metadata, warnings


def create_previews(
    output: Path, rules: ReelsRules, work: Path, token: CancelToken,
) -> dict[str, str]:
    """Separate review assets never become a cover or change the delivery video's frames."""
    artifacts: dict[str, str] = {}
    if rules.quality_gate.sample_preview_enabled:
        preview = work / "preview.mp4"
        execute([ffmpeg_bin(), "-v", "error", "-y", "-i", str(output),
                 "-t", str(rules.quality_gate.sample_preview_seconds), "-map", "0:v:0",
                 "-map", "0:a:0?", "-c", "copy", "-movflags", "+faststart", str(preview)],
                work / "preview.log", token, timeout=rules.worker.wall_timeout_sec)
        artifacts["sample"] = preview.name
    if rules.packaging.safe_area_preview_enabled:
        frame = work / "preview-frame.png"
        execute([ffmpeg_bin(), "-v", "error", "-y", "-i", str(output),
                 "-frames:v", "1", "-update", "1", str(frame)],
                work / "preview-frame.log", token, timeout=60)
        with Image.open(frame) as image:
            base = image.convert("RGBA")
        overlay = Image.new("RGBA", base.size)
        draw = ImageDraw.Draw(overlay)
        left, top, right, bottom = safe_box(rules)
        draw.rectangle((0, 0, base.width, top), fill=(230, 90, 70, 55))
        draw.rectangle((0, bottom, base.width, base.height), fill=(230, 90, 70, 55))
        draw.rectangle((0, top, left, bottom), fill=(230, 90, 70, 55))
        draw.rectangle((right, top, base.width, bottom), fill=(230, 90, 70, 55))
        draw.rectangle((left, top, right, bottom), outline=(30, 225, 170, 255), width=3)
        draw.text((left + 8, top + 8), "PREVIEW ONLY | internal safe area", fill="white",
                  stroke_width=1, stroke_fill="black", font=ImageFont.load_default(size=18))
        destination = work / "safe-area.png"
        Image.alpha_composite(base, overlay).convert("RGB").save(destination)
        frame.unlink()
        artifacts["safe_area"] = destination.name
    check_cancel(token)
    return artifacts
