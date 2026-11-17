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
handlers/Analytics.py — Statistiques de lecture locales.

Données sauvegardées dans ~/.tsumi/analytics.json
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ANALYTICS_FILE = Path.home() / ".tsumi" / "analytics.json"


def _load() -> dict:
    if ANALYTICS_FILE.exists():
        try:
            return json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sessions": [], "totals": {}}


def _save(data: dict) -> None:
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANALYTICS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class ReadingSession:
    """Suit une session de lecture (un chapitre ouvert)."""

    def __init__(self, source: str, manga: str, chapter: str) -> None:
        self.source  = source
        self.manga   = manga
        self.chapter = chapter
        self._start  = time.time()
        self._pages_read = 0

    def record_page(self) -> None:
        self._pages_read += 1

    def close(self) -> None:
        duration = int(time.time() - self._start)
        data = _load()

        session = {
            "source":      self.source,
            "manga":       self.manga,
            "chapter":     self.chapter,
            "duration_s":  duration,
            "pages_read":  self._pages_read,
            "ts":          int(self._start),
        }
        data["sessions"].append(session)

        # Totaux agrégés par manga
        key = f"{self.source}::{self.manga}"
        t = data["totals"].setdefault(key, {
            "source": self.source,
            "manga":  self.manga,
            "total_duration_s":  0,
            "total_pages":       0,
            "chapters_finished": 0,
        })
        t["total_duration_s"] += duration
        t["total_pages"]      += self._pages_read

        _save(data)
        logger.debug(
            "Session fermée: %s ch.%s — %ds, %d pages",
            self.manga, self.chapter, duration, self._pages_read,
        )

    def mark_chapter_finished(self) -> None:
        data = _load()
        key  = f"{self.source}::{self.manga}"
        t = data["totals"].setdefault(key, {
            "source": self.source,
            "manga":  self.manga,
            "total_duration_s":  0,
            "total_pages":       0,
            "chapters_finished": 0,
        })
        t["chapters_finished"] += 1
        _save(data)


def get_stats(manga: Optional[str] = None) -> dict:
    """Retourne les statistiques globales ou pour un manga précis."""
    data = _load()
    if manga:
        for key, v in data["totals"].items():
            if v["manga"] == manga:
                return v
        return {}
    return data["totals"]
