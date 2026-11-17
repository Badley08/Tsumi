# Tsumi â€” Lecteur de manga, manhwa, manhua et webtoon
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
Tsumi Downloader
~~~~~~~~~~~~~~~~
Gestionnaire de tÃ©lÃ©chargements de chapitres manga en fichiers .cbz.

Usage::

    dl = Downloader()
    dl.on_progress = lambda ch, page, total: print(f"{page}/{total}")
    dl.on_done    = lambda ch, path: print(f"Done: {path}")
    dl.on_error   = lambda ch, err:  print(f"Error: {err}")
    dl.download_chapter(source_instance, "My Manga", chapter_dict)
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
import zipfile
import logging
import threading
import traceback
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor, Future

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SANITIZE_RE = re.compile(r"[^\w\s\-]")
_MULTI_DASH_RE = re.compile(r"[-\s]+")


def sanitize_name(name: str) -> str:
    """Transforme un titre en nom de dossier valide.

    Espaces â†’ tirets, caractÃ¨res spÃ©ciaux supprimÃ©s, casse prÃ©servÃ©e.
    Ex: "The Tutorial is Too Hard!" â†’ "The-Tutorial-is-Too-Hard"
    """
    name = _SANITIZE_RE.sub("", name)
    name = _MULTI_DASH_RE.sub("-", name)
    return name.strip("-")


def _chapter_num(chapter_dict: dict) -> str:
    """Extrait le numÃ©ro de chapitre depuis un dict de chapitre."""
    for key in ("number", "num", "chapter", "ch", "id"):
        if key in chapter_dict:
            val = chapter_dict[key]
            # Normalise "1.0" â†’ "1", "12.5" â†’ "12.5"
            try:
                f = float(val)
                return str(int(f)) if f == int(f) else str(f)
            except (TypeError, ValueError):
                return str(val)
    return "0"


# ---------------------------------------------------------------------------
# Download task
# ---------------------------------------------------------------------------

class _DownloadTask:
    """ReprÃ©sente un chapitre Ã  tÃ©lÃ©charger."""

    def __init__(
        self,
        source,
        manga_title: str,
        chapter_dict: dict,
        cbz_path: Path,
        part_dir: Path,
    ):
        self.source = source
        self.manga_title = manga_title
        self.chapter_dict = chapter_dict
        self.cbz_path = cbz_path
        self.part_dir = part_dir
        self.chapter_num = _chapter_num(chapter_dict)
        # identifiant lisible
        self.label = f"{manga_title} ch.{self.chapter_num}"


# ---------------------------------------------------------------------------
# Main Downloader class
# ---------------------------------------------------------------------------

class Downloader:
    """Gestionnaire de tÃ©lÃ©chargements de chapitres manga.

    Attributes
    ----------
    on_progress : callable(chapter_label, page_index, total_pages)
        AppelÃ© pour chaque image tÃ©lÃ©chargÃ©e (thread-safe via callback).
    on_done : callable(chapter_label, cbz_path)
        AppelÃ© quand un chapitre est entiÃ¨rement tÃ©lÃ©chargÃ© et empaquetÃ©.
    on_error : callable(chapter_label, exception_or_message)
        AppelÃ© si une erreur irrÃ©mÃ©diable survient.
    max_parallel : int
        Nombre de chapitres tÃ©lÃ©chargÃ©s en parallÃ¨le (dÃ©faut: 2).
    """

    # Nombre de workers simultanÃ©s pour les chapitres
    max_parallel: int = 2
    # Nombre de threads pour tÃ©lÃ©charger les images Ã  l'intÃ©rieur d'un chapitre
    _page_workers: int = 4
    # DÃ©lai entre requÃªtes (poli envers le serveur)
    _request_delay: float = 0.3

    # Callbacks (peuvent Ãªtre None)
    on_progress: Optional[Callable[[str, int, int], None]] = None
    on_done:     Optional[Callable[[str, Path], None]]     = None
    on_error:    Optional[Callable[[str, Any], None]]      = None

    def __init__(self) -> None:
        self._session = self._make_session()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._start_executor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_download_dir(self) -> Path:
        """Retourne le dossier racine des tÃ©lÃ©chargements: ~/Tsumi/Downloads."""
        return Path.home() / "Tsumi" / "Downloads"

    def get_chapter_path(
        self, source_name: str, manga_title: str, chapter_num: str | int | float
    ) -> Path:
        """Chemin CBZ prÃ©vu pour un chapitre.

        Ex: ~/Tsumi/Downloads/Rimu-Scan/The-Tutorial-is-Too-Hard/chap1.cbz
        """
        # Normalise le numÃ©ro
        try:
            f = float(chapter_num)
            num_str = str(int(f)) if f == int(f) else str(f)
        except (TypeError, ValueError):
            num_str = str(chapter_num)

        return (
            self.get_download_dir()
            / sanitize_name(source_name)
            / sanitize_name(manga_title)
            / f"chap{num_str}.cbz"
        )

    def download_chapter(
        self,
        source_instance,
        manga_title: str,
        chapter_dict: dict,
    ) -> Future:
        """Enfile un chapitre dans la queue de tÃ©lÃ©chargement.

        Retourne un :class:`concurrent.futures.Future` dont le rÃ©sultat est
        le chemin ``Path`` vers le fichier CBZ crÃ©Ã©.

        Parameters
        ----------
        source_instance :
            Instance d'une source (doit exposer ``get_pages(chapter_dict)``
            et ``NAME``).
        manga_title :
            Titre de l'Å“uvre (sera sanitisÃ© pour le nom de dossier).
        chapter_dict :
            Dictionnaire de chapitre tel que renvoyÃ© par ``get_chapters()``.
        """
        source_name = getattr(source_instance, "NAME", "Unknown")
        chapter_num = _chapter_num(chapter_dict)
        cbz_path = self.get_chapter_path(source_name, manga_title, chapter_num)
        part_dir = cbz_path.parent / f".part_{cbz_path.stem}"

        task = _DownloadTask(
            source=source_instance,
            manga_title=manga_title,
            chapter_dict=chapter_dict,
            cbz_path=cbz_path,
            part_dir=part_dir,
        )

        future = self._executor.submit(self._run_task, task)
        with self._lock:
            self._futures[task.label] = future

        logger.info("EnfilÃ©: %s â†’ %s", task.label, cbz_path)
        return future

    def cancel_all(self) -> None:
        """Annule tous les tÃ©lÃ©chargements en attente (non dÃ©marrÃ©s)."""
        with self._lock:
            for label, fut in list(self._futures.items()):
                if fut.cancel():
                    logger.info("AnnulÃ©: %s", label)

    def shutdown(self, wait: bool = True) -> None:
        """ArrÃªte l'executor proprement."""
        if self._executor:
            self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_executor(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_parallel,
            thread_name_prefix="tsumi-dl",
        )

    @staticmethod
    def _make_session() -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            }
        )
        s.timeout = (10, 30)
        return s

    # ------------------------------------------------------------------
    # Download logic
    # ------------------------------------------------------------------

    def _run_task(self, task: _DownloadTask) -> Path:
        """TÃ©lÃ©charge un chapitre et crÃ©e le CBZ. AppelÃ© dans un thread."""
        try:
            result = self._do_download(task)
            self._emit("on_done", task.label, result)
            return result
        except Exception as exc:
            logger.exception("Erreur pendant le tÃ©lÃ©chargement de %s", task.label)
            self._emit("on_error", task.label, exc)
            raise

    def _do_download(self, task: _DownloadTask) -> Path:
        # Si le CBZ existe dÃ©jÃ , on ne retÃ©lÃ©charge pas
        if task.cbz_path.exists():
            logger.info("CBZ dÃ©jÃ  prÃ©sent: %s", task.cbz_path)
            return task.cbz_path

        # CrÃ©e les dossiers nÃ©cessaires
        task.cbz_path.parent.mkdir(parents=True, exist_ok=True)
        task.part_dir.mkdir(parents=True, exist_ok=True)

        # RÃ©cupÃ¨re la liste des pages depuis la source
        logger.info("RÃ©cupÃ©ration des pages pour %sâ€¦", task.label)
        pages: list[str] = task.source.get_pages(task.chapter_dict)
        if not pages:
            raise ValueError(f"Aucune page trouvÃ©e pour {task.label}")

        total = len(pages)
        logger.info("%d pages pour %s", total, task.label)

        # TÃ©lÃ©charge les images en parallÃ¨le (interne au chapitre)
        downloaded: dict[int, bytes] = {}
        errors: list[str] = []
        dl_lock = threading.Lock()

        def dl_page(idx_url: tuple[int, str]) -> None:
            idx, url = idx_url
            # VÃ©rifie si l'image est dÃ©jÃ  dans le dossier .part (reprise)
            ext = self._guess_ext(url)
            part_file = task.part_dir / f"page_{idx:04d}{ext}"
            if part_file.exists() and part_file.stat().st_size > 0:
                data = part_file.read_bytes()
            else:
                data = self._download_image(url, task)
                if data:
                    part_file.write_bytes(data)
            if data:
                with dl_lock:
                    downloaded[idx] = data
                    self._emit("on_progress", task.label, len(downloaded), total)
            else:
                with dl_lock:
                    errors.append(f"page {idx}")

        with ThreadPoolExecutor(
            max_workers=self._page_workers, thread_name_prefix="tsumi-page"
        ) as page_exec:
            page_exec.map(dl_page, enumerate(pages))

        if errors:
            logger.warning(
                "%d page(s) manquantes pour %s: %s",
                len(errors), task.label, ", ".join(errors),
            )

        # EmpaquÃ¨te en CBZ (= ZIP)
        self._pack_cbz(task, downloaded, pages)

        # Nettoie le dossier .part
        self._cleanup_part(task.part_dir)

        return task.cbz_path

    def _download_image(self, url: str, task: _DownloadTask) -> bytes | None:
        """TÃ©lÃ©charge une image avec retryÃ—3."""
        headers = {}
        # Certains CDN mangent un referer
        referer = getattr(task.source, "BASE_URL", None) or getattr(
            task.source, "url", None
        )
        if referer:
            headers["Referer"] = referer

        for attempt in range(3):
            try:
                resp = self._session.get(url, headers=headers, timeout=(10, 30))
                resp.raise_for_status()
                time.sleep(self._request_delay)
                return resp.content
            except Exception as exc:
                logger.warning(
                    "Tentative %d/3 Ã©chouÃ©e pour %s: %s", attempt + 1, url, exc
                )
                time.sleep(1 * (attempt + 1))
        return None

    @staticmethod
    def _guess_ext(url: str) -> str:
        """DÃ©duit l'extension d'image depuis l'URL."""
        path = url.split("?")[0].lower()
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
            if path.endswith(ext):
                return ext if ext != ".jpeg" else ".jpg"
        return ".jpg"

    def _pack_cbz(
        self,
        task: _DownloadTask,
        downloaded: dict[int, bytes],
        pages: list[str],
    ) -> None:
        """CrÃ©e le fichier CBZ Ã  partir des images tÃ©lÃ©chargÃ©es."""
        tmp_path = task.cbz_path.with_suffix(".cbz.tmp")
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
            for idx in sorted(downloaded):
                ext = self._guess_ext(pages[idx])
                img_name = f"page_{idx:04d}{ext}"
                zf.writestr(img_name, downloaded[idx])
        # Renommage atomique
        tmp_path.replace(task.cbz_path)
        logger.info("CBZ crÃ©Ã©: %s", task.cbz_path)

    @staticmethod
    def _cleanup_part(part_dir: Path) -> None:
        """Supprime le dossier .part aprÃ¨s emballage rÃ©ussi."""
        try:
            for f in part_dir.iterdir():
                f.unlink()
            part_dir.rmdir()
        except Exception:
            pass  # Non-bloquant

    def _emit(self, event: str, *args) -> None:
        """Appelle le callback correspondant de maniÃ¨re thread-safe."""
        cb = getattr(self, event, None)
        if callable(cb):
            try:
                cb(*args)
            except Exception:
                logger.exception("Erreur dans le callback %s", event)

