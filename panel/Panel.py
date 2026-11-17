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
panel/Panel.py — Bibliothèque de l'utilisateur (style Tachiyomi).
"""

from __future__ import annotations

import io
import json
import logging
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path
from typing import Callable, Optional

import requests
from PIL import Image, ImageTk

from assets.theme import (
    ACCENT, ACCENT_H, BG, BG2, BG3, FG, FG_DIM,
    ui_font,
)

logger = logging.getLogger(__name__)

CONFIG_DIR   = Path.home() / ".tsumi"
LIBRARY_FILE = CONFIG_DIR / "library.json"

COVER_W = 140
COVER_H = 200
GRID_PAD = 12

CATEGORIES = ["Tout", "Manga", "Manhwa", "Manhua", "Webtoon"]
SORTS = ["Nom A-Z", "Date ajout", "Progression"]


def _load_library() -> list[dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if LIBRARY_FILE.exists():
        try:
            return json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_library(entries: list[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_cover_thumbnail(url_or_path: str) -> Optional[ImageTk.PhotoImage]:
    try:
        if url_or_path.startswith("http"):
            r = requests.get(url_or_path, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            data = r.content
        else:
            data = Path(url_or_path).read_bytes()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = img.resize((COVER_W, COVER_H), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as exc:
        logger.debug("Cover non chargée (%s): %s", url_or_path, exc)
        return None


class Panel(tk.Frame):
    """Panneau bibliothèque Tsumi."""

    def __init__(
        self,
        master: tk.Misc,
        on_open_chapter: Optional[Callable[[dict], None]] = None,
        on_goto_discover: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=BG, **kwargs)

        self._on_open_chapter = on_open_chapter
        self._on_goto_discover = on_goto_discover

        self._entries: list[dict] = []
        self._filtered: list[dict] = []
        self._cover_cache: dict[str, ImageTk.PhotoImage] = {}
        self._cover_items: list[dict] = []

        self._active_filter = "Tout"
        self._active_sort   = "Nom A-Z"

        self._build_ui()
        self.refresh()

    def add_entry(self, entry: dict) -> None:
        key = (entry.get("title", ""), entry.get("source", ""))
        for existing in self._entries:
            if (existing.get("title"), existing.get("source")) == key:
                existing.update(entry)
                _save_library(self._entries)
                self.refresh()
                return
        entry.setdefault("added_at", int(time.time()))
        entry.setdefault("type", "Manga")
        entry.setdefault("chapter", 1)
        entry.setdefault("page", 1)
        self._entries.append(entry)
        _save_library(self._entries)
        self.refresh()

    def remove_entry(self, title: str, source: str = "") -> None:
        self._entries = [
            e for e in self._entries
            if not (e.get("title") == title and e.get("source", "") == source)
        ]
        _save_library(self._entries)
        self.refresh()

    def refresh(self) -> None:
        self._entries = _load_library()
        self._apply_filter_sort()
        self._draw_grid()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Barre supérieure
        top_bar = tk.Frame(self, bg=BG2, height=48, padx=12)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.pack_propagate(False)

        # Filtres
        self._filter_btns: dict[str, tk.Button] = {}
        for cat in CATEGORIES:
            btn = tk.Button(
                top_bar, text=cat,
                bg=BG2, fg=FG_DIM,
                activebackground=ACCENT, activeforeground="white",
                relief="flat", padx=10, pady=3,
                font=ui_font(9),
                cursor="hand2",
                command=lambda c=cat: self._set_filter(c),
            )
            btn.pack(side="left", padx=2, pady=8)
            self._filter_btns[cat] = btn

        self._filter_btns["Tout"].config(bg=ACCENT, fg="white")

        # Bouton Explorer / Découvrir
        btn_explore = tk.Button(
            top_bar, text="+ Explorer les sources",
            bg=ACCENT, fg="white",
            activebackground=ACCENT_H, activeforeground="white",
            relief="flat", padx=12, pady=3,
            font=ui_font(9, "bold"),
            cursor="hand2",
            command=self._on_explore_clicked,
        )
        btn_explore.pack(side="right", padx=6, pady=8)

        # Tri
        self._sort_var = tk.StringVar(value=self._active_sort)
        sort_menu = ttk.Combobox(
            top_bar,
            textvariable=self._sort_var,
            values=SORTS,
            state="readonly",
            width=12,
            font=ui_font(9),
        )
        sort_menu.pack(side="right", padx=6, pady=8)
        sort_menu.bind("<<ComboboxSelected>>", self._on_sort_changed)

        tk.Label(top_bar, text="Trier par :", bg=BG2, fg=FG_DIM,
                 font=ui_font(9)).pack(side="right", padx=(10, 2), pady=8)

        # Corps scrollable
        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        vsb = tk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=vsb.set)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._inner_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )

        self._inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._inner_window, width=e.width))
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ── Filtres / Tri ────────────────────────────────────────────────────────

    def _set_filter(self, cat: str) -> None:
        self._active_filter = cat
        for c, btn in self._filter_btns.items():
            if c == cat:
                btn.config(bg=ACCENT, fg="white")
            else:
                btn.config(bg=BG2, fg=FG_DIM)
        self._apply_filter_sort()
        self._draw_grid()

    def _on_sort_changed(self, _event=None) -> None:
        self._active_sort = self._sort_var.get()
        self._apply_filter_sort()
        self._draw_grid()

    def _apply_filter_sort(self) -> None:
        if self._active_filter == "Tout":
            filtered = list(self._entries)
        else:
            filtered = [
                e for e in self._entries
                if e.get("type", "Manga") == self._active_filter
            ]

        sort = self._active_sort
        if sort == "Nom A-Z":
            filtered.sort(key=lambda e: e.get("title", "").lower())
        elif sort == "Date ajout":
            filtered.sort(key=lambda e: e.get("added_at", 0), reverse=True)
        elif sort == "Progression":
            def _prog(e):
                try:
                    return float(e.get("chapter", 0)) * 1000 + float(e.get("page", 0))
                except (TypeError, ValueError):
                    return 0
            filtered.sort(key=_prog, reverse=True)

        self._filtered = filtered

    # ── Grille ───────────────────────────────────────────────────────────────

    def _draw_grid(self) -> None:
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._cover_items.clear()

        if not self._filtered:
            self._show_empty_state()
            return

        self._inner.update_idletasks()
        grid_w = self._canvas.winfo_width() or 800
        cols   = max(1, (grid_w - GRID_PAD) // (COVER_W + GRID_PAD))

        for idx, entry in enumerate(self._filtered):
            row = idx // cols
            col = idx % cols
            card = self._make_card(entry)
            card.grid(row=row, column=col, padx=GRID_PAD, pady=GRID_PAD, sticky="n")

    def _make_card(self, entry: dict) -> tk.Frame:
        card = tk.Frame(self._inner, bg=BG2, cursor="hand2", padx=4, pady=4)

        cv = tk.Canvas(card, width=COVER_W, height=COVER_H, bg=BG3, highlightthickness=0)
        cv.pack()

        # Progression
        ch = entry.get("chapter", "1")
        badge = tk.Label(
            card, text=f"Ch. {ch}", bg=ACCENT, fg="white",
            font=ui_font(8, "bold"), padx=4, pady=1,
        )
        badge.pack(fill="x")

        # Titre
        title_lbl = tk.Label(
            card, text=entry.get("title", "Sans titre"),
            bg=BG2, fg=FG, font=ui_font(9, "bold"),
            wraplength=COVER_W - 8, justify="center", height=2,
        )
        title_lbl.pack(fill="x", pady=2)

        # Source
        src_lbl = tk.Label(
            card, text=entry.get("source", ""),
            bg=BG2, fg=FG_DIM, font=ui_font(8),
        )
        src_lbl.pack(fill="x")

        # Clic pour ouvrir
        for w in (card, cv, title_lbl, badge, src_lbl):
            w.bind("<Button-1>", lambda _e, e=entry: self._open_entry(e))
            w.bind("<Enter>", lambda _e, c=card: c.config(bg=BG3))
            w.bind("<Leave>", lambda _e, c=card: c.config(bg=BG2))

        cover_url = entry.get("cover", "")
        if cover_url:
            self._load_cover_async(cv, cover_url)

        return card

    def _load_cover_async(self, canvas: tk.Canvas, url: str) -> None:
        def _load():
            if url in self._cover_cache:
                tk_img = self._cover_cache[url]
            else:
                tk_img = _load_cover_thumbnail(url)
                if tk_img:
                    self._cover_cache[url] = tk_img

            if tk_img:
                def _place():
                    try:
                        canvas.delete("all")
                        canvas.create_image(0, 0, anchor="nw", image=tk_img)
                        canvas._img = tk_img
                    except tk.TclError:
                        pass
                canvas.after(0, _place)

        threading.Thread(target=_load, daemon=True).start()

    def _show_empty_state(self) -> None:
        box = tk.Frame(self._inner, bg=BG, pady=60)
        box.pack(fill="both", expand=True)

        lbl = tk.Label(
            box,
            text="Votre bibliothèque est vide pour le moment.",
            bg=BG, fg=FG,
            font=ui_font(13, "bold"),
        )
        lbl.pack(pady=(0, 6))

        sub = tk.Label(
            box,
            text="Parcourez les sources (Anime-Sama, Mangas Origines, Rimu Scan, Scantrad IO)\net ajoutez vos séries préférées en un clic !",
            bg=BG, fg=FG_DIM,
            font=ui_font(10),
            justify="center",
        )
        sub.pack(pady=(0, 16))

        btn = tk.Button(
            box,
            text="Explorer les mangas dans Découvrir",
            bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT_H, activeforeground="#ffffff",
            relief="flat", font=ui_font(10, "bold"),
            padx=18, pady=8, cursor="hand2",
            command=self._on_explore_clicked,
        )
        btn.pack()

    def _open_entry(self, entry: dict) -> None:
        if self._on_open_chapter:
            self._on_open_chapter(entry)

    def _on_explore_clicked(self) -> None:
        if self._on_goto_discover:
            self._on_goto_discover()

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
