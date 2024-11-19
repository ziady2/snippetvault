"""In-memory indexes for a loaded snippet book."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set

from .collection import Collection
from .snippet import Snippet


@dataclass(frozen=True)
class CatalogIssue:
    code: str
    message: str
    entity: str = ""


@dataclass
class Catalog:
    """A read-only index rebuilt from snippets and collections."""

    snippets: List[Snippet] = field(default_factory=list)
    collections: List[Collection] = field(default_factory=list)
    _by_id: Dict[str, Snippet] = field(init=False, default_factory=dict)
    _by_slug: Dict[str, Snippet] = field(init=False, default_factory=dict)
    _by_language: Dict[str, List[Snippet]] = field(init=False, default_factory=dict)
    _by_tag: Dict[str, List[Snippet]] = field(init=False, default_factory=dict)
    _collection_ids: Dict[str, Set[str]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.snippets = list(self.snippets)
        self.collections = list(self.collections)
        by_language: dict[str, list[Snippet]] = defaultdict(list)
        by_tag: dict[str, list[Snippet]] = defaultdict(list)
        for snippet in self.snippets:
            self._by_id.setdefault(snippet.id, snippet)
            if snippet.slug:
                self._by_slug.setdefault(snippet.slug.lower(), snippet)
            by_language[(snippet.language or "plain").lower()].append(snippet)
            for tag in snippet.all_tags():
                by_tag[tag.lower()].append(snippet)
        self._by_language = dict(by_language)
        self._by_tag = dict(by_tag)
        self._collection_ids = {
            collection.name.lower(): set(collection.snippet_ids) for collection in self.collections
        }

    @classmethod
    def from_book(cls, book) -> "Catalog":
        return cls(snippets=list(book), collections=book.collections())

    def get(self, identifier: str) -> Optional[Snippet]:
        return self._by_id.get(identifier) or self._by_slug.get((identifier or "").lower())

    def by_language(self, language: str) -> list[Snippet]:
        return list(self._by_language.get((language or "").lower(), []))

    def by_tag(self, tag: str) -> list[Snippet]:
        return list(self._by_tag.get((tag or "").lower(), []))

    def in_collection(self, name: str) -> list[Snippet]:
        ids = self._collection_ids.get((name or "").lower(), set())
        return [snippet for snippet in self.snippets if snippet.id in ids]

    def languages(self) -> list[str]:
        return sorted(self._by_language)

    def tags(self) -> list[str]:
        return sorted(self._by_tag)

    def iter_active(self) -> Iterator[Snippet]:
        return (snippet for snippet in self.snippets if not snippet.archived)

    def related(self, snippet: Snippet, *, limit: int = 5) -> list[Snippet]:
        """Find snippets sharing tags, language or collection membership."""
        scores: Counter = Counter()
        for tag in snippet.all_tags():
            for candidate in self.by_tag(tag):
                if candidate.id != snippet.id:
                    scores[candidate.id] += 3
        for candidate in self.by_language(snippet.language):
            if candidate.id != snippet.id:
                scores[candidate.id] += 1
        for ids in self._collection_ids.values():
            if snippet.id not in ids:
                continue
            for candidate_id in ids:
                if candidate_id != snippet.id:
                    scores[candidate_id] += 2
        ordered = sorted(
            scores,
            key=lambda identifier: (
                -scores[identifier],
                -(self._by_id.get(identifier).updated_at if identifier in self._by_id else 0),
                identifier,
            ),
        )
        return [self._by_id[identifier] for identifier in ordered[: max(0, limit)] if identifier in self._by_id]

    def issues(self) -> list[CatalogIssue]:
        issues: list[CatalogIssue] = []
        id_counts = Counter(snippet.id for snippet in self.snippets)
        slug_counts = Counter(snippet.slug.lower() for snippet in self.snippets if snippet.slug)
        for identifier, count in sorted(id_counts.items()):
            if not identifier:
                issues.append(CatalogIssue("blank_id", "snippet has a blank id"))
            elif count > 1:
                issues.append(CatalogIssue("duplicate_id", f"id appears {count} times", identifier))
        for slug, count in sorted(slug_counts.items()):
            if count > 1:
                issues.append(CatalogIssue("duplicate_slug", f"slug appears {count} times", slug))
        known_ids = set(self._by_id)
        for collection in self.collections:
            for identifier in collection.snippet_ids:
                if identifier not in known_ids:
                    issues.append(
                        CatalogIssue(
                            "dangling_collection_member",
                            f"collection {collection.name!r} references a missing snippet",
                            identifier,
                        )
                    )
        return issues

    def summary(self) -> dict:
        active = sum(1 for snippet in self.snippets if not snippet.archived)
        return {
            "snippets": len(self.snippets),
            "active": active,
            "archived": len(self.snippets) - active,
            "languages": len(self._by_language),
            "tags": len(self._by_tag),
            "collections": len(self.collections),
            "issues": len(self.issues()),
        }

    def as_rows(self) -> list[tuple[str, str, str, int]]:
        return [
            (snippet.id, snippet.slug, snippet.language, len(snippet.all_tags()))
            for snippet in sorted(self.snippets, key=lambda item: item.title.lower())
        ]
