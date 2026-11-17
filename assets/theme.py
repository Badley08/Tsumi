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
assets/theme.py — Palette de couleurs, polices et Scrollbar sombre personnalisée.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

# ── Couleurs ──────────────────────────────────────────────────────────────────
BG       = "#0d0d0d"
BG2      = "#131313"
BG3      = "#1c1c1c"
BG_CARD  = "#161616"
BG_CARD_HOVER = "#202020"
ACCENT   = "#1671e3"
ACCENT_H = "#2d8cff"
FG       = "#e6e6e6"
FG_DIM   = "#888888"

# ── Polices ───────────────────────────────────────────────────────────────────
_UI_CANDIDATES = [
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "Ubuntu",
    "Segoe UI",
    "Arial",
]

_KANJI_CANDIDATES = [
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "IPAGothic",
    "Yu Gothic",
    "MS Gothic",
    "TkDefaultFont",
]

_UI_FONT: str | None = None
_KANJI_FONT: str | None = None


def _pick_font(candidates: list[str]) -> str:
    try:
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return name
    except Exception:
        pass
    return "TkDefaultFont"


def ui_font(size: int = 10, weight: str = "normal") -> tuple:
    global _UI_FONT
    if _UI_FONT is None:
        _UI_FONT = _pick_font(_UI_CANDIDATES)
    return (_UI_FONT, size, weight)


def kanji_font(size: int = 22, weight: str = "bold") -> tuple:
    global _KANJI_FONT
    if _KANJI_FONT is None:
        _KANJI_FONT = _pick_font(_KANJI_CANDIDATES)
    return (_KANJI_FONT, size, weight)


# ── DarkScrollbar (Canvas pur, zéro widget natif blanc moche) ──────────────────

class DarkScrollbar(tk.Canvas):
    """Scrollbar verticale moderne et sombre dessinée sur Canvas.
    Élimine complètement la scrollbar blanche native de Windows / Linux.
    """

    def __init__(self, master, command=None, width=10, bg="#0d0d0d", thumb_color="#262626", thumb_hover="#3d3d3d", **kwargs):
        super().__init__(master, width=width, bg=bg, highlightthickness=0, **kwargs)
        self._command = command
        self._thumb_color = thumb_color
        self._thumb_hover = thumb_hover
        self._is_hovered = False
        self._drag_data = {"y": 0}

        self._top = 0.0
        self._bottom = 1.0

        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)

    def set(self, top, bottom):
        self._top = float(top)
        self._bottom = float(bottom)
        self._redraw()

    def _redraw(self, event=None):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h <= 1:
            return

        y1 = max(2, int(self._top * h))
        y2 = min(h - 2, int(self._bottom * h))

        if y2 - y1 < 16:
            y2 = y1 + 16

        color = self._thumb_hover if self._is_hovered else self._thumb_color

        # Curseur avec coins légèrement arrondis
        pad = 2
        r = 3
        self.create_polygon(
            pad + r, y1,
            w - pad - r, y1,
            w - pad, y1 + r,
            w - pad, y2 - r,
            w - pad - r, y2,
            pad + r, y2,
            pad, y2 - r,
            pad, y1 + r,
            fill=color, outline="", smooth=True,
        )

    def _on_enter(self, _e):
        self._is_hovered = True
        self._redraw()

    def _on_leave(self, _e):
        self._is_hovered = False
        self._redraw()

    def _on_click(self, event):
        h = self.winfo_height()
        click_ratio = event.y / h
        cur_mid = (self._top + self._bottom) / 2
        if click_ratio < self._top:
            if self._command:
                self._command("scroll", -1, "pages")
        elif click_ratio > self._bottom:
            if self._command:
                self._command("scroll", 1, "pages")
        else:
            self._drag_data["y"] = event.y

    def _on_drag(self, event):
        h = self.winfo_height()
        if h <= 0:
            return
        dy = event.y - self._drag_data["y"]
        self._drag_data["y"] = event.y
        delta_ratio = dy / h
        new_top = max(0.0, min(1.0 - (self._bottom - self._top), self._top + delta_ratio))
        if self._command:
            self._command("moveto", new_top)
