"""Source provenance records for imported and generated snippets."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .snippet import Snippet


KINDS = {"manual", "file", "url", "gist", "editor", "generated", "import"}


@dataclass(frozen=True)
class SourceRecord:
    kind: str
    locator: str = ""
    imported_at: float = field(default_factory=time.time)
    checksum: str = ""
    tool: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown source kind: {self.kind}")
        if self.checksum and (
            len(self.checksum) != 64
            or any(character not in "0123456789abcdef" for character in self.checksum.lower())
        ):
            raise ValueError("source checksum must be a sha256 digest")

    @classmethod
    def for_text(
        cls,
        text: str,
        *,
        kind: str = "import",
        locator: str = "",
        tool: str = "",
        imported_at: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> "SourceRecord":
        return cls(
            kind=kind,
            locator=locator,
            imported_at=time.time() if imported_at is None else float(imported_at),
            checksum=hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest(),
            tool=tool,
            metadata=dict(metadata or {}),
        )

    def matches_text(self, text: str) -> bool:
        if not self.checksum:
            return False
        actual = hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()
        return actual == self.checksum

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "locator": self.locator,
            "imported_at": self.imported_at,
            "checksum": self.checksum,
            "tool": self.tool,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SourceRecord":
        return cls(
            kind=str(data.get("kind") or "manual"),
            locator=str(data.get("locator") or ""),
            imported_at=float(data.get("imported_at") or 0),
            checksum=str(data.get("checksum") or ""),
            tool=str(data.get("tool") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


class ProvenanceIndex:
    """Map snippet ids to ordered source records."""

    def __init__(self, records: Optional[Dict[str, Iterable[SourceRecord]]] = None) -> None:
        self._records: Dict[str, List[SourceRecord]] = {
            identifier: sorted(list(values), key=lambda record: record.imported_at)
            for identifier, values in (records or {}).items()
        }

    def add(self, snippet_id: str, record: SourceRecord, *, deduplicate: bool = True) -> bool:
        identifier = (snippet_id or "").strip()
        if not identifier:
            raise ValueError("snippet_id is blank")
        records = self._records.setdefault(identifier, [])
        if deduplicate and any(
            existing.kind == record.kind
            and existing.locator == record.locator
            and existing.checksum == record.checksum
            for existing in records
        ):
            return False
        records.append(record)
        records.sort(key=lambda item: item.imported_at)
        return True

    def list(self, snippet_id: str) -> List[SourceRecord]:
        return list(self._records.get(snippet_id, []))

    def latest(self, snippet_id: str) -> Optional[SourceRecord]:
        records = self._records.get(snippet_id, [])
        return records[-1] if records else None

    def remove(self, snippet_id: str, *, locator: str = "", kind: str = "") -> int:
        records = self._records.get(snippet_id, [])
        kept = [
            record
            for record in records
            if not (not locator or record.locator == locator) or not (not kind or record.kind == kind)
        ]
        removed = len(records) - len(kept)
        if kept:
            self._records[snippet_id] = kept
        else:
            self._records.pop(snippet_id, None)
        return removed

    def find_by_locator(self, locator: str) -> List[str]:
        return sorted(
            snippet_id
            for snippet_id, records in self._records.items()
            if any(record.locator == locator for record in records)
        )

    def stale(self, snippets: Iterable[Snippet]) -> List[str]:
        stale_ids: list[str] = []
        for snippet in snippets:
            record = self.latest(snippet.id)
            if record and record.checksum and not record.matches_text(snippet.body):
                stale_ids.append(snippet.id)
        return sorted(stale_ids)

    def orphan_ids(self, known_ids: Iterable[str]) -> List[str]:
        return sorted(set(self._records) - set(known_ids))

    def to_dict(self) -> dict:
        return {
            identifier: [record.to_dict() for record in records]
            for identifier, records in sorted(self._records.items())
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProvenanceIndex":
        records: dict[str, list[SourceRecord]] = {}
        for identifier, raw_records in (data or {}).items():
            parsed: list[SourceRecord] = []
            for raw in raw_records or []:
                try:
                    parsed.append(SourceRecord.from_dict(raw))
                except (TypeError, ValueError):
                    continue
            records[str(identifier)] = parsed
        return cls(records)


def index_for_book(book) -> ProvenanceIndex:
    metadata = book.data.setdefault("metadata", {})
    return ProvenanceIndex.from_dict(metadata.get("provenance") or {})


def save_index(book, index: ProvenanceIndex) -> None:
    book.data.setdefault("metadata", {})["provenance"] = index.to_dict()


def infer(snippet: Snippet) -> SourceRecord:
    source = (snippet.source or "").strip()
    if source.startswith(("http://", "https://")):
        kind = "url"
    elif source.startswith("gist:"):
        kind = "gist"
    elif source:
        kind = "file"
    else:
        kind = "manual"
    return SourceRecord.for_text(snippet.body, kind=kind, locator=source)
