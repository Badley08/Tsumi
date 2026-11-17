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
Tsumi Reader
~~~~~~~~~~~~
Lecteur de manga/webtoon supportant CBZ locaux et URLs distantes.

Modes:
  - PAGED  : affichage page par page (manga classique)
  - SCROLL : défilement vertical continu (webtoon)

Usage::

    root = tk.Tk()
    reader = Reader(root)
    reader.open_cbz("/path/to/chapter.cbz")
    root.mainloop()
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import tkinter as tk
import zipfile
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thème
# ---------------------------------------------------------------------------
BG       = "#0d0d0d"
ACCENT   = "#1671e3"
FG       = "#dddddd"
HUD_BG   = "#1a1a1aCC"  # semi-transparent (simulé)

# ---------------------------------------------------------------------------
# Dossier de configuration
# ---------------------------------------------------------------------------
CONFIG_DIR  = Path.home() / ".tsumi"
PROGRESS_FILE = CONFIG_DIR / "progress.json"


def _load_progress() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_progress(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Image loader helpers
# ---------------------------------------------------------------------------

def _load_image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Redimensionne l'image pour tenir dans (max_w, max_h) en préservant le ratio."""
    if max_w <= 0 or max_h <= 0:
        return img
    w, h = img.size
    ratio = min(max_w / w, max_h / h, 1.0)  # jamais upscale
    nw, nh = int(w * ratio), int(h * ratio)
    if (nw, nh) == (w, h):
        return img
    return img.resize((nw, nh), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Reader widget
# ---------------------------------------------------------------------------

class Reader(tk.Frame):
    """Lecteur CBZ/online intégrable dans une fenêtre Tkinter parent.

    Parameters
    ----------
    master :
        Widget parent Tkinter.
    mode : str
        ``"paged"`` (défaut) ou ``"scroll"``.
    rtl : bool
        ``True`` pour lecture droite→gauche (manga japonais).
    """

    MODE_PAGED  = "paged"
    MODE_SCROLL = "scroll"

    def __init__(
        self,
        master: tk.Misc,
        mode: str = MODE_PAGED,
        rtl: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=BG, **kwargs)

        self._mode   = mode
        self._rtl    = rtl
        self._pages: list[bytes] = []        # données brutes des images
        self._page_idx: int = 0              # page courante (mode paged)
        self._total: int = 0

        # Métadonnées (pour sauvegarde)
        self._source  : str = ""
        self._manga   : str = ""
        self._chapter : str = ""

        # Cache d'images Tk (évite la garbage collection)
        self._tk_cache: dict[int, ImageTk.PhotoImage] = {}

        # Préchargement
        self._preload_thread: Optional[threading.Thread] = None
        self._preload_lock = threading.Lock()

        # HUD
        self._hud_job: Optional[str] = None  # after() handle

        # Scroll mode
        self._scroll_images: list[ImageTk.PhotoImage] = []
        self._scroll_canvas_items: list[int] = []
        self._lazy_loaded: set[int] = set()

        self._build_ui()
        self._bind_keys()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_cbz(self, path: str) -> None:
        """Ouvre un fichier CBZ/ZIP local."""
        path = Path(path)
        if not path.exists():
            logger.error("CBZ introuvable: %s", path)
            return

        pages: list[bytes] = []
        with zipfile.ZipFile(path, "r") as zf:
            names = sorted(
                [n for n in zf.namelist() if not n.startswith("__MACOSX")
                 and not n.endswith("/")]
            )
            for name in names:
                pages.append(zf.read(name))

        self._manga   = path.parent.name
        self._chapter = path.stem          # ex: "chap12"
        self._source  = path.parent.parent.name
        self._load_pages(pages)

    def open_online(
        self,
        pages: list[str],
        source: str = "",
        manga: str = "",
        chapter: str = "",
    ) -> None:
        """Ouvre une liste d'URLs distantes.

        Les images sont téléchargées en arrière-plan au fur et à mesure.
        """
        self._source  = str(source)
        self._manga   = str(manga)
        self._chapter = str(chapter)

        # Prépare les slots (None = pas encore chargé)
        self._pages = [b""] * len(pages)
        self._urls  = pages
        self._total = len(pages)

        # Affiche un placeholder immédiatement
        self._page_idx = self._get_saved_page()
        self._show_placeholder(self._page_idx)
        self._show_hud()

        # Charge en background
        def _bg_load():
            sess = requests.Session()
            sess.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
            for idx, url in enumerate(pages):
                try:
                    r = sess.get(url, timeout=(10, 30))
                    r.raise_for_status()
                    self._pages[idx] = r.content
                    # Si c'est la page courante ou la suivante, rafraîchit
                    if idx in (self._page_idx, self._page_idx + 1):
                        self.after(0, self._display_current)
                except Exception as exc:
                    logger.warning("Erreur chargement page %d: %s", idx, exc)

        t = threading.Thread(target=_bg_load, daemon=True, name="tsumi-online-load")
        t.start()

    # ------------------------------------------------------------------
    # Page loading
    # ------------------------------------------------------------------

    def _load_pages(self, pages: list[bytes]) -> None:
        self._pages = pages if not self._rtl else list(reversed(pages))
        self._total = len(pages)
        self._tk_cache.clear()
        self._page_idx = self._get_saved_page()
        if self._mode == self.MODE_SCROLL:
            self._setup_scroll_mode()
        else:
            self._display_current()
        self._show_hud()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Canvas principal
        self._canvas = tk.Canvas(
            self, bg=BG, highlightthickness=0, cursor="hand2"
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbar vertical (mode scroll webtoon)
        self._vsb = tk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview,
            bg=BG, troughcolor=BG, activebackground=ACCENT,
        )
        self._canvas.configure(yscrollcommand=self._vsb.set)

        # HUD label (overlay "Page X / Y")
        self._hud = tk.Label(
            self,
            text="",
            bg="#1c1c1c",
            fg=FG,
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=4,
        )

        # Barre de navigation (mode paged)
        self._nav_bar = tk.Frame(self, bg="#111111", height=36)
        self._nav_bar.grid(row=1, column=0, sticky="ew")
        self._nav_bar.columnconfigure(1, weight=1)

        from assets.icons import (
            draw_icon_arrow_left, draw_icon_arrow_right,
            draw_icon_scroll, draw_icon_book,
        )
        from menu.Menu import TsumiButton

        self._btn_prev = TsumiButton(
            self._nav_bar,
            icon_fn=draw_icon_arrow_left,
            text="Précédent",
            command=self.prev_page,
            width=130, height=36,
        )
        self._btn_prev.grid(row=0, column=0, sticky="w", padx=4, pady=2)

        self._page_label = tk.Label(
            self._nav_bar, text="", bg="#111111", fg=FG,
            font=("Segoe UI", 10),
        )
        self._page_label.grid(row=0, column=1)

        self._btn_next = TsumiButton(
            self._nav_bar,
            icon_fn=draw_icon_arrow_right,
            text="Suivant",
            command=self.next_page,
            width=120, height=36,
        )
        self._btn_next.grid(row=0, column=2, sticky="e", padx=4, pady=2)

        self._btn_mode = TsumiButton(
            self._nav_bar,
            icon_fn=draw_icon_scroll,
            text="Scroll",
            command=self._toggle_mode,
            width=110, height=36,
        )
        self._btn_mode.grid(row=0, column=3, padx=4, pady=2)

    def _bind_keys(self) -> None:
        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<Button-1>", self._on_left_click)
        self._canvas.bind("<Button-3>", self._on_right_click)
        self._canvas.bind("<Double-Button-1>", self._on_double_click)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        # Bind sur le frame aussi pour attraper les événements clavier
        self.bind_all("<Right>",    lambda e: self.next_page())
        self.bind_all("<Left>",     lambda e: self.prev_page())
        self.bind_all("<d>",        lambda e: self.next_page())
        self.bind_all("<a>",        lambda e: self.prev_page())
        self.bind_all("<f>",        lambda e: self._toggle_fullscreen())
        self.bind_all("<F>",        lambda e: self._toggle_fullscreen())
        self.bind_all("<Escape>",   lambda e: self._on_escape())
        self.bind_all("<r>",        lambda e: self._toggle_rtl())
        self.bind_all("<R>",        lambda e: self._toggle_rtl())

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def next_page(self) -> None:
        if self._mode == self.MODE_SCROLL:
            self._canvas.yview_scroll(5, "units")
            return
        if self._page_idx < self._total - 1:
            self._page_idx += 1
            self._display_current()
            self._show_hud()
            self._save_progress_now()
            self._start_preload(self._page_idx + 1)

    def prev_page(self) -> None:
        if self._mode == self.MODE_SCROLL:
            self._canvas.yview_scroll(-5, "units")
            return
        if self._page_idx > 0:
            self._page_idx -= 1
            self._display_current()
            self._show_hud()
            self._save_progress_now()

    def go_to_page(self, idx: int) -> None:
        if 0 <= idx < self._total:
            self._page_idx = idx
            self._display_current()
            self._show_hud()
            self._save_progress_now()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _display_current(self) -> None:
        """Affiche la page courante sur le canvas."""
        if self._mode == self.MODE_SCROLL:
            return  # Le mode scroll gère l'affichage lui-même

        idx = self._page_idx
        self._canvas.delete("all")

        if not self._pages or not self._pages[idx]:
            self._show_placeholder(idx)
            return

        tk_img = self._get_tk_image(idx)
        if tk_img is None:
            self._show_placeholder(idx)
            return

        cw = self._canvas.winfo_width()  or 800
        ch = self._canvas.winfo_height() or 600
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=tk_img)
        self._page_label.config(
            text=f"Page {idx + 1} / {self._total}"
        )
        # Précharge la suivante
        self._start_preload(idx + 1)

    def _show_placeholder(self, idx: int) -> None:
        cw = self._canvas.winfo_width()  or 800
        ch = self._canvas.winfo_height() or 600
        self._canvas.create_rectangle(0, 0, cw, ch, fill=BG, outline="")
        self._canvas.create_text(
            cw // 2, ch // 2,
            text=f"Chargement page {idx + 1}…",
            fill=FG, font=("Segoe UI", 14),
        )

    def _get_tk_image(self, idx: int) -> Optional[ImageTk.PhotoImage]:
        """Retourne un PhotoImage pour la page idx (avec cache)."""
        if idx in self._tk_cache:
            return self._tk_cache[idx]
        if idx >= len(self._pages) or not self._pages[idx]:
            return None
        try:
            img = _load_image_from_bytes(self._pages[idx])
            cw = self._canvas.winfo_width()  or 800
            ch = self._canvas.winfo_height() or 600
            img = _fit_image(img, cw, ch)
            tk_img = ImageTk.PhotoImage(img)
            self._tk_cache[idx] = tk_img
            # Évite une mémoire illimitée — garde max 5 pages en cache
            if len(self._tk_cache) > 5:
                old = min(self._tk_cache)
                del self._tk_cache[old]
            return tk_img
        except Exception as exc:
            logger.warning("Impossible de décoder l'image %d: %s", idx, exc)
            return None

    # ------------------------------------------------------------------
    # Scroll (webtoon) mode
    # ------------------------------------------------------------------

    def _setup_scroll_mode(self) -> None:
        """Construit l'affichage scroll vertical continu."""
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._nav_bar.grid_remove()
        self._canvas.delete("all")
        self._scroll_images.clear()
        self._scroll_canvas_items.clear()
        self._lazy_loaded.clear()

        # Calcule la largeur disponible
        self.update_idletasks()
        cw = self._canvas.winfo_width() or 800

        y_offset = 10
        for idx in range(self._total):
            # Réserve de l'espace pour chaque image (lazy)
            ph_id = self._canvas.create_rectangle(
                10, y_offset, cw - 10, y_offset + 300,
                fill="#1a1a1a", outline="",
                tags=(f"ph_{idx}",),
            )
            lbl_id = self._canvas.create_text(
                cw // 2, y_offset + 150,
                text=f"Page {idx + 1}",
                fill="#444444", font=("Segoe UI", 10),
                tags=(f"lbl_{idx}",),
            )
            self._scroll_canvas_items.append((y_offset, ph_id, lbl_id))
            y_offset += 310

        self._canvas.configure(scrollregion=(0, 0, cw, y_offset))

        # Charge les premières images
        for i in range(min(3, self._total)):
            self._lazy_load_scroll_page(i)

        # Surveille le scroll pour le lazy-loading
        self._canvas.bind("<Configure>", self._on_scroll_resize)
        self._vsb.bind("<ButtonRelease-1>", self._on_scroll_changed)
        self._canvas.bind("<MouseWheel>", self._on_scroll_wheel)

    def _lazy_load_scroll_page(self, idx: int) -> None:
        if idx in self._lazy_loaded or idx >= len(self._pages):
            return
        self._lazy_loaded.add(idx)

        def _load():
            tk_img = self._get_tk_image_scroll(idx)
            if tk_img:
                self.after(0, lambda: self._place_scroll_image(idx, tk_img))

        threading.Thread(target=_load, daemon=True, name=f"tsumi-lazy-{idx}").start()

    def _get_tk_image_scroll(self, idx: int) -> Optional[ImageTk.PhotoImage]:
        if not self._pages[idx]:
            return None
        try:
            img  = _load_image_from_bytes(self._pages[idx])
            cw   = self._canvas.winfo_width() or 800
            img  = _fit_image(img, cw - 20, 99999)   # largeur fixe, hauteur libre
            tk_img = ImageTk.PhotoImage(img)
            return tk_img
        except Exception as exc:
            logger.warning("scroll img %d: %s", idx, exc)
            return None

    def _place_scroll_image(self, idx: int, tk_img: ImageTk.PhotoImage) -> None:
        if idx >= len(self._scroll_canvas_items):
            return
        y_offset, ph_id, lbl_id = self._scroll_canvas_items[idx]
        iw, ih = tk_img.width(), tk_img.height()
        cw = self._canvas.winfo_width() or 800

        # Supprime le placeholder
        self._canvas.delete(ph_id)
        self._canvas.delete(lbl_id)

        # Place l'image
        img_id = self._canvas.create_image(
            cw // 2, y_offset, anchor="n", image=tk_img,
            tags=(f"img_{idx}",)
        )
        self._scroll_images.append(tk_img)  # prevent GC

        # Ajuste la scrollregion si la hauteur réelle diffère
        # (simplification : on remet à jour après tout chargement)

    def _on_scroll_changed(self, _event=None) -> None:
        # Charge les pages visibles + N+2 suivantes
        view = self._canvas.yview()
        total_h = self._canvas.bbox("all")
        if not total_h:
            return
        visible_top    = view[0] * total_h[3]
        visible_bottom = view[1] * total_h[3]
        for idx, (y_off, *_) in enumerate(self._scroll_canvas_items):
            if visible_top - 500 <= y_off <= visible_bottom + 500:
                self._lazy_load_scroll_page(idx)

    def _on_scroll_wheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._on_scroll_changed()

    def _on_scroll_resize(self, _event=None) -> None:
        pass  # TODO: recalculer la scrollregion

    # ------------------------------------------------------------------
    # HUD overlay "Page X / Y"
    # ------------------------------------------------------------------

    def _show_hud(self) -> None:
        if not self._total:
            return
        self._hud.config(text=f"Page {self._page_idx + 1} / {self._total}")
        # Place le HUD en bas à droite
        self._hud.place(relx=1.0, rely=1.0, x=-60, y=-60, anchor="se")
        self._hud.lift()
        # Annule le timer précédent
        if self._hud_job:
            try:
                self.after_cancel(self._hud_job)
            except Exception:
                pass
        # Fade-out après 2s (simulé par disparition)
        self._hud_alpha = 10
        self._hud_job = self.after(2000, self._fade_hud)

    def _fade_hud(self) -> None:
        """Fait disparaître le HUD en réduisant progressivement l'opacité (simulé)."""
        # Tkinter ne supporte pas nativement l'opacité des widgets,
        # on simule en réduisant le contraste progressivement.
        alpha = self._hud_alpha
        if alpha <= 0:
            self._hud.place_forget()
            self._hud_job = None
            return
        # Interpole la couleur de fond et du texte vers BG
        level = int(alpha * 25)  # 0-255
        hex_level = f"{level:02x}"
        self._hud.config(fg=f"#{hex_level}{hex_level}{hex_level}")
        self._hud_alpha -= 1
        self._hud_job = self.after(50, self._fade_hud)

    # ------------------------------------------------------------------
    # Préchargement
    # ------------------------------------------------------------------

    def _start_preload(self, idx: int) -> None:
        if idx < 0 or idx >= self._total:
            return
        if idx in self._tk_cache:
            return

        def _preload():
            with self._preload_lock:
                self._get_tk_image(idx)

        t = threading.Thread(target=_preload, daemon=True, name="tsumi-preload")
        t.start()
        self._preload_thread = t

    # ------------------------------------------------------------------
    # Progress persistence
    # ------------------------------------------------------------------

    def _progress_key(self) -> str:
        return f"{self._source}::{self._manga}::{self._chapter}"

    def _get_saved_page(self) -> int:
        data = _load_progress()
        key  = self._progress_key()
        return data.get(key, {}).get("page", 0)

    def _save_progress_now(self) -> None:
        data = _load_progress()
        data[self._progress_key()] = {
            "page":    self._page_idx,
            "chapter": self._chapter,
            "manga":   self._manga,
            "source":  self._source,
            "ts":      int(time.time()),
        }
        _save_progress(data)

    # ------------------------------------------------------------------
    # Keyboard / mouse handlers
    # ------------------------------------------------------------------

    def _on_left_click(self, event: tk.Event) -> None:
        if self._mode == self.MODE_PAGED:
            self.next_page()

    def _on_right_click(self, event: tk.Event) -> None:
        if self._mode == self.MODE_PAGED:
            self.prev_page()

    def _on_double_click(self, _event: tk.Event) -> None:
        self._toggle_fullscreen()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self._mode == self.MODE_SCROLL:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.delta < 0:
                self.next_page()
            else:
                self.prev_page()

    def _on_resize(self, _event: tk.Event) -> None:
        # Vide le cache pour recalculer les tailles
        self._tk_cache.clear()
        if self._mode == self.MODE_PAGED:
            self._display_current()

    def _on_escape(self) -> None:
        # Quitte le plein écran si actif, sinon remonte au parent
        win = self.winfo_toplevel()
        if win.attributes("-fullscreen"):
            win.attributes("-fullscreen", False)
        else:
            # Ferme la fenêtre reader si elle est standalone
            win.destroy()

    def _toggle_fullscreen(self) -> None:
        win = self.winfo_toplevel()
        current = win.attributes("-fullscreen")
        win.attributes("-fullscreen", not current)

    def _toggle_rtl(self) -> None:
        self._rtl = not self._rtl
        # Inverse l'ordre des pages
        self._pages.reverse()
        self._page_idx = max(0, self._total - 1 - self._page_idx)
        self._tk_cache.clear()
        self._display_current()
        self._show_hud()

    def _toggle_mode(self) -> None:
        if self._mode == self.MODE_PAGED:
            self._mode = self.MODE_SCROLL
            self._btn_mode.config_text("Paged")
            self._setup_scroll_mode()
        else:
            self._mode = self.MODE_PAGED
            self._btn_mode.config_text("Scroll")
            self._vsb.grid_remove()
            self._nav_bar.grid()
            self._display_current()


# ---------------------------------------------------------------------------
# Standalone window (utile pour ouvrir un CBZ depuis le gestionnaire de fichiers)
# ---------------------------------------------------------------------------

class ReaderWindow(tk.Toplevel):
    """Fenêtre autonome contenant un Reader."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Tsumi Reader")
        self.configure(bg=BG)
        self.geometry("900x700")
        self.minsize(600, 400)

        self.reader = Reader(self)
        self.reader.pack(fill="both", expand=True)

    def open_cbz(self, path: str) -> None:
        self.reader.open_cbz(path)
        name = Path(path).stem
        self.title(f"Tsumi — {name}")

    def open_online(self, pages, source="", manga="", chapter="") -> None:
        self.reader.open_online(pages, source, manga, chapter)
        self.title(f"Tsumi — {manga} ch.{chapter}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    root = tk.Tk()
    root.withdraw()

    win = ReaderWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)

    if len(sys.argv) > 1:
        cbz = sys.argv[1]
        win.open_cbz(cbz)
    else:
        # Demo: image placeholder
        win.reader._total = 5
        win.reader._pages = [b""] * 5
        win.reader._show_hud()

    root.mainloop()
