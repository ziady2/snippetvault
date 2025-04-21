"""Revision history stored alongside snippets in book metadata."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .diffing import DiffResult, compare
from .snippet import Snippet


METADATA_KEY = "revision_history"


def _canonical_payload(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _checksum(data: dict) -> str:
    return hashlib.sha256(_canonical_payload(data).encode("utf-8")).hexdigest()


@dataclass
class Revision:
    id: str
    snippet_id: str
    sequence: int
    snapshot: dict
    created_at: float = field(default_factory=time.time)
    message: str = ""
    author: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        self.id = (self.id or "").strip()
        self.snippet_id = (self.snippet_id or "").strip()
        self.sequence = int(self.sequence)
        self.snapshot = dict(self.snapshot or {})
        self.message = (self.message or "").strip()
        self.author = (self.author or "").strip()
        if not self.id:
            seed = f"{self.snippet_id}:{self.sequence}:{self.created_at:.6f}"
            self.id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        if not self.checksum:
            self.checksum = _checksum(self.snapshot)

    def validate(self) -> None:
        if not self.snippet_id:
            raise ValueError("revision snippet_id is blank")
        if self.sequence < 1:
            raise ValueError("revision sequence must be positive")
        if self.snapshot.get("id") not in {None, "", self.snippet_id}:
            raise ValueError("revision snapshot belongs to another snippet")
        if self.checksum != _checksum(self.snapshot):
            raise ValueError("revision checksum does not match snapshot")

    def to_snippet(self) -> Snippet:
        payload = dict(self.snapshot)
        payload["id"] = self.snippet_id
        return Snippet.from_dict(payload)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "snippet_id": self.snippet_id,
            "sequence": self.sequence,
            "snapshot": dict(self.snapshot),
            "created_at": self.created_at,
            "message": self.message,
            "author": self.author,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Revision":
        revision = cls(
            id=data.get("id", ""),
            snippet_id=data.get("snippet_id", ""),
            sequence=data.get("sequence", 0),
            snapshot=dict(data.get("snapshot") or {}),
            created_at=float(data.get("created_at") or 0),
            message=data.get("message", ""),
            author=data.get("author", ""),
            checksum=data.get("checksum", ""),
        )
        return revision


class RevisionStore:
    """Manage revisions in a book-compatible metadata dictionary."""

    def __init__(self, metadata: Optional[dict] = None) -> None:
        self.metadata = metadata if metadata is not None else {}
        self.metadata.setdefault(METADATA_KEY, {})

    @property
    def _raw(self) -> dict:
        raw = self.metadata.setdefault(METADATA_KEY, {})
        if not isinstance(raw, dict):
            raw = {}
            self.metadata[METADATA_KEY] = raw
        return raw

    def list(self, snippet_id: str) -> List[Revision]:
        revisions: list[Revision] = []
        for raw in self._raw.get(snippet_id, []):
            try:
                revision = Revision.from_dict(raw)
                revision.validate()
            except (TypeError, ValueError):
                continue
            revisions.append(revision)
        return sorted(revisions, key=lambda revision: (revision.sequence, revision.created_at))

    def latest(self, snippet_id: str) -> Optional[Revision]:
        revisions = self.list(snippet_id)
        return revisions[-1] if revisions else None

    def get(self, snippet_id: str, revision_id: str) -> Optional[Revision]:
        for revision in self.list(snippet_id):
            if revision.id == revision_id or str(revision.sequence) == str(revision_id):
                return revision
        return None

    def record(
        self,
        snippet: Snippet,
        *,
        message: str = "",
        author: str = "",
        created_at: Optional[float] = None,
        skip_unchanged: bool = True,
    ) -> Optional[Revision]:
        existing = self.list(snippet.id)
        snapshot = snippet.to_dict()
        checksum = _checksum(snapshot)
        if existing and skip_unchanged and existing[-1].checksum == checksum:
            return None
        revision = Revision(
            id="",
            snippet_id=snippet.id,
            sequence=(existing[-1].sequence + 1) if existing else 1,
            snapshot=snapshot,
            created_at=time.time() if created_at is None else float(created_at),
            message=message,
            author=author,
            checksum=checksum,
        )
        revision.validate()
        self._raw.setdefault(snippet.id, []).append(revision.to_dict())
        return revision

    def remove(self, snippet_id: str, revision_id: str) -> bool:
        raw_revisions = self._raw.get(snippet_id, [])
        for index, raw in enumerate(raw_revisions):
            if raw.get("id") == revision_id or str(raw.get("sequence")) == str(revision_id):
                del raw_revisions[index]
                if not raw_revisions:
                    self._raw.pop(snippet_id, None)
                return True
        return False

    def prune(self, snippet_id: str, *, keep: int = 20) -> int:
        if keep < 0:
            raise ValueError("keep must not be negative")
        revisions = self._raw.get(snippet_id, [])
        remove_count = max(0, len(revisions) - keep)
        if remove_count:
            del revisions[:remove_count]
        if not revisions:
            self._raw.pop(snippet_id, None)
        return remove_count

    def diff(self, snippet_id: str, older: str, newer: str) -> DiffResult:
        left = self.get(snippet_id, older)
        right = self.get(snippet_id, newer)
        if left is None or right is None:
            raise KeyError("revision not found")
        return compare(
            left.snapshot.get("body", ""),
            right.snapshot.get("body", ""),
            old_label=f"revision-{left.sequence}",
            new_label=f"revision-{right.sequence}",
        )

    def restore(self, snippet_id: str, revision_id: str, *, touch: bool = True) -> Snippet:
        revision = self.get(snippet_id, revision_id)
        if revision is None:
            raise KeyError(f"revision not found: {revision_id}")
        snippet = revision.to_snippet()
        if touch:
            snippet.touch()
        return snippet

    def validate(self) -> list[str]:
        errors: list[str] = []
        for snippet_id, raw_revisions in sorted(self._raw.items()):
            expected_sequence = 1
            for raw in raw_revisions:
                try:
                    revision = Revision.from_dict(raw)
                    revision.validate()
                except (TypeError, ValueError) as exc:
                    errors.append(f"{snippet_id}: {exc}")
                    continue
                if revision.sequence != expected_sequence:
                    errors.append(
                        f"{snippet_id}: expected revision {expected_sequence}, got {revision.sequence}"
                    )
                expected_sequence = revision.sequence + 1
        return errors

    def snippet_ids(self) -> list[str]:
        return sorted(self._raw)

    def count(self, snippet_id: Optional[str] = None) -> int:
        if snippet_id is not None:
            return len(self._raw.get(snippet_id, []))
        return sum(len(revisions) for revisions in self._raw.values())


def store_for_book(book) -> RevisionStore:
    metadata = book.data.setdefault("metadata", {})
    return RevisionStore(metadata)


def record_many(store: RevisionStore, snippets: Iterable[Snippet], *, message: str = "") -> int:
    recorded = 0
    for snippet in snippets:
        if store.record(snippet, message=message) is not None:
            recorded += 1
    return recorded
