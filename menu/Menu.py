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
menu/Menu.py — Application principale Tsumi (fenêtre + navigation).

TsumiButton : tk.Frame + tk.Canvas interne (pas d'héritage Canvas).
              Compatible Python 3.11+ / Linux + Windows.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from assets.icons import (
    draw_icon_book,
    draw_icon_close,
    draw_icon_download,
    draw_icon_info,
    draw_icon_search,
    draw_icon_settings,
)
from assets.theme import (
    ACCENT, ACCENT_H, BG, BG2, BG3, FG, FG_DIM,
    kanji_font, ui_font,
)

logger = logging.getLogger(__name__)

SIDEBAR_W = 200
HEADER_H  = 56


# ── TsumiButton : Frame conteneur + Canvas dessiné ───────────────────────────
# On n'hérite PAS de tk.Canvas pour éviter les bugs d'ID sur Tk 8.6+/Py3.13.

class TsumiButton(tk.Frame):
    """Bouton flat — Frame + layout place() en pixels.
    Compatible Python 3.11/3.13, Linux/Windows.
    """

    _BAR_W = 3

    def __init__(
        self,
        master,
        text: str = "",
        icon_fn=None,
        icon_size: int = 18,
        command=None,
        width: int = 160,
        height: int = 40,
        bg: str = BG2,
        bg_hover: str = BG3,
        fg: str = FG,
        fg_hover: str = ACCENT_H,
        active_bg: str = "#152a40",
        radius: int = 6,
    ) -> None:
        super().__init__(master, bg=bg, width=width, height=height, cursor="hand2")
        self.pack_propagate(False)

        self._bg        = bg
        self._bg_hover  = bg_hover
        self._fg        = fg
        self._fg_hover  = fg_hover
        self._active_bg = active_bg
        self._command   = command
        self._icon_fn   = icon_fn
        self._icon_size = icon_size
        self._w_px      = width
        self._h_px      = height
        self._hovered   = False
        self._active    = False

        # ── Barre accent (3 px, gauche) ──────────────────────────────────
        self._bar = tk.Frame(self, bg=bg)
        self._bar.place(x=0, y=0, width=self._BAR_W, relheight=1)

        # ── Zone icône : Frame pixel-sized (pas Label, évite char-units) ─
        icon_w = icon_size + 10
        self._icon_frame = tk.Frame(self, bg=bg)
        self._icon_frame.place(x=self._BAR_W + 4, y=0,
                               width=icon_w, height=height)

        # ── Texte ─────────────────────────────────────────────────────────
        text_x = self._BAR_W + 4 + icon_w + 4
        self._lbl = tk.Label(self, text=text, bg=bg, fg=fg,
                             font=ui_font(10), anchor="w")
        self._lbl.place(x=text_x, y=0, width=width - text_x - 4, relheight=1)

        # ── Bindings ──────────────────────────────────────────────────────
        self._bind_tree(self)
        self.after_idle(self._make_icon)

    # ── Icône ──────────────────────────────────────────────────────────────

    def _make_icon(self) -> None:
        if not self._icon_fn:
            return
        s   = self._icon_size
        bg  = self._cur_bg()
        fg  = self._cur_fg()
        for w in self._icon_frame.winfo_children():
            w.destroy()
        try:
            cv = tk.Canvas(self._icon_frame, width=s, height=s,
                           bg=bg, highlightthickness=0, cursor="hand2")
            cv.place(relx=0.5, rely=0.5, anchor="center", width=s, height=s)
            self._icon_fn(cv, s // 2, s // 2, size=s - 2, color=fg)
            self._bind_tree(cv)
        except Exception as exc:
            logger.debug("TsumiButton icon: %s", exc)

    # ── État ───────────────────────────────────────────────────────────────

    def _cur_bg(self) -> str:
        if self._active:  return self._active_bg
        if self._hovered: return self._bg_hover
        return self._bg

    def _cur_fg(self) -> str:
        if self._active:  return ACCENT
        if self._hovered: return self._fg_hover
        return self._fg

    def _update(self) -> None:
        bg, fg = self._cur_bg(), self._cur_fg()
        self.config(bg=bg)
        self._bar.config(bg=ACCENT if self._active else bg)
        self._icon_frame.config(bg=bg)
        self._lbl.config(bg=bg, fg=fg)
        self._make_icon()

    # ── Bindings récursifs ─────────────────────────────────────────────────

    def _bind_tree(self, w) -> None:
        w.bind("<Enter>",           self._on_enter)
        w.bind("<Leave>",           self._on_leave)
        w.bind("<ButtonPress-1>",   self._on_press)
        w.bind("<ButtonRelease-1>", self._on_release)
        for child in w.winfo_children():
            self._bind_tree(child)

    def _on_enter(self, _e=None) -> None:
        self._hovered = True;  self._update()

    def _on_leave(self, _e=None) -> None:
        self._hovered = False; self._update()

    def _on_press(self, _e=None) -> None:
        self._hovered = False; self._update()

    def _on_release(self, _e=None) -> None:
        self._hovered = True;  self._update()
        if self._command:
            self._command()

    def set_active(self, active: bool) -> None:
        self._active = active; self._update()

    def config_text(self, text: str) -> None:
        self._lbl.config(text=text)


# ── Header gradient bleu→noir ─────────────────────────────────────────────────

class _GradientHeader(tk.Canvas):
    def __init__(self, master, height: int = HEADER_H, **kw) -> None:
        super().__init__(master, height=height, bg=BG,
                         highlightthickness=0, **kw)
        self._h = height
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _e=None) -> None:
        self.delete("all")
        w = self.winfo_width() or 1200
        h = self._h
        steps = 60
        for i in range(steps):
            t  = i / steps
            r  = int(0x16 + (0x0d - 0x16) * t)
            g  = int(0x71 + (0x0d - 0x71) * t)
            b  = int(0xe3 + (0x0d - 0xe3) * t)
            x0 = int(w * i / steps)
            x1 = int(w * (i + 1) / steps) + 1
            self.create_rectangle(x0, 0, x1, h,
                                  fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        self.create_text(24, h // 2, text="詰", fill="#ffffff",
                         font=kanji_font(22), anchor="w")
        self.create_text(60, h // 2, text="Tsumi", fill="#ffffff",
                         font=ui_font(16, "bold"), anchor="w")


# ── Pages placeholder ─────────────────────────────────────────────────────────

class _PlaceholderPage(tk.Frame):
    def __init__(self, master, title: str, **kw) -> None:
        super().__init__(master, bg=BG, **kw)
        tk.Label(self, text=title, bg=BG, fg=FG_DIM,
                 font=ui_font(18)).place(relx=0.5, rely=0.5, anchor="center")


class _SettingsPage(tk.Frame):
    def __init__(self, master, **kw) -> None:
        super().__init__(master, bg=BG, **kw)
        tk.Label(self, text="Paramètres", bg=BG, fg=FG,
                 font=ui_font(14, "bold")).pack(anchor="w", padx=24, pady=(24, 16))
        self._row("Thème", "Sombre")
        self._row("Téléchargements", str(Path.home() / "Tsumi" / "Downloads"))
        self._row("Version", "1.0.0-dev")

    def _row(self, label: str, value: str) -> None:
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=label, bg=BG2, fg=FG,
                 font=ui_font(10), width=28, anchor="w").pack(side="left", padx=12, pady=10)
        tk.Label(row, text=value, bg=BG2, fg=FG_DIM,
                 font=ui_font(10), anchor="w").pack(side="left")


# ── Application principale ────────────────────────────────────────────────────

class TsumiApp:
    """Fenêtre racine Tsumi : header + sidebar + zone de contenu."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._root.title("Tsumi")
        self._root.configure(bg=BG)
        self._root.minsize(900, 600)
        self._root.geometry("1200x750")

        # Initialisation du Downloader global (gère ~/Tsumi/Downloads/<Source>/<Titre>/)
        from downloader.Downloader import Downloader
        self._downloader = Downloader()

        try:
            from assets.icon import get_icon
            self._root.iconphoto(True, get_icon(self._root))
        except Exception:
            pass

        self._pages:    dict[str, tk.Widget] = {}
        self._nav_btns: dict[str, TsumiButton] = {}
        self._current_page = ""

        self._build_layout()
        self._build_sidebar()
        self._build_content()
        self._show_page("library")
        self._check_update()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self._header = _GradientHeader(self._root)
        self._header.pack(fill="x", side="top")
        self._main = tk.Frame(self._root, bg=BG)
        self._main.pack(fill="both", expand=True)

    def _build_sidebar(self) -> None:
        self._sidebar = tk.Frame(self._main, bg=BG2, width=SIDEBAR_W)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        tk.Frame(self._main, bg="#222222", width=1).pack(side="left", fill="y")

        nav = [
            ("library",   "Bibliothèque",   draw_icon_book),
            ("discover",  "Découvrir",       draw_icon_search),
            ("downloads", "Téléchargements", draw_icon_download),
            ("settings",  "Paramètres",      draw_icon_settings),
        ]
        tk.Frame(self._sidebar, bg=BG2, height=12).pack()

        for pid, label, icon_fn in nav:
            btn = TsumiButton(
                self._sidebar, text=label, icon_fn=icon_fn,
                command=lambda p=pid: self._show_page(p),
                width=SIDEBAR_W - 16, height=42,
                bg=BG2, bg_hover=BG3,
            )
            btn.pack(padx=8, pady=3)
            self._nav_btns[pid] = btn

        tk.Frame(self._sidebar, bg=BG2).pack(fill="both", expand=True)
        TsumiButton(
            self._sidebar, text="À propos", icon_fn=draw_icon_info,
            command=self._show_about,
            width=SIDEBAR_W - 16, height=38, bg=BG2,
        ).pack(padx=8, pady=(0, 12))

    def _build_content(self) -> None:
        from panel.Panel import Panel
        from panel.Discover import DiscoverPanel
        from panel.Downloads import DownloadsPanel

        self._content = tk.Frame(self._main, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

        self._pages["library"] = Panel(
            self._content,
            on_open_chapter=self._on_open_chapter,
            on_goto_discover=lambda: self._show_page("discover"),
        )
        self._pages["discover"] = DiscoverPanel(
            self._content,
            downloader=self._downloader,
            on_read_online=self._on_read_online,
            on_read_cbz=self.open_cbz_file,
            on_library_changed=lambda: self._pages["library"].refresh(),
        )
        self._pages["downloads"] = DownloadsPanel(
            self._content,
            downloader=self._downloader,
            on_open_cbz=self.open_cbz_file,
        )
        self._pages["settings"] = _SettingsPage(self._content)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_page(self, page_id: str) -> None:
        if self._current_page == page_id:
            return
        for w in self._pages.values():
            w.pack_forget()

        # Rafraîchit automatiquement la page si elle expose refresh()
        target_page = self._pages[page_id]
        if hasattr(target_page, "refresh"):
            target_page.refresh()

        target_page.pack(fill="both", expand=True)
        self._current_page = page_id
        for pid, btn in self._nav_btns.items():
            btn.set_active(pid == page_id)

    # ── Lecture CBZ / Online ──────────────────────────────────────────────────

    def open_cbz_file(self, path: str) -> None:
        from reader.Reader import ReaderWindow
        ReaderWindow(self._root).open_cbz(path)

    def _on_read_online(self, pages: list[str], source: str, manga: str, chapter: str) -> None:
        """Ouvre le lecteur Tsumi en streaming direct d'images."""
        from reader.Reader import ReaderWindow
        win = ReaderWindow(self._root)
        win.open_online(pages, source=source, manga=manga, chapter=chapter)

    def _on_open_chapter(self, entry: dict) -> None:
        """Ouverture depuis la bibliothèque : ouvre la fiche dans Découvrir ou le CBZ direct."""
        cbz = entry.get("cbz_path", "")
        if cbz and Path(cbz).exists():
            self.open_cbz_file(cbz)
            return

        # Si l'entrée a une URL de manga, on l'ouvre dans la vue Découvrir
        if "discover" in self._pages and hasattr(self._pages["discover"], "_open_manga_detail"):
            self._show_page("discover")
            self._pages["discover"]._open_manga_detail(entry)

    def open_file_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Ouvrir un CBZ",
            filetypes=[("Archives manga", "*.cbz *.cbr *.zip"),
                       ("Tous les fichiers", "*.*")],
        )
        if path:
            self.open_cbz_file(path)

    # ── About ─────────────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("À propos")
        win.configure(bg=BG)
        win.geometry("360x280")
        win.resizable(False, False)
        tk.Label(win, text="詰", bg=BG, fg=ACCENT,
                 font=kanji_font(48)).pack(pady=(24, 0))
        tk.Label(win, text="Tsumi", bg=BG, fg=FG,
                 font=ui_font(18, "bold")).pack()
        tk.Label(win, text="v1.0.0-dev", bg=BG, fg=FG_DIM,
                 font=ui_font(10)).pack()
        tk.Label(win,
                 text="Lecteur manga / webtoon\nléger, CPU-only.",
                 bg=BG, fg=FG_DIM, font=ui_font(10),
                 justify="center").pack(pady=10)
        tk.Label(win, text="GNU GPL 3.0 — Badley08", bg=BG, fg=FG_DIM,
                 font=ui_font(9)).pack()
        TsumiButton(win, text="Fermer", icon_fn=draw_icon_close,
                    command=win.destroy, width=120, height=36,
                    bg=BG2).pack(pady=16)

    # ── Update check ──────────────────────────────────────────────────────────

    def _check_update(self) -> None:
        from updates.AppUpdate import check_update_async
        check_update_async(
            lambda v, u: self._root.after(0, lambda: self._notify_update(v, u))
        )

    def _notify_update(self, version: str, url: str) -> None:
        if messagebox.askyesno("Mise à jour disponible",
                               f"Tsumi {version} est disponible.\n"
                               "Ouvrir la page de téléchargement ?"):
            import webbrowser
            webbrowser.open(url)
