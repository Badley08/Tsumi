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
panel/Discover.py — Onglet Découvrir / Sources inspiré de Tachiyomi.

Permet de :
- Explorer et chercher parmi les sources installées (Anime-Sama, Mangas Origines, Rimu Scan, Scantrad IO)
- Consulter les mangas trouvés sous forme de cartes / grille
- Ouvrir une fiche manga détaillée (Titre, Cover, Source, Chapitres)
- Ajouter / retirer de la bibliothèque
- Lire directement en streaming dans Tsumi Reader
- Télécharger en fichier CBZ dans Tsumi/Downloads/<Source>/<TitreOeuvre>/chap<n>.cbz
"""

from __future__ import annotations

import io
import logging
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

import requests
from PIL import Image, ImageTk

from assets.icons import (
    draw_icon_arrow_left,
    draw_icon_book,
    draw_icon_download,
    draw_icon_play,
    draw_icon_search,
    draw_icon_star,
)
from assets.theme import (
    ACCENT, ACCENT_H, BG, BG2, BG3, FG, FG_DIM,
    ui_font,
)
from downloader.Downloader import Downloader
from sources import get_all

logger = logging.getLogger(__name__)

# Suggestions populaires initiales façon Tachiyomi pour démarrer en un clic
POPULAR_QUERIES = [
    "Solo Leveling",
    "The Tutorial is Too Hard",
    "Omniscient Reader",
    "Nano Machine",
    "One Piece",
    "Jujutsu Kaisen",
]


class DiscoverPanel(tk.Frame):
    """Panneau de découverte et recherche multi-sources style Tachiyomi."""

    def __init__(
        self,
        master: tk.Misc,
        downloader: Downloader,
        on_read_online: Callable[[list[str], str, str, str], None],
        on_read_cbz: Callable[[str], None],
        on_library_changed: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=BG, **kwargs)

        self._downloader = downloader
        self._on_read_online = on_read_online
        self._on_read_cbz = on_read_cbz
        self._on_library_changed = on_library_changed

        self._sources = get_all()
        self._active_source_name = "Toutes les sources"
        self._results: list[dict] = []
        self._cover_cache: dict[str, ImageTk.PhotoImage] = {}

        # Vue active : "search" ou "detail"
        self._active_view = "search"
        self._current_manga: Optional[dict] = None
        self._chapters: list[dict] = []

        self._build_ui()
        # Lance une recherche de découverte par défaut
        self.after(200, lambda: self._perform_search("Solo Leveling"))

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Container principal
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # 1. Vue Recherche / Résultats
        self._search_frame = tk.Frame(self, bg=BG)
        self._search_frame.grid(row=0, column=0, sticky="nsew")
        self._build_search_view()

        # 2. Vue Détails Manga (masquée par défaut)
        self._detail_frame = tk.Frame(self, bg=BG)
        self._detail_frame.grid(row=0, column=0, sticky="nsew")
        self._build_detail_view()
        self._detail_frame.grid_remove()

    def _build_search_view(self) -> None:
        sf = self._search_frame
        sf.columnconfigure(0, weight=1)
        sf.rowconfigure(2, weight=1)

        # ── Barre supérieure (Recherche + Source selector) ────────────────────
        top_bar = tk.Frame(sf, bg=BG2, height=56)
        top_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        top_bar.pack_propagate(False)

        # Champ de texte de recherche
        search_box = tk.Frame(top_bar, bg=BG3, padx=10, pady=6)
        search_box.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=8)

        self._search_var = tk.StringVar(value="")
        self._search_entry = tk.Entry(
            search_box,
            textvariable=self._search_var,
            bg=BG3,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=ui_font(11),
        )
        self._search_entry.pack(side="left", fill="x", expand=True)
        self._search_entry.bind("<Return>", lambda e: self._on_search_click())

        # Bouton Rechercher
        search_btn = tk.Button(
            top_bar,
            text="Rechercher",
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_H,
            activeforeground="#ffffff",
            relief="flat",
            font=ui_font(10, "bold"),
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._on_search_click,
        )
        search_btn.pack(side="left", padx=(0, 10), pady=8)

        # Sélecteur de source
        src_label = tk.Label(top_bar, text="Source :", bg=BG2, fg=FG_DIM, font=ui_font(9))
        src_label.pack(side="left", padx=(6, 4))

        self._source_options = ["Toutes les sources"] + sorted(list(self._sources.keys()))
        self._source_var = tk.StringVar(value="Toutes les sources")

        src_menu = tk.OptionMenu(
            top_bar,
            self._source_var,
            *self._source_options,
            command=self._on_source_selected,
        )
        src_menu.config(
            bg=BG3, fg=FG, activebackground=BG3, activeforeground=ACCENT,
            relief="flat", font=ui_font(9), highlightthickness=0,
        )
        src_menu["menu"].config(bg=BG2, fg=FG, activebackground=ACCENT, activeforeground="#ffffff")
        src_menu.pack(side="left", padx=(0, 12), pady=8)

        # ── Barre de suggestions rapides ─────────────────────────────────────
        pills_frame = tk.Frame(sf, bg=BG)
        pills_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))

        sug_lbl = tk.Label(pills_frame, text="Populaires :", bg=BG, fg=FG_DIM, font=ui_font(9))
        sug_lbl.pack(side="left", padx=(0, 6))

        for q in POPULAR_QUERIES:
            b = tk.Button(
                pills_frame,
                text=q,
                bg=BG2,
                fg=FG,
                activebackground=BG3,
                activeforeground=ACCENT,
                relief="flat",
                font=ui_font(9),
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda term=q: self._quick_search(term),
            )
            b.pack(side="left", padx=4)

        # ── Zone Résultats avec Canvas défilable ──────────────────────────────
        results_container = tk.Frame(sf, bg=BG)
        results_container.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))
        results_container.columnconfigure(0, weight=1)
        results_container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(results_container, bg=BG, highlightthickness=0)
        self._vscroll = tk.Scrollbar(results_container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vscroll.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vscroll.grid(row=0, column=1, sticky="ns")

        self._grid_inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._grid_inner, anchor="nw")

        self._grid_inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width),
        )
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Message statut (chargement / vide)
        self._status_lbl = tk.Label(
            self._grid_inner,
            text="Recherchez un manga ou sélectionnez une source ci-dessus.",
            bg=BG,
            fg=FG_DIM,
            font=ui_font(12),
            pady=40,
        )
        self._status_lbl.pack()

    # ── Détail View (style fiche manga Tachiyomi) ─────────────────────────────

    def _build_detail_view(self) -> None:
        df = self._detail_frame
        df.columnconfigure(0, weight=1)
        df.rowconfigure(1, weight=1)

        # Barre supérieure : Bouton retour
        top_bar = tk.Frame(df, bg=BG2, height=48)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.pack_propagate(False)

        back_btn = tk.Button(
            top_bar,
            text="← Retour aux résultats",
            bg=BG2,
            fg=FG,
            activebackground=BG3,
            activeforeground=ACCENT,
            relief="flat",
            font=ui_font(10),
            padx=12,
            cursor="hand2",
            command=self._back_to_search,
        )
        back_btn.pack(side="left", padx=10, pady=8)

        # Conteneur défilable pour la fiche
        detail_container = tk.Frame(df, bg=BG)
        detail_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        detail_container.columnconfigure(0, weight=1)
        detail_container.rowconfigure(0, weight=1)

        self._detail_canvas = tk.Canvas(detail_container, bg=BG, highlightthickness=0)
        self._detail_vscroll = tk.Scrollbar(detail_container, orient="vertical", command=self._detail_canvas.yview)
        self._detail_canvas.configure(yscrollcommand=self._detail_vscroll.set)

        self._detail_canvas.grid(row=0, column=0, sticky="nsew")
        self._detail_vscroll.grid(row=0, column=1, sticky="ns")

        self._detail_inner = tk.Frame(self._detail_canvas, bg=BG)
        self._detail_window = self._detail_canvas.create_window((0, 0), window=self._detail_inner, anchor="nw")

        self._detail_inner.bind(
            "<Configure>",
            lambda e: self._detail_canvas.configure(scrollregion=self._detail_canvas.bbox("all")),
        )
        self._detail_canvas.bind(
            "<Configure>",
            lambda e: self._detail_canvas.itemconfig(self._detail_window, width=e.width),
        )

        # Section Entête Manga (Cover + Infos + Actions)
        self._header_frame = tk.Frame(self._detail_inner, bg=BG2, padx=16, pady=16)
        self._header_frame.pack(fill="x", padx=10, pady=10)

        self._cover_lbl = tk.Label(self._header_frame, bg=BG3, width=140, height=200)
        self._cover_lbl.pack(side="left", padx=(0, 20))

        info_box = tk.Frame(self._header_frame, bg=BG2)
        info_box.pack(side="left", fill="both", expand=True)

        self._manga_title_lbl = tk.Label(
            info_box, text="", bg=BG2, fg="#ffffff",
            font=ui_font(16, "bold"), anchor="w", justify="left", wraplength=500,
        )
        self._manga_title_lbl.pack(anchor="w", pady=(0, 6))

        self._manga_source_lbl = tk.Label(
            info_box, text="", bg=BG2, fg=ACCENT, font=ui_font(10, "bold"), anchor="w",
        )
        self._manga_source_lbl.pack(anchor="w", pady=(0, 14))

        # Boutons d'action : Ajouter à la bibliothèque
        actions_bar = tk.Frame(info_box, bg=BG2)
        actions_bar.pack(anchor="w", pady=(0, 10))

        self._fav_btn = tk.Button(
            actions_bar,
            text="+ Ajouter à la bibliothèque",
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_H,
            activeforeground="#ffffff",
            relief="flat",
            font=ui_font(10, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._toggle_favorite,
        )
        self._fav_btn.pack(side="left", padx=(0, 10))

        # Section Liste des Chapitres
        chap_header = tk.Frame(self._detail_inner, bg=BG)
        chap_header.pack(fill="x", padx=10, pady=(16, 6))

        self._chap_count_lbl = tk.Label(
            chap_header, text="Chapitres", bg=BG, fg=FG,
            font=ui_font(13, "bold"),
        )
        self._chap_count_lbl.pack(side="left")

        self._chapters_list_frame = tk.Frame(self._detail_inner, bg=BG)
        self._chapters_list_frame.pack(fill="x", padx=10, pady=4)

    # ── Recherche & Fetch ─────────────────────────────────────────────────────

    def _quick_search(self, term: str) -> None:
        self._search_var.set(term)
        self._perform_search(term)

    def _on_search_click(self) -> None:
        query = self._search_var.get().strip()
        if query:
            self._perform_search(query)

    def _on_source_selected(self, val: str) -> None:
        self._active_source_name = val
        q = self._search_var.get().strip()
        if q:
            self._perform_search(q)

    def _perform_search(self, query: str) -> None:
        """Lance la recherche en thread background pour ne jamais bloquer l'UI."""
        self._clear_results()
        self._set_status(f"Recherche de « {query} » en cours...")

        def _worker():
            results = []
            selected_source = self._source_var.get()

            target_sources = {}
            if selected_source == "Toutes les sources":
                target_sources = self._sources
            elif selected_source in self._sources:
                target_sources = {selected_source: self._sources[selected_source]}

            for name, src in target_sources.items():
                try:
                    logger.info("Search in %s for '%s'", name, query)
                    found = src.search(query)
                    for item in found:
                        item["source"] = name
                        results.append(item)
                except Exception as exc:
                    logger.warning("Erreur search sur %s: %s", name, exc)

            self.after(0, lambda: self._display_results(results, query))

        threading.Thread(target=_worker, daemon=True, name="tsumi-search").start()

    def _clear_results(self) -> None:
        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._results.clear()

    def _set_status(self, text: str) -> None:
        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._status_lbl = tk.Label(
            self._grid_inner, text=text, bg=BG, fg=FG_DIM,
            font=ui_font(12), pady=40,
        )
        self._status_lbl.pack()

    def _display_results(self, results: list[dict], query: str) -> None:
        self._clear_results()
        self._results = results

        if not results:
            self._set_status(f"Aucun manga trouvé pour « {query} ».\nEssayez un autre mot-clé ou changez de source.")
            return

        # Construction de la grille de cartes (Cartes manga)
        cols = 4
        grid_frame = tk.Frame(self._grid_inner, bg=BG)
        grid_frame.pack(fill="both", expand=True, padx=4, pady=4)

        for idx, item in enumerate(results):
            r = idx // cols
            c = idx % cols
            card = self._create_manga_card(grid_frame, item)
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            grid_frame.columnconfigure(c, weight=1)

    def _create_manga_card(self, parent: tk.Widget, item: dict) -> tk.Widget:
        """Carte manga cliquable avec Cover, Titre, et Badge Source."""
        card = tk.Frame(parent, bg=BG2, cursor="hand2", padx=6, pady=6)

        # Image de couverture (taille 130x180)
        cover_w, cover_h = 130, 180
        img_label = tk.Label(card, bg=BG3, width=cover_w, height=cover_h)
        img_label.pack(fill="x")

        # Chargement asynchrone de la cover
        cover_url = item.get("cover", "")
        if cover_url:
            self._load_async_cover(cover_url, img_label, cover_w, cover_h)

        # Titre (2 lignes max)
        title = item.get("title", "Sans titre")
        title_lbl = tk.Label(
            card,
            text=title,
            bg=BG2,
            fg=FG,
            font=ui_font(9, "bold"),
            anchor="w",
            justify="left",
            wraplength=125,
            height=2,
        )
        title_lbl.pack(fill="x", pady=(4, 2))

        # Badge Source
        source_name = item.get("source", "")
        badge = tk.Label(
            card,
            text=source_name,
            bg="#162942",
            fg=ACCENT_H,
            font=ui_font(8),
            anchor="w",
            padx=4,
            pady=1,
        )
        badge.pack(anchor="w")

        # Clic pour ouvrir la vue détails
        def _on_click(_e=None):
            self._open_manga_detail(item)

        for w in (card, img_label, title_lbl, badge):
            w.bind("<Button-1>", _on_click)
            w.bind("<Enter>", lambda e, c=card: c.configure(bg=BG3))
            w.bind("<Leave>", lambda e, c=card: c.configure(bg=BG2))

        return card

    def _load_async_cover(self, url: str, label: tk.Label, w: int, h: int) -> None:
        """Télécharge la vignette en tâche de fond et met à jour le Label."""
        if url in self._cover_cache:
            label.configure(image=self._cover_cache[url], width=w, height=h)
            return

        def _bg():
            try:
                r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    pil_img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    pil_img = pil_img.resize((w, h), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self._cover_cache[url] = tk_img
                    self.after(0, lambda: label.configure(image=tk_img, width=w, height=h))
            except Exception as exc:
                logger.debug("Failed to load cover %s: %s", url, exc)

        threading.Thread(target=_bg, daemon=True).start()

    # ── Fiche Détails Manga ───────────────────────────────────────────────────

    def _open_manga_detail(self, manga_item: dict) -> None:
        """Affiche la vue détaillée avec la liste des chapitres."""
        self._current_manga = manga_item
        self._search_frame.grid_remove()
        self._detail_frame.grid()
        self._active_view = "detail"

        # Titre et source
        self._manga_title_lbl.config(text=manga_item.get("title", ""))
        self._manga_source_lbl.config(text=f"Source : {manga_item.get('source', '')}")

        # Cover
        cover_url = manga_item.get("cover", "")
        if cover_url:
            self._load_async_cover(cover_url, self._cover_lbl, 140, 200)

        # Vérifie statut favoris
        self._update_favorite_button()

        # Vide et charge les chapitres
        for w in self._chapters_list_frame.winfo_children():
            w.destroy()
        loading_lbl = tk.Label(
            self._chapters_list_frame,
            text="Chargement des chapitres depuis la source...",
            bg=BG, fg=FG_DIM, font=ui_font(11), pady=20,
        )
        loading_lbl.pack()

        # Fetch des chapitres en thread
        def _fetch_chapters():
            source_name = manga_item.get("source")
            source_inst = self._sources.get(source_name)
            chapters = []
            if source_inst:
                try:
                    chapters = source_inst.get_chapters(manga_item.get("url", ""))
                except Exception as exc:
                    logger.error("Failed get_chapters: %s", exc)

            self.after(0, lambda: self._display_chapters(chapters))

        threading.Thread(target=_fetch_chapters, daemon=True, name="tsumi-chaps").start()

    def _back_to_search(self) -> None:
        self._detail_frame.grid_remove()
        self._search_frame.grid()
        self._active_view = "search"

    def _display_chapters(self, chapters: list[dict]) -> None:
        self._chapters = chapters
        for w in self._chapters_list_frame.winfo_children():
            w.destroy()

        if not chapters:
            tk.Label(
                self._chapters_list_frame,
                text="Aucun chapitre trouvé pour cette œuvre.",
                bg=BG, fg=FG_DIM, font=ui_font(11), pady=20,
            ).pack()
            self._chap_count_lbl.config(text="Chapitres (0)")
            return

        self._chap_count_lbl.config(text=f"Chapitres ({len(chapters)})")

        source_name = self._current_manga.get("source", "")
        manga_title = self._current_manga.get("title", "")

        for chap in reversed(chapters):  # Afficher les plus récents en premier comme Tachiyomi
            row = self._create_chapter_row(self._chapters_list_frame, chap, source_name, manga_title)
            row.pack(fill="x", pady=2)

    def _create_chapter_row(
        self, parent: tk.Widget, chap: dict, source_name: str, manga_title: str
    ) -> tk.Widget:
        row = tk.Frame(parent, bg=BG2, padx=10, pady=6)

        # Titre du chapitre
        title_text = chap.get("title") or f"Chapitre {chap.get('number', '')}"
        lbl = tk.Label(
            row, text=title_text, bg=BG2, fg=FG,
            font=ui_font(10), anchor="w",
        )
        lbl.pack(side="left", fill="x", expand=True)

        # Vérifie si le CBZ existe déjà localement
        num = chap.get("number", 0)
        cbz_path = self._downloader.get_chapter_path(source_name, manga_title, num)
        is_downloaded = cbz_path.exists()

        if is_downloaded:
            badge = tk.Label(
                row, text="TÉLÉCHARGÉ", bg="#153d20", fg="#4cd964",
                font=ui_font(8, "bold"), padx=6, pady=2,
            )
            badge.pack(side="left", padx=8)

        # Bouton Lire
        read_btn = tk.Button(
            row,
            text="Lire",
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_H,
            activeforeground="#ffffff",
            relief="flat",
            font=ui_font(9, "bold"),
            padx=12,
            pady=3,
            cursor="hand2",
            command=lambda c=chap, cp=cbz_path: self._on_read_chapter(c, cp),
        )
        read_btn.pack(side="right", padx=4)

        # Bouton Télécharger (CBZ)
        if not is_downloaded:
            dl_btn = tk.Button(
                row,
                text="Télécharger",
                bg=BG3,
                fg=FG,
                activebackground=BG2,
                activeforeground=ACCENT,
                relief="flat",
                font=ui_font(9),
                padx=10,
                pady=3,
                cursor="hand2",
                command=lambda c=chap, b=row: self._start_download(c, b),
            )
            dl_btn.pack(side="right", padx=4)

        return row

    def _on_read_chapter(self, chap: dict, cbz_path: Path) -> None:
        """Lance la lecture : en local si CBZ présent, sinon en streaming online."""
        if cbz_path.exists():
            self._on_read_cbz(str(cbz_path))
            return

        # Lecture en ligne : fetch des images du chapitre
        source_name = self._current_manga.get("source", "")
        manga_title = self._current_manga.get("title", "")
        source_inst = self._sources.get(source_name)

        if not source_inst:
            return

        def _fetch_pages():
            try:
                pages = source_inst.get_pages(chap.get("url", ""))
                chap_num = str(chap.get("number", ""))
                self.after(
                    0,
                    lambda: self._on_read_online(pages, source_name, manga_title, chap_num),
                )
            except Exception as exc:
                logger.error("Failed get_pages: %s", exc)

        threading.Thread(target=_fetch_pages, daemon=True).start()

    def _start_download(self, chap: dict, row_widget: tk.Widget) -> None:
        """Lance le téléchargement CBZ vers ~/Tsumi/Downloads/<Source>/<Titre>/chap<n>.cbz."""
        source_name = self._current_manga.get("source", "")
        manga_title = self._current_manga.get("title", "")
        source_inst = self._sources.get(source_name)
        if not source_inst:
            return

        # Notification visuelle dans le bouton
        for child in row_widget.winfo_children():
            if isinstance(child, tk.Button) and child.cget("text") == "Télécharger":
                child.config(text="Téléchargement...", state="disabled", bg=BG3, fg=FG_DIM)

        future = self._downloader.download_chapter(source_inst, manga_title, chap)

        def _wait_done():
            try:
                cbz_path = future.result()
                self.after(0, lambda: self._on_download_complete(row_widget))
            except Exception as exc:
                logger.error("Download failed: %s", exc)

        threading.Thread(target=_wait_done, daemon=True).start()

    def _on_download_complete(self, row_widget: tk.Widget) -> None:
        for child in row_widget.winfo_children():
            if isinstance(child, tk.Button) and child.cget("text") == "Téléchargement...":
                child.destroy()
        badge = tk.Label(
            row_widget, text="TÉLÉCHARGÉ", bg="#153d20", fg="#4cd964",
            font=ui_font(8, "bold"), padx=6, pady=2,
        )
        badge.pack(side="left", padx=8)

    # ── Gestion Bibliothèque (Ajout / Retrait) ────────────────────────────────

    def _is_in_library(self) -> bool:
        from panel.Panel import _load_library
        lib = _load_library()
        key = (self._current_manga.get("title", ""), self._current_manga.get("source", ""))
        return any((item.get("title"), item.get("source")) == key for item in lib)

    def _update_favorite_button(self) -> None:
        if self._is_in_library():
            self._fav_btn.config(
                text="✓ Dans la bibliothèque",
                bg="#153d20",
                fg="#4cd964",
            )
        else:
            self._fav_btn.config(
                text="+ Ajouter à la bibliothèque",
                bg=ACCENT,
                fg="#ffffff",
            )

    def _toggle_favorite(self) -> None:
        from panel.Panel import _load_library, _save_library
        lib = _load_library()
        key = (self._current_manga.get("title", ""), self._current_manga.get("source", ""))

        exists_idx = None
        for i, item in enumerate(lib):
            if (item.get("title"), item.get("source")) == key:
                exists_idx = i
                break

        if exists_idx is not None:
            # Retirer de la bibliothèque
            lib.pop(exists_idx)
            _save_library(lib)
        else:
            # Ajouter à la bibliothèque
            entry = {
                "title": self._current_manga.get("title", ""),
                "type": self._current_manga.get("type", "Manga"),
                "cover": self._current_manga.get("cover", ""),
                "source": self._current_manga.get("source", ""),
                "url": self._current_manga.get("url", ""),
                "chapter": "1",
                "page": 0,
            }
            lib.append(entry)
            _save_library(lib)

        self._update_favorite_button()
        if self._on_library_changed:
            self._on_library_changed()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self._active_view == "search":
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            self._detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
