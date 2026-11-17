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
updates/AppUpdate.py — Vérification des mises à jour GitHub.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

CURRENT_VERSION = "1.0.0"
GITHUB_API_URL  = "https://api.github.com/repos/Badley08/Tsumi/releases/latest"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse 'v1.2.3' ou '1.2.3' en tuple (1, 2, 3)."""
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def check_update_async(
    on_update: Callable[[str, str], None],
    on_no_update: Optional[Callable[[], None]] = None,
) -> None:
    """Vérifie les updates en arrière-plan.

    Parameters
    ----------
    on_update:
        Appelé avec (latest_version, download_url) si une update est dispo.
    on_no_update:
        Appelé si on est à jour (optionnel).
    """
    def _check():
        try:
            resp = requests.get(
                GITHUB_API_URL,
                timeout=10,
                headers={"Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            data = resp.json()

            tag     = data.get("tag_name", "")
            latest  = _parse_version(tag)
            current = _parse_version(CURRENT_VERSION)

            if latest > current:
                # Cherche l'AppImage dans les assets
                url = data.get("html_url", "")
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".AppImage"):
                        url = asset["browser_download_url"]
                        break
                on_update(tag, url)
            else:
                if on_no_update:
                    on_no_update()

        except Exception as exc:
            logger.debug("Vérification update échouée: %s", exc)

    threading.Thread(target=_check, daemon=True, name="tsumi-update-check").start()
