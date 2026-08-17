"""Render 报一 as a LiSu wordmark in text-only terminals.

Terminals cannot apply a different font to only a few characters.  This module
therefore renders the two glyphs with the locally installed LiSu typeface and
projects the raster into true-colour Unicode half blocks.  It is image-backed
typography, not an approximation made from box-drawing characters.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text

_FONTS = (
    Path(r"C:\Windows\Fonts\SIMLI.TTF"),  # LiSu / 隶书
    Path(r"C:\Windows\Fonts\STLITI.TTF"),
    Path(r"C:\Windows\Fonts\simkai.ttf"),
)


def _font_path() -> Path | None:
    return next((path for path in _FONTS if path.is_file()), None)


def wordmark() -> Text:
    """Return an ANSI-safe, LiSu-rendered ``报一`` wordmark.

    The fallback deliberately remains just the requested two characters if
    Pillow or an East-Asian font is unavailable.
    """
    path = _font_path()
    if path is None:
        return Text("报一", style="bold bright_yellow")
    try:
        from PIL import Image, ImageDraw, ImageFont

        font = ImageFont.truetype(str(path), size=142)
        canvas = Image.new("L", (680, 146), 0)
        draw = ImageDraw.Draw(canvas)
        # Render glyphs independently with deliberate breathing room.
        centers = (225, 455)
        for glyph, center in zip("报一", centers):
            bounds = draw.textbbox((0, 0), glyph, font=font, stroke_width=0)
            width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
            draw.text((center - width // 2 - bounds[0], (146 - height) // 2 - bounds[1] - 3), glyph, fill=255, font=font)
        # One terminal character represents two vertical pixels.
        pixels = canvas.resize((68, 10), Image.Resampling.LANCZOS)
        output = Text()
        for y in range(0, 10, 2):
            for x in range(68):
                top, bottom = pixels.getpixel((x, y)), pixels.getpixel((x, y + 1))
                if not top and not bottom:
                    output.append(" ")
                    continue
                fg_level = 66 + top * 174 // 255
                bg_level = 66 + bottom * 174 // 255
                fg = f"rgb({fg_level},{fg_level},{fg_level})"
                bg = f"rgb({bg_level},{bg_level},{bg_level})"
                output.append("▀", style=f"{fg} on {bg}")
            if y < 8:
                output.append("\n")
        return output
    except Exception:
        return Text("报一", style="bold bright_yellow")

