"""Collections - named groups of snippets.

A snippet can belong to many collections. The book stores the
membership as a list of snippet ids per collection (so we don't have
to mutate snippets when collections change).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, List


def _now() -> float:
    return time.time()


@dataclass
class Collection:
    name: str
    description: str = ""
    snippet_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        self.snippet_ids = list(dict.fromkeys(self.snippet_ids))  # dedupe, keep order

    def add(self, snippet_id: str) -> bool:
        if not snippet_id:
            return False
        if snippet_id in self.snippet_ids:
            return False
        self.snippet_ids.append(snippet_id)
        self.updated_at = _now()
        return True

    def remove(self, snippet_id: str) -> bool:
        if snippet_id in self.snippet_ids:
            self.snippet_ids.remove(snippet_id)
            self.updated_at = _now()
            return True
        return False

    def contains(self, snippet_id: str) -> bool:
        return snippet_id in self.snippet_ids

    def size(self) -> int:
        return len(self.snippet_ids)

    def is_empty(self) -> bool:
        return not self.snippet_ids

    def rename(self, new_name: str) -> None:
        new_name = (new_name or "").strip()
        if not new_name:
            return
        self.name = new_name
        self.updated_at = _now()

    def replace_ids(self, ids: Iterable) -> None:
        self.snippet_ids = list(dict.fromkeys(ids))
        self.updated_at = _now()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "snippet_ids": list(self.snippet_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Collection":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            snippet_ids=list(data.get("snippet_ids") or []),
            created_at=float(data.get("created_at") or _now()),
            updated_at=float(data.get("updated_at") or _now()),
        )


def merge(a: Collection, b: Collection, name: str = "") -> Collection:
    """Merge two collections into a new one. Order: a then b."""
    out_ids = list(a.snippet_ids) + [i for i in b.snippet_ids if i not in a.snippet_ids]
    return Collection(
        name=name or a.name,
        description=a.description or b.description,
        snippet_ids=out_ids,
    )


def difference(a: Collection, b: Collection, name: str = "") -> Collection:
    bids = set(b.snippet_ids)
    out_ids = [i for i in a.snippet_ids if i not in bids]
    return Collection(name=name or a.name + "-minus-" + b.name, snippet_ids=out_ids)


def intersection(a: Collection, b: Collection, name: str = "") -> Collection:
    bids = set(b.snippet_ids)
    out_ids = [i for i in a.snippet_ids if i in bids]
    return Collection(name=name or "shared", snippet_ids=out_ids)


def find_by_name(collections, name: str) -> "Collection":
    target = (name or "").strip().lower()
    for c in collections:
        if c.name.lower() == target:
            return c
    return None  # type: ignore[return-value]


def names(collections) -> List[str]:
    return [c.name for c in collections]


def sort_by_size(collections) -> List["Collection"]:
    return sorted(collections, key=lambda c: -c.size())


def sort_alpha(collections) -> List["Collection"]:
    return sorted(collections, key=lambda c: c.name.lower())
