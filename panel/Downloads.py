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
panel/Downloads.py — Gestionnaire et explorateur des chapitres CBZ téléchargés.

Dossier surveillé : ~/Tsumi/Downloads/<Source>/<TitreOeuvre>/chap<n>.cbz
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable

from assets.theme import (
    ACCENT, ACCENT_H, BG, BG2, BG3, FG, FG_DIM,
    ui_font,
)
from downloader.Downloader import Downloader

logger = logging.getLogger(__name__)


class DownloadsPanel(tk.Frame):
    """Panneau listant les chapitres CBZ stockés hors-ligne dans ~/Tsumi/Downloads."""

    def __init__(
        self,
        master: tk.Misc,
        downloader: Downloader,
        on_open_cbz: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=BG, **kwargs)

        self._downloader = downloader
        self._on_open_cbz = on_open_cbz

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        header = tk.Frame(self, bg=BG2, height=50, padx=16)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)

        title = tk.Label(
            header, text="Téléchargements Hors-Ligne", bg=BG2, fg="#ffffff",
            font=ui_font(12, "bold"),
        )
        title.pack(side="left")

        ref_btn = tk.Button(
            header,
            text="Actualiser",
            bg=BG3,
            fg=FG,
            activebackground=BG,
            activeforeground=ACCENT,
            relief="flat",
            font=ui_font(9),
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.refresh,
        )
        ref_btn.pack(side="right", padx=6)

        open_folder_btn = tk.Button(
            header,
            text="Ouvrir le dossier",
            bg=BG3,
            fg=FG,
            activebackground=BG,
            activeforeground=ACCENT,
            relief="flat",
            font=ui_font(9),
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._open_system_folder,
        )
        open_folder_btn.pack(side="right", padx=6)

        # Scrollable list
        container = tk.Frame(self, bg=BG)
        container.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        self._vsb = tk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")

        self._list_inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_win = self._canvas.create_window((0, 0), window=self._list_inner, anchor="nw")

        self._list_inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_win, width=e.width),
        )

    def refresh(self) -> None:
        """Parcourt ~/Tsumi/Downloads/<Source>/<TitreOeuvre>/chap<n>.cbz."""
        for w in self._list_inner.winfo_children():
            w.destroy()

        root_dir = self._downloader.get_download_dir()
        if not root_dir.exists():
            root_dir.mkdir(parents=True, exist_ok=True)

        # Recherche de tous les .cbz
        cbz_files = sorted(root_dir.glob("*/*/*.cbz"))

        if not cbz_files:
            empty_lbl = tk.Label(
                self._list_inner,
                text=f"Aucun téléchargement trouvé dans :\n{root_dir}\n\nTéléchargez des chapitres depuis l'onglet Découvrir !",
                bg=BG,
                fg=FG_DIM,
                font=ui_font(11),
                justify="center",
                pady=40,
            )
            empty_lbl.pack()
            return

        # Regrouper par Source / Titre
        grouped: dict[tuple[str, str], list[Path]] = {}
        for path in cbz_files:
            source = path.parent.parent.name
            manga = path.parent.name
            grouped.setdefault((source, manga), []).append(path)

        for (source, manga), files in grouped.items():
            card = tk.Frame(self._list_inner, bg=BG2, padx=12, pady=10)
            card.pack(fill="x", pady=6)

            title_row = tk.Frame(card, bg=BG2)
            title_row.pack(fill="x", pady=(0, 8))

            m_lbl = tk.Label(
                title_row, text=manga.replace("-", " "), bg=BG2, fg="#ffffff",
                font=ui_font(11, "bold"),
            )
            m_lbl.pack(side="left")

            s_badge = tk.Label(
                title_row, text=source, bg="#162942", fg=ACCENT_H,
                font=ui_font(8), padx=6, pady=1,
            )
            s_badge.pack(side="left", padx=8)

            c_count = tk.Label(
                title_row, text=f"{len(files)} chapitres", bg=BG2, fg=FG_DIM,
                font=ui_font(9),
            )
            c_count.pack(side="right")

            # Liste des chapitres
            for f in files:
                frow = tk.Frame(card, bg=BG3, padx=8, pady=4)
                frow.pack(fill="x", pady=2)

                size_mb = f.stat().st_size / (1024 * 1024)
                name_lbl = tk.Label(
                    frow, text=f"{f.stem}.cbz ({size_mb:.1f} Mo)",
                    bg=BG3, fg=FG, font=ui_font(9), anchor="w",
                )
                name_lbl.pack(side="left")

                del_btn = tk.Button(
                    frow, text="Supprimer", bg=BG3, fg="#e05555",
                    activebackground=BG2, activeforeground="#ff6666",
                    relief="flat", font=ui_font(8), padx=6, cursor="hand2",
                    command=lambda p=f: self._delete_cbz(p),
                )
                del_btn.pack(side="right", padx=2)

                read_btn = tk.Button(
                    frow, text="Lire", bg=ACCENT, fg="#ffffff",
                    activebackground=ACCENT_H, activeforeground="#ffffff",
                    relief="flat", font=ui_font(8, "bold"), padx=10, cursor="hand2",
                    command=lambda p=f: self._on_open_cbz(str(p)),
                )
                read_btn.pack(side="right", padx=6)

    def _delete_cbz(self, path: Path) -> None:
        if messagebox.askyesno("Confirmation", f"Supprimer le fichier {path.name} ?"):
            try:
                path.unlink()
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Erreur", f"Impossible de supprimer : {exc}")

    def _open_system_folder(self) -> None:
        root_dir = self._downloader.get_download_dir()
        root_dir.mkdir(parents=True, exist_ok=True)
        import os
        import subprocess
        import sys
        if sys.platform == "win32":
            os.startfile(str(root_dir))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(root_dir)])
        else:
            subprocess.Popen(["xdg-open", str(root_dir)])
