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
handlers/Logs.py — Logging centralisé pour Tsumi.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR  = Path.home() / ".tsumi" / "logs"
LOG_FILE = LOG_DIR / "tsumi.log"

FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Couleurs ANSI console (désactivées si pas de TTY)
_COLORS = {
    "DEBUG":    "\033[36m",
    "INFO":     "\033[32m",
    "WARNING":  "\033[33m",
    "ERROR":    "\033[31m",
    "CRITICAL": "\033[35m",
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        msg = super().format(record)
        import sys
        if sys.stderr.isatty():
            return f"{color}{msg}{_RESET}"
        return msg


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure le logging global de l'application."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return  # déjà configuré

    # Handler fichier avec rotation (5 Mo × 3 backups)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter(FMT, datefmt=DATE_FMT))
    fh.setLevel(logging.DEBUG)

    # Handler console
    ch = logging.StreamHandler()
    ch.setFormatter(_ColorFormatter(FMT, datefmt=DATE_FMT))
    ch.setLevel(logging.INFO)

    root.addHandler(fh)
    root.addHandler(ch)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
