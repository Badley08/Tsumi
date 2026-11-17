# Tsumi — Lecteur de manga, manhwa, manhua et webtoon
# Copyright (C) 2024  Badley08
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
assets/icon.py — Titlebar icon for Tsumi

Provides get_icon_base64() → str  (Base64-encoded PNG, 48×48)
and     get_photo_image(root) → tk.PhotoImage ready to use.

The icon is rendered from assets/logo_256.svg (or logo.svg) at runtime
when cairosvg / rsvg or Pillow+cairosvg are available.  Falls back to a
built-in Base64 PNG so the app always has an icon even without system libs.
"""

from __future__ import annotations

import base64
import io
import pathlib
import sys
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).parent          # …/assets/
_SVG_256 = _HERE / "logo_256.svg"
_SVG_512 = _HERE / "logo.svg"

# ── Icon size ─────────────────────────────────────────────────────────────────
ICON_SIZE = 48          # pixels (square)

# ── Minimal fallback PNG (48×48, dark bg + blue 詰 kanji, embedded Base64) ───
# Generated once; keeps the app functional with zero system dependencies.
_FALLBACK_B64 = (
    # This is a 48×48 RGBA PNG built inline with Pillow (see _build_fallback).
    # We fill it lazily on first request.
    None
)


def _build_fallback_png() -> bytes:
    """Create a minimal 48×48 PNG entirely in Python (no SVG libs needed)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded-square background
        radius = 10
        draw.rounded_rectangle(
            [(0, 0), (ICON_SIZE - 1, ICON_SIZE - 1)],
            radius=radius,
            fill=(13, 13, 13, 255),
            outline=(22, 113, 227, 200),
            width=2,
        )

        # Gradient simulation: draw horizontal bands from blue→dark
        for y in range(2, ICON_SIZE - 2):
            t = y / ICON_SIZE
            r = int(22  + (13  - 22)  * t)
            g = int(113 + (13  - 113) * t)
            b = int(227 + (13  - 227) * t)
            draw.line([(2, y), (ICON_SIZE - 2, y)], fill=(r, g, b, 30))

        # Kanji 詰 — try to use a system font, fall back to default
        kanji = "詰"
        font: Optional[ImageFont.FreeTypeFont] = None
        font_candidates = [
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
            "/System/Library/Fonts/Hiragino Mincho ProN W3.otf",
            "C:/Windows/Fonts/YuMinL.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
        ]
        font_size = 32
        for path in font_candidates:
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except (IOError, OSError):
                continue

        if font is None:
            # PIL built-in bitmap font — very small, but always available
            font = ImageFont.load_default()
            kanji = "T"      # fallback glyph if no CJK font found
            font_size = 10

        # Center the glyph
        bbox = draw.textbbox((0, 0), kanji, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (ICON_SIZE - tw) // 2 - bbox[0]
        ty = (ICON_SIZE - th) // 2 - bbox[1]

        # Glow pass (slightly larger, low-opacity blue)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((tx + dx, ty + dy), kanji, font=font,
                      fill=(22, 113, 227, 100))

        # Main glyph
        draw.text((tx, ty), kanji, font=font, fill=(77, 166, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        # Absolute fallback: 1×1 transparent PNG
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )


def _render_svg_to_png(size: int = ICON_SIZE) -> Optional[bytes]:
    """
    Attempt to render logo_256.svg → PNG bytes at *size*×*size*.
    Returns None if no SVG renderer is available.
    """
    svg_path = _SVG_256 if _SVG_256.exists() else (_SVG_512 if _SVG_512.exists() else None)
    if svg_path is None:
        return None

    # Try cairosvg (best quality)
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2png(
            url=str(svg_path),
            output_width=size,
            output_height=size,
        )
    except ImportError:
        pass

    # Try Pillow + wand (ImageMagick binding)
    try:
        from wand.image import Image as WandImage  # type: ignore
        with WandImage(filename=str(svg_path)) as img:
            img.resize(size, size)
            img.format = "png"
            buf = io.BytesIO()
            img.save(file=buf)
            return buf.getvalue()
    except ImportError:
        pass

    # Try rsvg-convert subprocess
    try:
        import subprocess
        result = subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size),
             "-f", "png", str(svg_path)],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return None


def get_icon_bytes(size: int = ICON_SIZE) -> bytes:
    """
    Return raw PNG bytes for the Tsumi icon at *size*×*size* pixels.

    Rendering priority:
      1. SVG via cairosvg (best quality, vector)
      2. SVG via wand/ImageMagick
      3. SVG via rsvg-convert subprocess
      4. Pillow-drawn fallback (always works)
    """
    png = _render_svg_to_png(size)
    if png:
        # Resize to exactly *size* if needed (some renderers may differ)
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(png)).resize((size, size), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except ImportError:
            return png

    return _build_fallback_png()


def get_icon_base64(size: int = ICON_SIZE) -> str:
    """Return the icon as a Base64-encoded PNG string (no newlines)."""
    return base64.b64encode(get_icon_bytes(size)).decode("ascii")


def get_photo_image(root, size: int = ICON_SIZE):  # noqa: ANN001
    """
    Return a ``tk.PhotoImage`` suitable for ``root.iconphoto(True, icon)``.

    Parameters
    ----------
    root : tk.Tk or tk.Toplevel
        The Tk window (needed to keep a reference — do NOT let it GC).
    size : int
        Icon dimension in pixels.
    """
    import tkinter as tk
    data = get_icon_base64(size)
    return tk.PhotoImage(data=data, master=root)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tkinter as tk

    root = tk.Tk()
    root.title("icon.py — test")
    root.configure(bg="#0d0d0d")

    icon = get_photo_image(root, size=48)
    root.iconphoto(True, icon)

    # Display larger preview (256px) in window
    preview = get_photo_image(root, size=256)
    lbl = tk.Label(root, image=preview, bg="#0d0d0d")
    lbl.image = preview          # keep reference
    lbl.pack(padx=20, pady=20)

    info_lbl = tk.Label(
        root,
        text=f"Icon loaded — {ICON_SIZE}×{ICON_SIZE} px for titlebar",
        fg="#4da6ff", bg="#0d0d0d",
        font=("Helvetica", 11),
    )
    info_lbl.pack(pady=(0, 16))

    root.mainloop()
