"""Reusable named selections over a snippet library."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .query import filter_snippets, parse
from .snippet import Snippet


@dataclass
class SavedSelection:
    name: str
    query: str
    description: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    pinned_ids: List[str] = field(default_factory=list)
    excluded_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        self.query = (self.query or "").strip()
        if not self.name:
            raise ValueError("selection name is blank")
        parse(self.query)
        self.pinned_ids = list(dict.fromkeys(value for value in self.pinned_ids if value))
        self.excluded_ids = list(dict.fromkeys(value for value in self.excluded_ids if value))

    def evaluate(self, snippets: Iterable[Snippet]) -> List[Snippet]:
        snippets = list(snippets)
        by_id = {snippet.id: snippet for snippet in snippets}
        result = filter_snippets(snippets, self.query)
        result_ids = {snippet.id for snippet in result}
        for identifier in self.pinned_ids:
            if identifier in by_id and identifier not in result_ids:
                result.append(by_id[identifier])
                result_ids.add(identifier)
        excluded = set(self.excluded_ids)
        return [snippet for snippet in result if snippet.id not in excluded]

    def pin(self, snippet_id: str) -> bool:
        if not snippet_id or snippet_id in self.pinned_ids:
            return False
        self.pinned_ids.append(snippet_id)
        if snippet_id in self.excluded_ids:
            self.excluded_ids.remove(snippet_id)
        self.updated_at = time.time()
        return True

    def exclude(self, snippet_id: str) -> bool:
        if not snippet_id or snippet_id in self.excluded_ids:
            return False
        self.excluded_ids.append(snippet_id)
        if snippet_id in self.pinned_ids:
            self.pinned_ids.remove(snippet_id)
        self.updated_at = time.time()
        return True

    def clear_override(self, snippet_id: str) -> bool:
        changed = False
        if snippet_id in self.pinned_ids:
            self.pinned_ids.remove(snippet_id)
            changed = True
        if snippet_id in self.excluded_ids:
            self.excluded_ids.remove(snippet_id)
            changed = True
        if changed:
            self.updated_at = time.time()
        return changed

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "query": self.query,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned_ids": list(self.pinned_ids),
            "excluded_ids": list(self.excluded_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SavedSelection":
        return cls(
            name=str(data.get("name") or ""),
            query=str(data.get("query") or ""),
            description=str(data.get("description") or ""),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            pinned_ids=list(data.get("pinned_ids") or []),
            excluded_ids=list(data.get("excluded_ids") or []),
        )


class SelectionLibrary:
    def __init__(self, selections: Iterable[SavedSelection] = ()) -> None:
        self._selections: Dict[str, SavedSelection] = {}
        for selection in selections:
            self.add(selection)

    @staticmethod
    def _key(name: str) -> str:
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("selection name is blank")
        return key

    def add(self, selection: SavedSelection, *, replace: bool = False) -> bool:
        key = self._key(selection.name)
        if key in self._selections and not replace:
            return False
        self._selections[key] = selection
        return True

    def get(self, name: str) -> Optional[SavedSelection]:
        return self._selections.get(self._key(name))

    def remove(self, name: str) -> bool:
        return self._selections.pop(self._key(name), None) is not None

    def rename(self, old_name: str, new_name: str) -> bool:
        old_key = self._key(old_name)
        selection = self._selections.get(old_key)
        if selection is None:
            return False
        new_key = self._key(new_name)
        if new_key != old_key and new_key in self._selections:
            raise ValueError(f"selection already exists: {new_name}")
        del self._selections[old_key]
        selection.name = new_name.strip()
        selection.updated_at = time.time()
        self._selections[new_key] = selection
        return True

    def list(self) -> List[SavedSelection]:
        return sorted(self._selections.values(), key=lambda selection: selection.name.lower())

    def evaluate(self, name: str, snippets: Iterable[Snippet]) -> List[Snippet]:
        selection = self.get(name)
        if selection is None:
            raise KeyError(f"selection not found: {name}")
        return selection.evaluate(snippets)

    def to_list(self) -> list[dict]:
        return [selection.to_dict() for selection in self.list()]

    @classmethod
    def from_list(cls, data: Iterable[dict]) -> "SelectionLibrary":
        selections: list[SavedSelection] = []
        for item in data or []:
            try:
                selections.append(SavedSelection.from_dict(item))
            except (TypeError, ValueError):
                continue
        return cls(selections)


def library_for_book(book) -> SelectionLibrary:
    metadata = book.data.setdefault("metadata", {})
    return SelectionLibrary.from_list(metadata.get("saved_selections") or [])


def save_library(book, library: SelectionLibrary) -> None:
    book.data.setdefault("metadata", {})["saved_selections"] = library.to_list()
