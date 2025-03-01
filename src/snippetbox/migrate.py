"""Schema migrations for the JSON book.

We've bumped the schema three times so far:

- ``0 -> 1``: initial published shape.
- ``1 -> 2``: added ``collections``, gave each snippet a stable ``slug``.
- ``2 -> 3``: split ``tags`` (manual) from ``auto_tags`` so the
  auto-tagger can re-run without nuking my hand-tags.

Each migration takes a dict and returns a (possibly mutated) dict.
We always migrate forward; backward migration is not supported.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Dict

from .errors import MigrationError


CURRENT_SCHEMA = 3


def current_schema_version() -> int:
    return CURRENT_SCHEMA


def needs_migration(book: dict) -> bool:
    return _read_version(book) < CURRENT_SCHEMA


def _read_version(book: dict) -> int:
    raw = book.get("schema_version")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def migrate(book):
    """Return ``book`` migrated to ``CURRENT_SCHEMA``.

    Accepts either a dict or a bare list (treated as v0). Anything
    else raises ``MigrationError``.
    """
    if isinstance(book, list):
        # v0 books were a bare list — _migrate_0_to_1 wraps them.
        book = {"snippets": list(book)}
    if not isinstance(book, dict):
        raise MigrationError("book is not a dict", from_v=-1, to_v=CURRENT_SCHEMA)
    v = _read_version(book)
    if v > CURRENT_SCHEMA:
        raise MigrationError(
            f"book schema {v} is newer than current {CURRENT_SCHEMA}; can't downgrade",
            from_v=v,
            to_v=CURRENT_SCHEMA,
        )
    while v < CURRENT_SCHEMA:
        try:
            step = _STEPS[v]
        except KeyError as exc:
            raise MigrationError(
                f"no migration registered for {v} -> {v + 1}",
                from_v=v,
                to_v=v + 1,
            ) from exc
        book = step(book)
        v += 1
        book["schema_version"] = v
    return book


# -----------------------------------------------------------------
# concrete migrations
# -----------------------------------------------------------------


def _slugify(text: str) -> str:
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] if s else ""


def _migrate_0_to_1(book: dict) -> dict:
    """Pre-1.0: input might be a bare list of snippets, or have no metadata."""
    if isinstance(book, list):
        book = {"snippets": book}
    book.setdefault("metadata", {"created_at": time.time(), "version": "0.1.0"})
    book.setdefault("snippets", [])
    for s in book["snippets"]:
        # in 0.x there was no 'language' key at all; default to plain
        s.setdefault("language", "plain")
        s.setdefault("tags", [])
        s.setdefault("title", "")
        s.setdefault("body", "")
        s.setdefault("created_at", time.time())
        s.setdefault("updated_at", time.time())
    return book


def _migrate_1_to_2(book: dict) -> dict:
    """Add ``collections`` + per-snippet ``slug``."""
    book.setdefault("collections", [])
    seen: dict = {}
    for s in book.get("snippets", []):
        if not s.get("slug"):
            base = _slugify(s.get("title", "")) or s.get("id", "snip")[:8]
            slug = base
            n = 2
            while slug in seen:
                slug = f"{base}-{n}"
                n += 1
            seen[slug] = True
            s["slug"] = slug
        else:
            seen[s["slug"]] = True
    return book


def _migrate_2_to_3(book: dict) -> dict:
    """Split tags into manual (``tags``) and auto (``auto_tags``).

    In schema 2 the auto-tagger overwrote ``tags`` directly. We move
    every tag prefixed with ``auto:`` into ``auto_tags`` and drop the
    prefix.
    """
    for s in book.get("snippets", []):
        manual: list = []
        auto: list = []
        for t in s.get("tags") or []:
            if isinstance(t, str) and t.startswith("auto:"):
                auto.append(t[len("auto:") :])
            else:
                manual.append(t)
        s["tags"] = manual
        # don't drop existing auto_tags if a friendly user already had some
        existing = s.get("auto_tags") or []
        for t in auto:
            if t not in existing:
                existing.append(t)
        s["auto_tags"] = existing
        # archived / favourite started life in v2 as 0/1; coerce
        for key in ("archived", "favourite"):
            if key in s and not isinstance(s[key], bool):
                s[key] = bool(s[key])
    return book


_STEPS: Dict[int, Callable[[dict], dict]] = {
    0: _migrate_0_to_1,
    1: _migrate_1_to_2,
    2: _migrate_2_to_3,
}


def describe_step(v_from: int) -> str:
    """Human-readable description of the migration ``v_from -> v_from+1``."""
    table = {
        0: "initial -> 1: add metadata + ensure required fields",
        1: "1 -> 2: add collections; assign per-snippet slug",
        2: "2 -> 3: split manual tags from auto-generated tags",
    }
    return table.get(v_from, f"unknown step {v_from}")


def history() -> list:
    """List of all migration steps in order. Useful for ``snippetbox migrate --plan``."""
    return [(v, v + 1, describe_step(v)) for v in sorted(_STEPS.keys())]


def can_migrate(book: dict) -> bool:
    v = _read_version(book)
    return v in _STEPS or v == CURRENT_SCHEMA
