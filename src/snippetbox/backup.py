"""Backup + restore.

A backup is just a timestamped copy of the book file. There's no
clever incremental scheme. Disk space is cheap, my time isn't.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List

from .errors import BookNotFoundError


_BACKUP_DIR = "backups"
_FORMAT = "book-{ts}.json"


def backup_dir(book_path: Path) -> Path:
    return Path(book_path).parent / _BACKUP_DIR


def make_backup(book_path: Path, *, label: str = "") -> Path:
    """Copy ``book_path`` into ``<book_dir>/backups/book-<timestamp>.json``.

    Returns the new path.
    """
    book_path = Path(book_path)
    if not book_path.exists():
        raise BookNotFoundError(str(book_path))
    bd = backup_dir(book_path)
    bd.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    name = _FORMAT.format(ts=ts) + suffix
    target = bd / name
    shutil.copy2(book_path, target)
    return target


def list_backups(book_path: Path) -> List[Path]:
    bd = backup_dir(book_path)
    if not bd.exists():
        return []
    return sorted(bd.glob("book-*.json*"))


def latest_backup(book_path: Path):
    backups = list_backups(book_path)
    return backups[-1] if backups else None


def restore_backup(book_path: Path, backup_path: Path) -> None:
    book_path = Path(book_path)
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise BookNotFoundError(str(backup_path))
    # validate it parses as JSON before clobbering the live book
    json.loads(backup_path.read_text(encoding="utf-8"))
    book_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, book_path)


def prune_backups(book_path: Path, *, keep: int = 10) -> int:
    backups = list_backups(book_path)
    if len(backups) <= keep:
        return 0
    to_remove = backups[: len(backups) - keep]
    for p in to_remove:
        try:
            p.unlink()
        except OSError:
            # bare try/except because Windows likes to lock files
            pass
    return len(to_remove)


def total_backup_size(book_path: Path) -> int:
    return sum(p.stat().st_size for p in list_backups(book_path) if p.exists())


def parse_backup_timestamp(path: Path):
    name = Path(path).name
    if not name.startswith("book-") or len(name) < len("book-XXXXXXXX-XXXXXX.json"):
        return None
    raw = name[5:5 + 15]  # YYYYMMDD-HHMMSS
    try:
        return datetime.strptime(raw, "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def age_seconds(path: Path) -> float:
    ts = parse_backup_timestamp(path)
    if ts is None:
        return float("inf")
    return time.time() - ts.timestamp()


def find_by_label(book_path: Path, label: str):
    if not label:
        return None
    for p in list_backups(book_path):
        if p.name.endswith("-" + label):
            return p
    return None
