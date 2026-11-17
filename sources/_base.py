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
Base class for all Tsumi manga sources.
Provides: rotating User-Agents, rate limiting, in-memory TTL cache,
robust error handling, and the common SourceBase interface.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from functools import wraps
from threading import Lock
from typing import Any, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("tsumi.sources")

# ---------------------------------------------------------------------------
# User-Agent pool
# ---------------------------------------------------------------------------
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


# ---------------------------------------------------------------------------
# TTL in-memory cache
# ---------------------------------------------------------------------------
class _TTLCache:
    """Thread-safe TTL cache (default 10 minutes)."""

    def __init__(self, ttl: float = 600.0) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> tuple[bool, Any]:
        with self._lock:
            if key in self._store:
                value, ts = self._store[key]
                if time.monotonic() - ts < self._ttl:
                    return True, value
                del self._store[key]
        return False, None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic())

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def cached(method: Callable) -> Callable:
    """Decorator: cache the return value of an instance method using self._cache."""

    @wraps(method)
    def wrapper(self: "SourceBase", *args, **kwargs):
        key = f"{method.__name__}:{args}:{sorted(kwargs.items())}"
        hit, value = self._cache.get(key)
        if hit:
            logger.debug("[%s] Cache hit for %s", self.NAME, key)
            return value
        result = method(self, *args, **kwargs)
        self._cache.set(key, result)
        return result

    return wrapper


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, min_delay: float = 0.5, max_delay: float = 1.5) -> None:
        self._min = min_delay
        self._max = max_delay
        self._last: float = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            delay = random.uniform(self._min, self._max)
            if elapsed < delay:
                sleep_for = delay - elapsed
                time.sleep(sleep_for)
            self._last = time.monotonic()


# ---------------------------------------------------------------------------
# SourceBase
# ---------------------------------------------------------------------------
class SourceBase(ABC):
    """Abstract base class every Tsumi source must extend."""

    NAME: str = "Unknown Source"
    LANGUAGE: str = "FR"
    CATEGORIES: list[str] = ["Manga"]

    # Subclasses can override these
    BASE_URL: str = ""
    _RATE_MIN: float = 0.5
    _RATE_MAX: float = 1.5
    _CACHE_TTL: float = 600.0  # 10 minutes
    _TIMEOUT: int = 20
    _MAX_RETRIES: int = 3

    def __init__(self) -> None:
        self._cache = _TTLCache(ttl=self._CACHE_TTL)
        self._rate = _RateLimiter(self._RATE_MIN, self._RATE_MAX)
        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Session factory
    # ------------------------------------------------------------------
    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self._MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(self._base_headers())
        return session

    def _base_headers(self) -> dict[str, str]:
        return {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def _rotate_ua(self) -> None:
        """Rotate the User-Agent on the current session."""
        self._session.headers["User-Agent"] = _random_ua()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        referer: str | None = None,
        json_response: bool = False,
    ) -> requests.Response | dict | None:
        self._rate.wait()
        self._rotate_ua()
        h = {}
        if referer:
            h["Referer"] = referer
        if headers:
            h.update(headers)
        try:
            resp = self._session.get(
                url,
                params=params,
                headers=h or None,
                timeout=self._TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
            if json_response:
                return resp.json()
            return resp
        except requests.exceptions.HTTPError as exc:
            logger.warning("[%s] HTTP %s for %s", self.NAME, exc.response.status_code, url)
        except requests.exceptions.ConnectionError as exc:
            logger.error("[%s] Connection error for %s: %s", self.NAME, url, exc)
        except requests.exceptions.Timeout:
            logger.error("[%s] Timeout for %s", self.NAME, url)
        except requests.exceptions.RequestException as exc:
            logger.error("[%s] Request error for %s: %s", self.NAME, url, exc)
        return None

    def _post(
        self,
        url: str,
        *,
        data: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        referer: str | None = None,
    ) -> requests.Response | None:
        self._rate.wait()
        self._rotate_ua()
        h = {}
        if referer:
            h["Referer"] = referer
        if headers:
            h.update(headers)
        try:
            resp = self._session.post(
                url,
                data=data,
                json=json,
                headers=h or None,
                timeout=self._TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as exc:
            logger.error("[%s] POST error for %s: %s", self.NAME, url, exc)
        return None

    # ------------------------------------------------------------------
    # Abstract interface — every source MUST implement these
    # ------------------------------------------------------------------
    @abstractmethod
    def search(self, query: str) -> list[dict]:
        """
        Search for manga/manhwa/webtoon.

        Returns:
            list of dicts: [{"title": str, "url": str, "cover": str, "type": str}]
        """

    @abstractmethod
    def get_chapters(self, manga_url: str) -> list[dict]:
        """
        Get chapter list for a given manga URL.

        Returns:
            list of dicts: [{"title": str, "url": str, "number": float}]
            Sorted ascending by chapter number.
        """

    @abstractmethod
    def get_pages(self, chapter_url: str) -> list[str]:
        """
        Get page image URLs for a chapter.

        Returns:
            list of image URL strings, in page order.
        """

    @abstractmethod
    def get_cover(self, manga_url: str) -> str:
        """
        Get the cover image URL for a manga.

        Returns:
            URL string of the cover image.
        """

    # ------------------------------------------------------------------
    # Convenience helpers for subclasses
    # ------------------------------------------------------------------
    def _soup(self, url: str, **get_kwargs):
        """Fetch URL and return BeautifulSoup object, or None on failure."""
        from bs4 import BeautifulSoup

        resp = self._get(url, **get_kwargs)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    # Alias utilisé par les scrapers
    def _get_soup(self, url: str, **kw):
        return self._soup(url, **kw)

    def _parse_chapter_num(self, text: str) -> float:
        """Extrait un numéro de chapitre flottant depuis une chaîne."""
        import re
        m = re.search(r"(\d+(?:[.,]\d+)?)", str(text))
        if m:
            return float(m.group(1).replace(",", "."))
        return 0.0

    def clear_cache(self) -> None:
        self._cache.clear()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.NAME!r} lang={self.LANGUAGE!r}>"
