"""Deterministic snapshots and comparisons for complete books."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional

from .collection import Collection
from .snippet import Snippet


FORMAT_VERSION = 1


def canonical_json(value: object) -> str:
    """Serialise a JSON-compatible value deterministically."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def snippet_checksum(snippet: Snippet) -> str:
    return checksum(snippet.to_dict())


def collection_checksum(collection: Collection) -> str:
    return checksum(collection.to_dict())


@dataclass(frozen=True)
class SnapshotEntry:
    id: str
    checksum: str
    updated_at: float = 0.0
    title: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "checksum": self.checksum,
            "updated_at": self.updated_at,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SnapshotEntry":
        return cls(
            id=str(data.get("id") or ""),
            checksum=str(data.get("checksum") or ""),
            updated_at=float(data.get("updated_at") or 0),
            title=str(data.get("title") or ""),
        )


@dataclass
class BookSnapshot:
    id: str
    created_at: float
    schema_version: int
    snippets: List[SnapshotEntry] = field(default_factory=list)
    collections: List[SnapshotEntry] = field(default_factory=list)
    metadata_checksum: str = ""
    label: str = ""
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        self.snippets = list(self.snippets)
        self.collections = list(self.collections)
        if not self.id:
            payload = {
                "created_at": self.created_at,
                "schema_version": self.schema_version,
                "snippets": [entry.to_dict() for entry in self.snippets],
                "collections": [entry.to_dict() for entry in self.collections],
                "metadata_checksum": self.metadata_checksum,
            }
            self.id = checksum(payload)[:16]

    def validate(self) -> List[str]:
        errors: list[str] = []
        if self.format_version != FORMAT_VERSION:
            errors.append(f"unsupported snapshot format {self.format_version}")
        if self.schema_version < 0:
            errors.append("schema version is negative")
        for name, entries in (("snippet", self.snippets), ("collection", self.collections)):
            ids: set[str] = set()
            for entry in entries:
                if not entry.id:
                    errors.append(f"{name} entry has blank id")
                elif entry.id in ids:
                    errors.append(f"duplicate {name} entry: {entry.id}")
                ids.add(entry.id)
                if len(entry.checksum) != 64:
                    errors.append(f"{name} {entry.id} has invalid checksum")
        return errors

    def digest(self) -> str:
        payload = self.to_dict()
        payload.pop("id", None)
        return checksum(payload)

    def to_dict(self) -> dict:
        return {
            "format_version": self.format_version,
            "id": self.id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "snippets": [entry.to_dict() for entry in self.snippets],
            "collections": [entry.to_dict() for entry in self.collections],
            "metadata_checksum": self.metadata_checksum,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BookSnapshot":
        return cls(
            format_version=int(data.get("format_version") or FORMAT_VERSION),
            id=str(data.get("id") or ""),
            created_at=float(data.get("created_at") or 0),
            schema_version=int(data.get("schema_version") or 0),
            snippets=[SnapshotEntry.from_dict(item) for item in data.get("snippets") or []],
            collections=[SnapshotEntry.from_dict(item) for item in data.get("collections") or []],
            metadata_checksum=str(data.get("metadata_checksum") or ""),
            label=str(data.get("label") or ""),
        )


@dataclass(frozen=True)
class SnapshotDiff:
    snippets_added: tuple[str, ...] = ()
    snippets_removed: tuple[str, ...] = ()
    snippets_changed: tuple[str, ...] = ()
    collections_added: tuple[str, ...] = ()
    collections_removed: tuple[str, ...] = ()
    collections_changed: tuple[str, ...] = ()
    metadata_changed: bool = False
    schema_changed: bool = False

    @property
    def changed(self) -> bool:
        return any(
            (
                self.snippets_added,
                self.snippets_removed,
                self.snippets_changed,
                self.collections_added,
                self.collections_removed,
                self.collections_changed,
                self.metadata_changed,
                self.schema_changed,
            )
        )

    def summary(self) -> dict:
        return {
            "snippets_added": len(self.snippets_added),
            "snippets_removed": len(self.snippets_removed),
            "snippets_changed": len(self.snippets_changed),
            "collections_added": len(self.collections_added),
            "collections_removed": len(self.collections_removed),
            "collections_changed": len(self.collections_changed),
            "metadata_changed": self.metadata_changed,
            "schema_changed": self.schema_changed,
        }


def create(book, *, label: str = "", created_at: Optional[float] = None) -> BookSnapshot:
    snippet_entries = [
        SnapshotEntry(
            id=snippet.id,
            checksum=snippet_checksum(snippet),
            updated_at=snippet.updated_at,
            title=snippet.title,
        )
        for snippet in sorted(book, key=lambda item: item.id)
    ]
    collection_entries = [
        SnapshotEntry(
            id=collection.name,
            checksum=collection_checksum(collection),
            updated_at=collection.updated_at,
            title=collection.name,
        )
        for collection in sorted(book.collections(), key=lambda item: item.name.lower())
    ]
    metadata = dict(book.data.get("metadata") or {})
    metadata.pop("snapshots", None)
    return BookSnapshot(
        id="",
        created_at=time.time() if created_at is None else float(created_at),
        schema_version=int(book.data.get("schema_version") or 0),
        snippets=snippet_entries,
        collections=collection_entries,
        metadata_checksum=checksum(metadata),
        label=(label or "").strip(),
    )


def _compare_entries(before: Iterable[SnapshotEntry], after: Iterable[SnapshotEntry]):
    old = {entry.id: entry.checksum for entry in before}
    new = {entry.id: entry.checksum for entry in after}
    return (
        tuple(sorted(set(new) - set(old))),
        tuple(sorted(set(old) - set(new))),
        tuple(sorted(identifier for identifier in set(old) & set(new) if old[identifier] != new[identifier])),
    )


def compare(before: BookSnapshot, after: BookSnapshot) -> SnapshotDiff:
    snippets_added, snippets_removed, snippets_changed = _compare_entries(
        before.snippets, after.snippets
    )
    collections_added, collections_removed, collections_changed = _compare_entries(
        before.collections, after.collections
    )
    return SnapshotDiff(
        snippets_added=snippets_added,
        snippets_removed=snippets_removed,
        snippets_changed=snippets_changed,
        collections_added=collections_added,
        collections_removed=collections_removed,
        collections_changed=collections_changed,
        metadata_changed=before.metadata_checksum != after.metadata_checksum,
        schema_changed=before.schema_version != after.schema_version,
    )


def store(book, book_snapshot: BookSnapshot, *, keep: int = 25) -> None:
    if keep < 1:
        raise ValueError("keep must be positive")
    snapshots = book.data.setdefault("metadata", {}).setdefault("snapshots", [])
    snapshots.append(book_snapshot.to_dict())
    snapshots.sort(key=lambda item: float(item.get("created_at") or 0))
    del snapshots[:-keep]


def stored(book) -> List[BookSnapshot]:
    results: list[BookSnapshot] = []
    for raw in book.data.get("metadata", {}).get("snapshots", []):
        try:
            item = BookSnapshot.from_dict(raw)
        except (TypeError, ValueError):
            continue
        if not item.validate():
            results.append(item)
    return sorted(results, key=lambda item: item.created_at)
