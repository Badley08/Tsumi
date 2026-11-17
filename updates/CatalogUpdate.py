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
updates/CatalogUpdate.py — Rechargement dynamique des sources.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SOURCES_DIR = Path(__file__).parent.parent / "sources"


def reload_sources() -> dict:
    """Recharge toutes les sources sans redémarrer l'application.

    Returns
    -------
    dict
        {source_name: instance}
    """
    from sources import _discover_sources
    return _discover_sources(force_reload=True)


def get_source_info() -> list[dict]:
    """Retourne les métadonnées de toutes les sources disponibles."""
    result = []
    for path in sorted(SOURCES_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        result.append({
            "file":   path.name,
            "name":   path.stem,
            "exists": path.exists(),
        })
    return result
