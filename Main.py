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
Main.py — Point d'entrée de Tsumi.

Usage::
    python Main.py                  # Lance l'UI principale
    python Main.py /path/to/ch.cbz  # Ouvre directement un CBZ
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from handlers.Logs import setup_logging
from menu.Menu import TsumiApp


def main() -> None:
    setup_logging()

    root = tk.Tk()
    app = TsumiApp(root)

    # Ouverture directe d'un CBZ depuis le gestionnaire de fichiers
    if len(sys.argv) > 1:
        cbz_path = Path(sys.argv[1])
        if cbz_path.exists() and cbz_path.suffix.lower() in (".cbz", ".cbr", ".zip"):
            root.after(100, lambda: app.open_cbz_file(str(cbz_path)))

    root.mainloop()


if __name__ == "__main__":
    main()
