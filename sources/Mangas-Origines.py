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
sources/Mangas-Origines.py — Scraper pour mangas-origines.fr
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from sources._base import SourceBase, cached

logger = logging.getLogger(__name__)


class MangasOrigines(SourceBase):
    NAME       = "Mangas Origines"
    LANGUAGE   = "FR"
    BASE_URL   = "https://mangas-origines.fr"
    CATEGORIES = ["Manga", "Manhwa", "Manhua", "Webtoon"]

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    @cached
    def search(self, query: str) -> list[dict]:
        """Recherche via https://mangas-origines.fr/?s=query."""
        url = f"{self.BASE_URL}/?s={quote_plus(query)}"
        soup = self._get_soup(url)
        if not soup:
            return []

        results = []
        seen_urls = set()

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/oeuvre/" not in href or href in seen_urls:
                continue
            seen_urls.add(href)

            # Image de couverture
            img = a.find("img")
            cover = ""
            if img:
                cover = img.get("src") or img.get("data-src") or ""

            # Extraction d'un titre lisible
            # Souvent le texte direct du lien contient la note genre "4.8Solo LevelingAction"
            raw_text = a.get_text(strip=True)
            title = ""
            h_tag = a.find(["h2", "h3", "h4", "span.title", "div.title"])
            if h_tag:
                title = h_tag.get_text(strip=True)
            
            if not title:
                # Nettoie depuis le slug de l'URL: /oeuvre/826-solo-leveling/ -> "Solo Leveling"
                slug = href.rstrip("/").split("/")[-1]
                slug_clean = re.sub(r"^\d+-", "", slug)
                title = slug_clean.replace("-", " ").title()

            # Nettoie les notes en début de titre (ex: "4.5 Solo Leveling" -> "Solo Leveling")
            title = re.sub(r"^\d+[\.,]\d+\s*", "", title).strip()

            results.append({
                "title": title,
                "url":   href,
                "cover": cover,
                "type":  "Manhwa" if "manhwa" in raw_text.lower() else "Manga",
            })

        logger.info("[MangasOrigines] search('%s') -> %d résultats", query, len(results))
        return results

    # ------------------------------------------------------------------
    # get_chapters
    # ------------------------------------------------------------------
    @cached
    def get_chapters(self, manga_url: str) -> list[dict]:
        """Extrait tous les liens de chapitres /chapitre-<num>/."""
        soup = self._get_soup(manga_url)
        if not soup:
            return []

        chapters = []
        seen = set()

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/chapitre-" in href and href not in seen:
                seen.add(href)
                num = self._parse_chapter_num(href)
                # Ignore les boutons "Commencer" ou "Dernier" si le numéro n'est pas fiable
                title = a.get_text(strip=True)
                if not any(k in title.lower() for k in ("commencer", "dernier")):
                    clean_title = f"Chapitre {int(num) if num == int(num) else num}"
                else:
                    clean_title = f"Chapitre {int(num) if num == int(num) else num}"

                chapters.append({
                    "title":  clean_title,
                    "url":    href,
                    "number": num,
                })

        # Trier du plus ancien au plus récent
        chapters.sort(key=lambda c: c["number"])
        logger.info("[MangasOrigines] %d chapitres pour %s", len(chapters), manga_url)
        return chapters

    # ------------------------------------------------------------------
    # get_pages
    # ------------------------------------------------------------------
    @cached
    def get_pages(self, chapter_url: str) -> list[str]:
        soup = self._get_soup(chapter_url)
        if not soup:
            return []

        pages = []
        for img in soup.find_all("img"):
            src = (img.get("data-src") or img.get("src") or "").strip()
            if not src.startswith("http"):
                continue
            # Filtrer les logos, bannières et pubs
            if "/WP-manga/data/" in src or any(re.search(r"/\d+\.(?:jpg|png|webp)", src, re.I) for _ in [1]):
                pages.append(src)
            elif any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                if not any(k in src.lower() for k in ("logo", "banner", "thumb", "icon", "avatar", "ad")):
                    pages.append(src)

        logger.info("[MangasOrigines] %d pages pour %s", len(pages), chapter_url)
        return pages

    # ------------------------------------------------------------------
    # get_cover
    # ------------------------------------------------------------------
    @cached
    def get_cover(self, manga_url: str) -> str:
        soup = self._get_soup(manga_url)
        if not soup:
            return ""
        for sel in [".thumb img", ".cover img", "img.wp-post-image", "meta[property='og:image']"]:
            el = soup.select_one(sel)
            if not el:
                continue
            if el.name == "meta":
                return el.get("content", "")
            return el.get("src") or el.get("data-src", "")
        return ""
