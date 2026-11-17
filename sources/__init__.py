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
sources/__init__.py — Auto-discovery des sources pluggables.
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_SOURCES_DIR = Path(__file__).parent
_cache: dict = {}


def _discover_sources(force_reload: bool = False) -> dict:
    global _cache
    if _cache and not force_reload:
        return _cache

    result = {}
    for path in sorted(_SOURCES_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        mod_name = f"sources.{path.stem}"
        try:
            if force_reload and mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)

            # Cherche une classe avec attribut NAME (convention de base)
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name)
                if (
                    isinstance(cls, type)
                    and hasattr(cls, "NAME")
                    and hasattr(cls, "search")
                    and cls.__name__ != "SourceBase"
                ):
                    instance = cls()
                    result[instance.NAME] = instance
                    logger.debug("Source chargée: %s", instance.NAME)
                    break
        except Exception as exc:
            logger.warning("Impossible de charger la source %s: %s", path.stem, exc)

    _cache = result
    return result


def get_all() -> dict:
    """Retourne toutes les sources disponibles: {name: instance}."""
    return _discover_sources()
