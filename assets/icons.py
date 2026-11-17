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
assets/icons.py — Canvas-drawn SVG-style icons for Tsumi UI

All public functions follow the signature:
    draw_icon_*(canvas, x, y, size=24, color="#dddddd", **kw) -> list[int]

Parameters
----------
canvas : tk.Canvas
    The target canvas to draw on.
x, y : int | float
    Centre point of the icon (not top-left).
size : int
    Icon bounding box in pixels (square). Default 24.
color : str
    Stroke/fill colour.  Defaults to the Tsumi text colour #dddddd.

Returns
-------
list[int]
    Canvas item IDs (useful for later deletion/animation).

Usage example
-------------
    from assets.icons import draw_icon_home
    ids = draw_icon_home(canvas, x=20, y=20, size=24, color="#4da6ff")
    # To delete later:
    for item_id in ids: canvas.delete(item_id)
"""

from __future__ import annotations
from typing import List


# ── Helpers ───────────────────────────────────────────────────────────────────

def _r(x: float, y: float, size: float):
    """Return (x0, y0) — top-left corner — from centre (x, y) and size."""
    h = size / 2
    return x - h, y - h


def _pt(cx: float, cy: float, size: float, rx: float, ry: float):
    """
    Map relative coordinates [−1 … 1] to canvas coordinates.
    rx, ry: position within the icon, normalised to [−1 … 1].
    """
    h = size / 2
    return cx + rx * h, cy + ry * h


def _lw(size: float) -> float:
    """Scale-aware line width (minimum 1 px)."""
    return max(1.0, round(size / 20, 1))


# ── Home ──────────────────────────────────────────────────────────────────────

def draw_icon_home(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """House outline — used for Library / Home."""
    ids = []
    lw = _lw(size)
    # Roof triangle
    roof = [
        _pt(x, y, size, -0.85, 0.1),
        _pt(x, y, size,  0.00, -0.90),
        _pt(x, y, size,  0.85, 0.1),
    ]
    ids.append(canvas.create_polygon(
        *[c for pt in roof for c in pt],
        outline=color, fill="", width=lw,
    ))
    # Walls
    wall = [
        _pt(x, y, size, -0.6,  0.1),
        _pt(x, y, size, -0.6,  0.95),
        _pt(x, y, size,  0.6,  0.95),
        _pt(x, y, size,  0.6,  0.1),
    ]
    ids.append(canvas.create_polygon(
        *[c for pt in wall for c in pt],
        outline=color, fill="", width=lw,
    ))
    # Door
    dx0, dy0 = _pt(x, y, size, -0.22, 0.95)
    dx1, dy1 = _pt(x, y, size,  0.22, 0.45)
    ids.append(canvas.create_rectangle(dx0, dy1, dx1, dy0, outline=color, width=lw))
    return ids


# ── Download ──────────────────────────────────────────────────────────────────

def draw_icon_download(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Down-arrow with underline — Downloads."""
    ids = []
    lw = _lw(size)
    # Vertical stem
    ax, ay = _pt(x, y, size, 0, -0.75)
    bx, by = _pt(x, y, size, 0,  0.20)
    ids.append(canvas.create_line(ax, ay, bx, by, fill=color, width=lw, capstyle="round"))
    # Arrow head
    head = [
        _pt(x, y, size, -0.45, -0.10),
        _pt(x, y, size,  0.00,  0.50),
        _pt(x, y, size,  0.45, -0.10),
    ]
    ids.append(canvas.create_polygon(
        *[c for pt in head for c in pt],
        fill=color, outline=color,
    ))
    # Underline
    lx0, ly = _pt(x, y, size, -0.70, 0.75)
    lx1, _  = _pt(x, y, size,  0.70, 0.75)
    ids.append(canvas.create_line(lx0, ly, lx1, ly, fill=color, width=lw, capstyle="round"))
    return ids


# ── Settings / Gear ───────────────────────────────────────────────────────────

def draw_icon_settings(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Gear (8 teeth) — Settings."""
    import math
    ids = []
    lw = _lw(size)
    teeth = 8
    outer_r = size * 0.46
    inner_r = size * 0.30
    hole_r  = size * 0.14

    pts = []
    for i in range(teeth * 2):
        angle = math.pi / teeth * i - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        pts.extend([x + math.cos(angle) * r, y + math.sin(angle) * r])

    ids.append(canvas.create_polygon(pts, outline=color, fill="", width=lw, smooth=False))
    # Centre hole
    ids.append(canvas.create_oval(
        x - hole_r, y - hole_r, x + hole_r, y + hole_r,
        outline=color, fill="", width=lw,
    ))
    return ids


# ── Book / Library ────────────────────────────────────────────────────────────

def draw_icon_book(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Open book — Library / reading view."""
    ids = []
    lw = _lw(size)
    # Left page
    left = [
        _pt(x, y, size, -0.85, -0.75),
        _pt(x, y, size, -0.05, -0.65),
        _pt(x, y, size, -0.05,  0.80),
        _pt(x, y, size, -0.85,  0.75),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in left for c in p], outline=color, fill="", width=lw,
    ))
    # Right page
    right = [
        _pt(x, y, size,  0.85, -0.75),
        _pt(x, y, size,  0.05, -0.65),
        _pt(x, y, size,  0.05,  0.80),
        _pt(x, y, size,  0.85,  0.75),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in right for c in p], outline=color, fill="", width=lw,
    ))
    # Spine line
    sx, sy0 = _pt(x, y, size, 0, -0.65)
    _,  sy1 = _pt(x, y, size, 0,  0.80)
    ids.append(canvas.create_line(sx, sy0, sx, sy1, fill=color, width=lw))
    return ids


# ── Search / Magnifier ────────────────────────────────────────────────────────

def draw_icon_search(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Magnifying glass — Search / Discover."""
    ids = []
    lw = _lw(size)
    r = size * 0.28
    cx, cy = _pt(x, y, size, -0.20, -0.20)
    ids.append(canvas.create_oval(
        cx - r, cy - r, cx + r, cy + r, outline=color, width=lw,
    ))
    # Handle
    hx0, hy0 = _pt(x, y, size,  0.10,  0.10)
    hx1, hy1 = _pt(x, y, size,  0.75,  0.75)
    ids.append(canvas.create_line(
        hx0, hy0, hx1, hy1, fill=color, width=lw * 1.5, capstyle="round",
    ))
    return ids


# ── Close / X ─────────────────────────────────────────────────────────────────

def draw_icon_close(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """× cross — close / dismiss."""
    ids = []
    lw = _lw(size) * 1.5
    ax0, ay0 = _pt(x, y, size, -0.65, -0.65)
    ax1, ay1 = _pt(x, y, size,  0.65,  0.65)
    ids.append(canvas.create_line(ax0, ay0, ax1, ay1, fill=color, width=lw, capstyle="round"))
    bx0, by0 = _pt(x, y, size,  0.65, -0.65)
    bx1, by1 = _pt(x, y, size, -0.65,  0.65)
    ids.append(canvas.create_line(bx0, by0, bx1, by1, fill=color, width=lw, capstyle="round"))
    return ids


# ── Play ──────────────────────────────────────────────────────────────────────

def draw_icon_play(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Right-pointing triangle — play / open / start reading."""
    ids = []
    pts = [
        _pt(x, y, size, -0.45, -0.80),
        _pt(x, y, size,  0.75,  0.00),
        _pt(x, y, size, -0.45,  0.80),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in pts for c in p], fill=color, outline=color,
    ))
    return ids


# ── Arrow Left ────────────────────────────────────────────────────────────────

def draw_icon_arrow_left(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """← Previous page / back."""
    ids = []
    lw = _lw(size) * 1.5
    # Stem
    sx0, sy = _pt(x, y, size,  0.50, 0)
    sx1, _  = _pt(x, y, size, -0.30, 0)
    ids.append(canvas.create_line(sx0, sy, sx1, sy, fill=color, width=lw, capstyle="round"))
    # Arrowhead
    head = [
        _pt(x, y, size,  0.10, -0.45),
        _pt(x, y, size, -0.65,  0.00),
        _pt(x, y, size,  0.10,  0.45),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in head for c in p], fill=color, outline=color,
    ))
    return ids


# ── Arrow Right ───────────────────────────────────────────────────────────────

def draw_icon_arrow_right(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """→ Next page / forward."""
    ids = []
    lw = _lw(size) * 1.5
    # Stem
    sx0, sy = _pt(x, y, size, -0.50, 0)
    sx1, _  = _pt(x, y, size,  0.30, 0)
    ids.append(canvas.create_line(sx0, sy, sx1, sy, fill=color, width=lw, capstyle="round"))
    # Arrowhead
    head = [
        _pt(x, y, size, -0.10, -0.45),
        _pt(x, y, size,  0.65,  0.00),
        _pt(x, y, size, -0.10,  0.45),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in head for c in p], fill=color, outline=color,
    ))
    return ids


# ── Menu / Hamburger ──────────────────────────────────────────────────────────

def draw_icon_menu(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """≡ Hamburger — sidebar toggle."""
    ids = []
    lw = _lw(size) * 1.3
    for ry in (-0.40, 0.00, 0.40):
        lx0, ly = _pt(x, y, size, -0.65, ry)
        lx1, _  = _pt(x, y, size,  0.65, ry)
        ids.append(canvas.create_line(lx0, ly, lx1, ly, fill=color, width=lw, capstyle="round"))
    return ids


# ── Fullscreen ────────────────────────────────────────────────────────────────

def draw_icon_fullscreen(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Four corners expanding — fullscreen toggle."""
    ids = []
    lw = _lw(size)
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    arm = 0.40
    for sx, sy in corners:
        ox, oy = _pt(x, y, size, sx * 0.60, sy * 0.60)
        # Horizontal arm
        ex, ey = _pt(x, y, size, sx * (0.60 + arm * abs(sx)), sy * 0.60)
        ids.append(canvas.create_line(ox, oy, ex, ey, fill=color, width=lw, capstyle="round"))
        # Vertical arm
        ex2, ey2 = _pt(x, y, size, sx * 0.60, sy * (0.60 + arm * abs(sy)))
        ids.append(canvas.create_line(ox, oy, ex2, ey2, fill=color, width=lw, capstyle="round"))
    return ids


# ── Star / Favourite ──────────────────────────────────────────────────────────

def draw_icon_star(canvas, x, y, size=24, color="#dddddd", filled=False) -> List[int]:
    """★ Favourite / bookmark."""
    import math
    ids = []
    pts = []
    for i in range(10):
        angle = math.pi / 5 * i - math.pi / 2
        r = size * (0.48 if i % 2 == 0 else 0.20)
        pts.extend([x + math.cos(angle) * r, y + math.sin(angle) * r])
    ids.append(canvas.create_polygon(
        pts,
        fill=color if filled else "",
        outline=color,
        width=_lw(size),
    ))
    return ids


# ── Scroll / Webtoon mode ─────────────────────────────────────────────────────

def draw_icon_scroll(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """Vertical scroll lines — Webtoon / scroll mode."""
    ids = []
    lw = _lw(size)
    for ry in (-0.60, -0.20, 0.20, 0.60):
        lx0, ly = _pt(x, y, size, -0.65, ry)
        lx1, _  = _pt(x, y, size,  0.65, ry)
        ids.append(canvas.create_line(lx0, ly, lx1, ly, fill=color, width=lw, capstyle="round"))
    # Down arrow on right edge
    ax, ay0 = _pt(x, y, size, 0.65, 0.40)
    _,  ay1 = _pt(x, y, size, 0.65, 0.80)
    ids.append(canvas.create_line(ax, ay0, ax, ay1, fill=color, width=lw, capstyle="round"))
    hx0, hy = _pt(x, y, size, 0.45, 0.65)
    hx1, _  = _pt(x, y, size, 0.85, 0.65)
    ids.append(canvas.create_line(hx0, hy, ax, ay1, fill=color, width=lw, capstyle="round"))
    ids.append(canvas.create_line(hx1, hy, ax, ay1, fill=color, width=lw, capstyle="round"))
    return ids


# ── RTL / LTR toggle ──────────────────────────────────────────────────────────

def draw_icon_rtl(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """← Text lines — RTL reading direction."""
    ids = []
    lw = _lw(size)
    for ry in (-0.35, 0.00, 0.35):
        lx0, ly = _pt(x, y, size,  0.65, ry)
        lx1, _  = _pt(x, y, size, -0.30, ry)
        ids.append(canvas.create_line(lx0, ly, lx1, ly, fill=color, width=lw, capstyle="round"))
    head = [
        _pt(x, y, size, -0.00, -0.42),
        _pt(x, y, size, -0.70,  0.00),
        _pt(x, y, size, -0.00,  0.42),
    ]
    ids.append(canvas.create_polygon(
        *[c for p in head for c in p], fill=color, outline=color,
    ))
    return ids


# ── Info ──────────────────────────────────────────────────────────────────────

def draw_icon_info(canvas, x, y, size=24, color="#dddddd") -> List[int]:
    """ⓘ — About / info."""
    ids = []
    lw = _lw(size)
    r = size * 0.46
    ids.append(canvas.create_oval(
        x - r, y - r, x + r, y + r, outline=color, width=lw,
    ))
    # Dot
    dot = size * 0.07
    dx, dy = _pt(x, y, size, 0, -0.40)
    ids.append(canvas.create_oval(dx - dot, dy - dot, dx + dot, dy + dot, fill=color, outline=""))
    # Stem
    sx, sy0 = _pt(x, y, size, 0, -0.15)
    _,  sy1 = _pt(x, y, size, 0,  0.50)
    ids.append(canvas.create_line(sx, sy0, sx, sy1, fill=color, width=lw * 1.3, capstyle="round"))
    return ids


# ── Preview / test harness ────────────────────────────────────────────────────

if __name__ == "__main__":
    import tkinter as tk

    ICONS = [
        ("home",         draw_icon_home),
        ("download",     draw_icon_download),
        ("settings",     draw_icon_settings),
        ("book",         draw_icon_book),
        ("search",       draw_icon_search),
        ("close",        draw_icon_close),
        ("play",         draw_icon_play),
        ("arrow_left",   draw_icon_arrow_left),
        ("arrow_right",  draw_icon_arrow_right),
        ("menu",         draw_icon_menu),
        ("fullscreen",   draw_icon_fullscreen),
        ("star",         draw_icon_star),
        ("scroll",       draw_icon_scroll),
        ("rtl",          draw_icon_rtl),
        ("info",         draw_icon_info),
    ]

    COLS = 5
    CELL = 80
    SIZE = 36
    ROWS = -(-len(ICONS) // COLS)

    root = tk.Tk()
    root.title("Tsumi Icons Preview")
    root.configure(bg="#0d0d0d")

    cv = tk.Canvas(
        root,
        width=COLS * CELL, height=ROWS * CELL,
        bg="#0d0d0d", highlightthickness=0,
    )
    cv.pack(padx=8, pady=8)

    for i, (name, fn) in enumerate(ICONS):
        col = i % COLS
        row = i // COLS
        cx = col * CELL + CELL // 2
        cy = row * CELL + CELL // 2 - 10
        fn(cv, cx, cy, size=SIZE, color="#4da6ff")
        cv.create_text(cx, cy + SIZE // 2 + 10, text=name,
                       fill="#888888", font=("Helvetica", 8))

    root.mainloop()
