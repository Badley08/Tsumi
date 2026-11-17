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
sources/Anime-Sama.py — Scraper pour Anime-Sama (animes-sama.fr).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from sources._base import SourceBase, cached

logger = logging.getLogger("tsumi.sources.animesama")

_DOMAINS = [
    "https://animes-sama.fr",
    "https://anime-sama.to",
    "https://anime-sama.fr",
]


class AnimeSama(SourceBase):
    NAME = "Anime-Sama"
    LANGUAGE = "FR"
    CATEGORIES = ["Manga", "Manhwa", "Manhua", "Webtoon"]

    BASE_URL = _DOMAINS[0]

    def __init__(self) -> None:
        super().__init__()
        self._resolved = False

    def _ensure_domain(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        for domain in _DOMAINS:
            try:
                resp = self._get(domain + "/")
                if resp is not None and resp.status_code < 400:
                    logger.info("[AnimeSama] Domaine actif: %s", domain)
                    self.BASE_URL = domain
                    return
            except Exception:
                continue
        self.BASE_URL = _DOMAINS[0]

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    @cached
    def search(self, query: str) -> list[dict]:
        self._ensure_domain()
        results: list[dict] = []
        search_url = f"{self.BASE_URL}/catalogue/?search={quote_plus(query)}"
        soup = self._soup(search_url, referer=self.BASE_URL + "/catalogue/")

        if not soup:
            return results

        seen_urls = set()
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/catalogue/" not in href or href == "/catalogue/" or href.endswith("/catalogue") or href in seen_urls:
                continue
            seen_urls.add(href)

            if not href.startswith("http"):
                full_url = self.BASE_URL + href
            else:
                full_url = href

            # Couverture
            img = a.find("img")
            cover = ""
            if img:
                cover = img.get("src") or img.get("data-src") or ""
                if cover and not cover.startswith("http"):
                    cover = self.BASE_URL + cover

            # Titre
            title = a.get_text(strip=True)
            if not title:
                title = href.rstrip("/").split("/")[-1].replace("-", " ").title()

            results.append({
                "title": title,
                "url": full_url,
                "cover": cover,
                "type": "Manga",
            })

        logger.info("[AnimeSama] search('%s') -> %d résultats", query, len(results))
        return results

    # ------------------------------------------------------------------
    # get_chapters
    # ------------------------------------------------------------------
    @cached
    def get_chapters(self, manga_url: str) -> list[dict]:
        self._ensure_domain()
        chapters: list[dict] = []
        soup = self._soup(manga_url, referer=self.BASE_URL + "/catalogue/")
        if not soup:
            return chapters

        seen = set()
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if any(k in href for k in ("/scan/", "/chapitre/", "/chapter/")) and href not in seen:
                seen.add(href)
                if not href.startswith("http"):
                    full_url = self.BASE_URL + href
                else:
                    full_url = href
                title = a.get_text(strip=True)
                num = self._parse_chapter_num(href)
                chapters.append({
                    "title": title or f"Chapitre {int(num) if num == int(num) else num}",
                    "url": full_url,
                    "number": num,
                })

        chapters.sort(key=lambda c: c["number"])
        logger.info("[AnimeSama] get_chapters -> %d chapitres", len(chapters))
        return chapters

    # ------------------------------------------------------------------
    # get_pages
    # ------------------------------------------------------------------
    @cached
    def get_pages(self, chapter_url: str) -> list[str]:
        pages: list[str] = []
        soup = self._soup(chapter_url, referer=chapter_url)
        if not soup:
            return pages

        for img in soup.find_all("img"):
            src = (img.get("data-src") or img.get("src") or "").strip()
            if src.startswith("http") and any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                if not any(k in src.lower() for k in ("logo", "banner", "thumb", "icon", "avatar", "ad")):
                    pages.append(src)

        logger.info("[AnimeSama] get_pages -> %d pages", len(pages))
        return pages

    # ------------------------------------------------------------------
    # get_cover
    # ------------------------------------------------------------------
    @cached
    def get_cover(self, manga_url: str) -> str:
        soup = self._soup(manga_url, referer=self.BASE_URL + "/catalogue/")
        if not soup:
            return ""
        for sel in ["img.coverAnime", "img[class*='cover']", "div.coverContainer img", "meta[property='og:image']"]:
            el = soup.select_one(sel)
            if el:
                if el.name == "meta":
                    return el.get("content", "")
                src = el.get("data-src") or el.get("src", "")
                if src and not src.startswith("http"):
                    src = self.BASE_URL + src
                return src
        return ""
