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
Scraper pour Rimu Scan (rimuscans.fr / rimuscan.fr).
Site FR de scanlation basé sur WordPress/Madara.
"""

from __future__ import annotations

import logging
import re

from ._base import SourceBase, cached

logger = logging.getLogger("tsumi.sources.rimuscan")

# Domain fallback list — essayé dans l'ordre
_DOMAINS = [
    "https://rimuscans.fr",
    "https://rimuscan.fr",
    "https://www.rimuscans.fr",
]


class RimuScan(SourceBase):
    NAME = "Rimu Scan"
    LANGUAGE = "FR"
    CATEGORIES = ["Manga", "Manhwa", "Manhua", "Webtoon"]

    BASE_URL = _DOMAINS[0]

    # Madara theme AJAX endpoint
    _AJAX_URL = "/wp-admin/admin-ajax.php"

    def __init__(self) -> None:
        super().__init__()
        self._resolved = False  # résolution lazy

    # ------------------------------------------------------------------
    # Domain resolution (lazy)
    # ------------------------------------------------------------------
    def _ensure_domain(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        for domain in _DOMAINS:
            try:
                resp = self._get(domain + "/")
                if resp is not None and resp.status_code < 400:
                    logger.info("[RimuScan] Domaine actif: %s", domain)
                    self.BASE_URL = domain
                    return
            except Exception:
                continue
        logger.warning("[RimuScan] Aucun domaine résolu, utilisation par défaut.")
        self.BASE_URL = _DOMAINS[0]

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    @cached
    def search(self, query: str) -> list[dict]:
        """Recherche via la page /manga?s=query (Madara search)."""
        self._ensure_domain()
        results: list[dict] = []
        url = f"{self.BASE_URL}/?s={query}&post_type=wp-manga"

        soup = self._soup(url, referer=self.BASE_URL + "/")
        if soup is None:
            return results

        # Madara search results container
        for card in soup.select("div.c-tabs-item__content, div.row.c-tabs-item__content"):
            try:
                a_tag = card.select_one("h3.h5 a, .post-title a")
                img_tag = card.select_one("img")
                type_tag = card.select_one(".manga-title-badges, .badge")

                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                url_ = a_tag["href"]
                cover = (
                    img_tag.get("data-src") or img_tag.get("src", "")
                    if img_tag else ""
                )
                media_type = type_tag.get_text(strip=True) if type_tag else "Manga"

                results.append({
                    "title": title,
                    "url": url_,
                    "cover": cover.strip(),
                    "type": media_type,
                })
            except Exception as exc:
                logger.debug("[RimuScan] Erreur parsing card search: %s", exc)

        # Fallback: Madara AJAX search
        if not results:
            results = self._ajax_search(query)

        logger.info("[RimuScan] search('%s') -> %d résultats", query, len(results))
        return results

    def _ajax_search(self, query: str) -> list[dict]:
        """Madara AJAX search fallback."""
        results: list[dict] = []
        resp = self._post(
            self.BASE_URL + self._AJAX_URL,
            data={
                "action": "wp-manga-search-manga",
                "title": query,
            },
            referer=self.BASE_URL + "/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if resp is None:
            return results
        try:
            data = resp.json()
            if data.get("success") and isinstance(data.get("data"), list):
                for item in data["data"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "cover": item.get("thumb", ""),
                        "type": item.get("type", "Manga"),
                    })
        except Exception as exc:
            logger.debug("[RimuScan] AJAX search JSON error: %s", exc)
        return results

    # ------------------------------------------------------------------
    # get_chapters
    # ------------------------------------------------------------------
    @cached
    def get_chapters(self, manga_url: str) -> list[dict]:
        """
        Recupere la liste des chapitres via AJAX Madara (action=manga-chapters).
        Fallback: parsing HTML direct.
        """
        chapters: list[dict] = []

        # Extraire le post ID depuis la page manga
        soup = self._soup(manga_url, referer=self.BASE_URL + "/")
        if soup is None:
            return chapters

        # Trouver l'ID du post (input hidden ou data attribute)
        post_id = None
        id_input = soup.select_one("#manga-chapters-holder[data-id]")
        if id_input:
            post_id = id_input.get("data-id")

        if post_id:
            chapters = self._fetch_chapters_ajax(post_id, manga_url)

        # Fallback: parser directement le HTML
        if not chapters:
            chapters = self._parse_chapters_html(soup, manga_url)

        logger.info("[RimuScan] get_chapters('%s') -> %d chapitres", manga_url, len(chapters))
        return sorted(chapters, key=lambda c: c["number"])

    def _fetch_chapters_ajax(self, post_id: str, referer: str) -> list[dict]:
        chapters: list[dict] = []
        resp = self._post(
            self.BASE_URL + self._AJAX_URL,
            data={
                "action": "manga_get_chapters",
                "manga": post_id,
            },
            referer=referer,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if resp is None:
            return chapters

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_chapters_html(soup, referer)

    def _parse_chapters_html(self, soup, referer: str) -> list[dict]:
        chapters: list[dict] = []
        for li in soup.select("li.wp-manga-chapter"):
            a = li.select_one("a")
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            number = self._extract_number(title, href)
            chapters.append({"title": title, "url": href, "number": number})
        return chapters

    # ------------------------------------------------------------------
    # get_pages
    # ------------------------------------------------------------------
    @cached
    def get_pages(self, chapter_url: str) -> list[str]:
        """
        Recupere les URLs d'images d'un chapitre.
        Utilise ?style=list pour tout recuperer en un seul HTML.
        """
        pages: list[str] = []
        url = chapter_url.rstrip("/") + "?style=list"
        soup = self._soup(url, referer=chapter_url)
        if soup is None:
            return pages

        for img in soup.select("div.reading-content img, .page-break img"):
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src", "")
            src = src.strip()
            if src and src.startswith("http"):
                pages.append(src)

        logger.info("[RimuScan] get_pages('%s') -> %d pages", chapter_url, len(pages))
        return pages

    # ------------------------------------------------------------------
    # get_cover
    # ------------------------------------------------------------------
    @cached
    def get_cover(self, manga_url: str) -> str:
        soup = self._soup(manga_url, referer=self.BASE_URL + "/")
        if soup is None:
            return ""

        # Madara: image principale dans .summary_image
        img = soup.select_one(".summary_image img, .tab-summary img")
        if img:
            return (img.get("data-src") or img.get("src", "")).strip()
        return ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_number(title: str, url: str) -> float:
        """Extrait le numero de chapitre depuis le titre ou l'URL."""
        for text in (title, url):
            m = re.search(r"(?:chapitre?|chap(?:itre)?|ch)[.\s\-_#]*(\d+(?:[.,]\d+)?)", text, re.I)
            if m:
                return float(m.group(1).replace(",", "."))
            m = re.search(r"(\d+(?:[.,]\d+)?)", text)
            if m:
                return float(m.group(1).replace(",", "."))
        return 0.0
