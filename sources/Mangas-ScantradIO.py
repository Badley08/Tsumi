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
sources/Mangas-ScantradIO.py — Scraper pour scantrad.io / scantrad-france.com
"""

from __future__ import annotations

import logging

from sources._base import SourceBase

logger = logging.getLogger(__name__)


class ScantradIO(SourceBase):
    NAME       = "Scantrad IO"
    LANGUAGE   = "FR"
    BASE_URL   = "https://scantrad.io"
    CATEGORIES = ["Manga", "Manhwa"]

    def search(self, query: str) -> list[dict]:
        url = f"{self.BASE_URL}/mangas?search={query.replace(' ', '+')}"
        soup = self._get_soup(url)
        if not soup:
            return []

        results = []
        for item in soup.select(".manga-item, .card-manga")[:20]:
            a   = item.select_one("a")
            img = item.select_one("img")
            ttl = item.select_one(".manga-title, h3, h4")
            if not a:
                continue
            href = a.get("href", "")
            if not href.startswith("http"):
                href = self.BASE_URL + href
            results.append({
                "title":  ttl.get_text(strip=True) if ttl else a.get_text(strip=True),
                "url":    href,
                "cover":  img.get("src", "") if img else "",
                "type":   "Manga",
            })
        return results

    def get_chapters(self, manga_url: str) -> list[dict]:
        soup = self._get_soup(manga_url)
        if not soup:
            return []

        chapters = []
        for item in soup.select(".chapter-item, .chapter-row, li.chapter"):
            a   = item.select_one("a")
            if not a:
                continue
            href = a.get("href", "")
            if not href.startswith("http"):
                href = self.BASE_URL + href
            title = a.get_text(strip=True)
            chapters.append({
                "title":  title,
                "url":    href,
                "number": self._parse_chapter_num(title),
            })
        return sorted(chapters, key=lambda c: c["number"])

    def get_pages(self, chapter_url: str) -> list[str]:
        soup = self._get_soup(chapter_url)
        if not soup:
            return []

        pages = []
        for img in soup.select(".chapter-image img, #reader img, .page img"):
            src = img.get("src") or img.get("data-src", "")
            if src and src.startswith("http"):
                pages.append(src)
        return pages

    def get_cover(self, manga_url: str) -> str:
        soup = self._get_soup(manga_url)
        if not soup:
            return ""
        img = soup.select_one(".manga-cover img, .cover img")
        return img.get("src", "") if img else ""
