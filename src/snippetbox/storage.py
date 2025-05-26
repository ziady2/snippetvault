"""JSON-on-disk storage.

The storage layer uses one JSON file (the "book") with this rough
shape:

::

    {
        "schema_version": 3,
        "snippets": [...],
        "collections": [...],
        "metadata": {...}
    }

Writes are atomic: we write to ``book.json.tmp`` and ``os.replace``
into place. That's a Windows-safe rename.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .collection import Collection
from .errors import BookNotFoundError, DuplicateSlugError, InvalidSnippetError
from .migrate import current_schema_version, migrate
from .snippet import Snippet


DEFAULT_BOOK_NAME = "book.json"


def default_book_path() -> Path:
    """Resolve the default book path: ``$SNIPPETBOX_BOOK`` or ``~/.snippetbox/book.json``."""
    env = os.environ.get("SNIPPETBOX_BOOK")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".snippetbox" / DEFAULT_BOOK_NAME


def empty_book() -> dict:
    return {
        "schema_version": current_schema_version(),
        "snippets": [],
        "collections": [],
        "metadata": {
            "created_at": time.time(),
            "version": "2.0.0",
        },
    }


class Book:
    """A loaded book."""

    def __init__(self, path: Path, data: Optional[dict] = None) -> None:
        self.path = Path(path)
        self.data = data if data is not None else empty_book()

    # ----- factory helpers -----

    @classmethod
    def load(cls, path: Path) -> "Book":
        p = Path(path)
        if not p.exists():
            raise BookNotFoundError(str(p))
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            # we keep the original message; the CLI will dress it up
            raise InvalidSnippetError(f"book is not valid JSON: {exc}") from exc
        data = migrate(raw)
        return cls(p, data)

    @classmethod
    def init(cls, path: Path, *, overwrite: bool = False) -> "Book":
        p = Path(path)
        if p.exists() and not overwrite:
            return cls.load(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        book = cls(p, empty_book())
        book.save()
        return book

    # ----- snippet access -----

    def snippets(self) -> List[Snippet]:
        return [Snippet.from_dict(s) for s in self.data.get("snippets", [])]

    def get(self, snippet_id: str) -> Optional[Snippet]:
        for raw in self.data.get("snippets", []):
            if raw.get("id") == snippet_id:
                return Snippet.from_dict(raw)
        return None

    def get_by_slug(self, slug: str) -> Optional[Snippet]:
        target = (slug or "").lower()
        for raw in self.data.get("snippets", []):
            if (raw.get("slug") or "").lower() == target:
                return Snippet.from_dict(raw)
        return None

    def add(self, snippet: Snippet) -> None:
        snippet.validate()
        for s in self.data.get("snippets", []):
            if s.get("slug") and snippet.slug and s["slug"] == snippet.slug and s["id"] != snippet.id:
                raise DuplicateSlugError(snippet.slug)
        self.data.setdefault("snippets", []).append(snippet.to_dict())

    def replace(self, snippet: Snippet) -> bool:
        snippet.validate()
        snippets = self.data.setdefault("snippets", [])
        for i, raw in enumerate(snippets):
            if raw.get("id") == snippet.id:
                snippets[i] = snippet.to_dict()
                return True
        return False

    def delete(self, snippet_id: str) -> bool:
        snippets = self.data.setdefault("snippets", [])
        for i, raw in enumerate(snippets):
            if raw.get("id") == snippet_id:
                del snippets[i]
                # also drop from collections
                for coll in self.data.get("collections", []):
                    ids = coll.get("snippet_ids") or []
                    if snippet_id in ids:
                        ids.remove(snippet_id)
                return True
        return False

    def __iter__(self) -> Iterator[Snippet]:
        for raw in self.data.get("snippets", []):
            yield Snippet.from_dict(raw)

    def __len__(self) -> int:
        return len(self.data.get("snippets", []))

    # ----- collection access -----

    def collections(self) -> List[Collection]:
        return [Collection.from_dict(c) for c in self.data.get("collections", [])]

    def get_collection(self, name: str) -> Optional[Collection]:
        target = (name or "").lower()
        for raw in self.data.get("collections", []):
            if (raw.get("name") or "").lower() == target:
                return Collection.from_dict(raw)
        return None

    def upsert_collection(self, collection: Collection) -> None:
        cs = self.data.setdefault("collections", [])
        for i, raw in enumerate(cs):
            if (raw.get("name") or "").lower() == collection.name.lower():
                cs[i] = collection.to_dict()
                return
        cs.append(collection.to_dict())

    def remove_collection(self, name: str) -> bool:
        cs = self.data.setdefault("collections", [])
        target = (name or "").lower()
        for i, raw in enumerate(cs):
            if (raw.get("name") or "").lower() == target:
                del cs[i]
                return True
        return False

    # ----- metadata -----

    def metadata(self) -> dict:
        return dict(self.data.get("metadata") or {})

    def set_metadata(self, key: str, value) -> None:
        self.data.setdefault("metadata", {})[key] = value

    def stats(self) -> dict:
        snips = self.data.get("snippets", [])
        return {
            "snippet_count": len(snips),
            "collection_count": len(self.data.get("collections", [])),
            "schema_version": self.data.get("schema_version"),
            "languages": sorted({s.get("language") for s in snips if s.get("language")}),
        }

    # ----- write -----

    def save(self, *, indent: int = 2) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, self.data, indent=indent)


def atomic_write_json(path: Path, data: dict, *, indent: int = 2) -> None:
    """Write JSON to ``path`` via a temp + rename.

    Why: a power cut between ``open`` and ``write`` would otherwise
    truncate the book.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=False)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(encoded)
            if not encoded.endswith("\n"):
                f.write("\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Some filesystems (e.g. tmpfs) don't support fsync.
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            # bare try/except because Windows likes to lock files
            pass
        raise


def copy_book(src: Path, dst: Path) -> None:
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise BookNotFoundError(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def book_size(path: Path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return p.stat().st_size


def book_exists(path: Path) -> bool:
    return Path(path).exists()


def merge_into(book: Book, snippets: Iterable[Snippet]) -> int:
    added = 0
    for s in snippets:
        if book.get(s.id):
            continue
        try:
            book.add(s)
        except DuplicateSlugError:
            s.slug = s.slug + "-" + s.id[:4]
            book.add(s)
        added += 1
    return added
