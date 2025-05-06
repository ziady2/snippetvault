"""High-level application service for library integrations.

Most modules in snippetbox are deliberately functional. ``SnippetService``
provides a stateful facade for applications that want common workflows without
recreating the persistence and metadata plumbing used by the CLI.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

from . import batch, health, quality, query, ranking, sharing, snapshot
from .batch import BatchOperation, BatchPlan
from .catalog import Catalog
from .revision import Revision, RevisionStore, store_for_book
from .review import ReviewQueue, queue_for_book, save_queue
from .selection import SelectionLibrary, library_for_book, save_library
from .snippet import Snippet
from .storage import Book
from .template import SnippetTemplate, TemplateLibrary


@dataclass(frozen=True)
class MutationResult:
    changed: bool
    snippet: Optional[Snippet] = None
    revision: Optional[Revision] = None
    message: str = ""


class SnippetService:
    """Coordinate a loaded ``Book`` and its higher-level features."""

    def __init__(self, book: Book, *, autosave: bool = False) -> None:
        self.book = book
        self.autosave = autosave

    @classmethod
    def open(cls, path: Path, *, create: bool = False, autosave: bool = False) -> "SnippetService":
        path = Path(path)
        book = Book.init(path) if create and not path.exists() else Book.load(path)
        return cls(book, autosave=autosave)

    def save(self) -> None:
        self.book.save()

    def _save_if_needed(self) -> None:
        if self.autosave:
            self.book.save()

    def catalog(self) -> Catalog:
        return Catalog.from_book(self.book)

    def revisions(self) -> RevisionStore:
        return store_for_book(self.book)

    def reviews(self) -> ReviewQueue:
        return queue_for_book(self.book)

    def selections(self) -> SelectionLibrary:
        return library_for_book(self.book)

    def templates(self) -> TemplateLibrary:
        raw = self.book.data.setdefault("metadata", {}).get("templates") or []
        return TemplateLibrary.from_list(raw)

    def save_templates(self, library: TemplateLibrary) -> None:
        self.book.data.setdefault("metadata", {})["templates"] = library.to_list()
        self._save_if_needed()

    def add(
        self,
        snippet: Snippet,
        *,
        revision_message: str = "initial version",
        author: str = "",
        request_review: bool = False,
    ) -> MutationResult:
        self.book.add(snippet)
        revision = self.revisions().record(snippet, message=revision_message, author=author)
        if request_review:
            queue = self.reviews()
            queue.request(snippet.id)
            save_queue(self.book, queue)
        self._save_if_needed()
        return MutationResult(True, snippet, revision, "snippet added")

    def update(
        self,
        snippet: Snippet,
        *,
        revision_message: str = "updated",
        author: str = "",
        record_unchanged: bool = False,
    ) -> MutationResult:
        existing = self.book.get(snippet.id)
        if existing is None:
            return MutationResult(False, None, None, "snippet not found")
        before = existing.to_dict()
        after = snippet.to_dict()
        changed = before != after
        if not changed and not record_unchanged:
            return MutationResult(False, existing, None, "snippet unchanged")
        if not self.book.replace(snippet):
            return MutationResult(False, None, None, "snippet not found")
        revision = self.revisions().record(
            snippet,
            message=revision_message,
            author=author,
            skip_unchanged=not record_unchanged,
        )
        self._save_if_needed()
        return MutationResult(True, snippet, revision, "snippet updated")

    def delete(self, identifier: str) -> MutationResult:
        snippet = self.book.get(identifier) or self.book.get_by_slug(identifier)
        if snippet is None:
            return MutationResult(False, None, None, "snippet not found")
        changed = self.book.delete(snippet.id)
        if changed:
            reviews = queue_for_book(self.book)
            reviews.remove(snippet.id)
            save_queue(self.book, reviews)
            selections = library_for_book(self.book)
            for saved in selections.list():
                saved.clear_override(snippet.id)
            save_library(self.book, selections)
            self._save_if_needed()
        return MutationResult(changed, snippet, None, "snippet deleted" if changed else "snippet not found")

    def structured_query(self, text: str, *, limit: Optional[int] = None) -> list[Snippet]:
        snippets = query.filter_snippets(list(self.book), text)
        snippets.sort(key=lambda item: (-item.updated_at, item.title.lower(), item.id))
        return snippets if limit is None else snippets[: max(0, limit)]

    def ranked_query(
        self,
        text: str,
        *,
        profile: Optional[ranking.RankingProfile] = None,
        limit: int = 20,
    ) -> list[ranking.RankedSnippet]:
        candidates = self.structured_query(text)
        return ranking.rank(candidates, text, profile=profile, limit=limit)

    def related(self, identifier: str, *, limit: int = 5) -> list[Snippet]:
        catalog = self.catalog()
        snippet = catalog.get(identifier)
        if snippet is None:
            return []
        return catalog.related(snippet, limit=limit)

    def instantiate(
        self,
        template_name: str,
        values: Mapping[str, object],
        *,
        add: bool = False,
        source: str = "",
    ) -> Snippet:
        snippet = self.templates().instantiate(template_name, values, source=source)
        if add:
            self.add(snippet, revision_message=f"created from template {template_name}")
        return snippet

    def add_template(self, template: SnippetTemplate, *, replace: bool = False) -> bool:
        library = self.templates()
        changed = library.add(template, replace=replace)
        if changed:
            self.save_templates(library)
        return changed

    def plan_batch(
        self,
        operations: Iterable[BatchOperation],
        *,
        query_text: str = "",
    ) -> BatchPlan:
        predicate = query.compile_predicate(query_text) if query_text else None
        return batch.plan(list(self.book), operations, predicate=predicate)

    def apply_batch(self, batch_plan: BatchPlan, *, revision_message: str = "batch edit") -> int:
        revisions = self.revisions()
        changed = 0
        for item in batch_plan.changed():
            snippet = Snippet.from_dict(copy.deepcopy(item.after))
            snippet.touch()
            if self.book.replace(snippet):
                revisions.record(snippet, message=revision_message)
                changed += 1
        if changed:
            self._save_if_needed()
        return changed

    def request_review(
        self,
        identifier: str,
        *,
        assignee: str = "",
        priority: int = 0,
        labels: Iterable[str] = (),
    ):
        snippet = self.book.get(identifier) or self.book.get_by_slug(identifier)
        if snippet is None:
            raise KeyError(f"snippet not found: {identifier}")
        queue = self.reviews()
        record = queue.request(
            snippet.id,
            assignee=assignee,
            priority=priority,
            labels=labels,
        )
        save_queue(self.book, queue)
        self._save_if_needed()
        return record

    def transition_review(
        self,
        identifier: str,
        status: str,
        *,
        reviewer: str = "",
        note: str = "",
    ):
        queue = self.reviews()
        record = queue.get(identifier)
        if record is None:
            snippet = self.book.get_by_slug(identifier)
            record = queue.get(snippet.id) if snippet is not None else None
        if record is None:
            raise KeyError(f"review not found: {identifier}")
        event = record.transition(status, reviewer=reviewer, note=note)
        save_queue(self.book, queue)
        self._save_if_needed()
        return event

    def snapshot(self, *, label: str = "", store: bool = False) -> snapshot.BookSnapshot:
        result = snapshot.create(self.book, label=label)
        if store:
            snapshot.store(self.book, result)
            self._save_if_needed()
        return result

    def health(self, *, now: float = 0) -> health.HealthReport:
        return health.inspect_book(self.book, now=now)

    def quality(self, *, now: Optional[float] = None) -> quality.LibraryQuality:
        return quality.score_library(list(self.book), now=now)

    def share(
        self,
        *,
        profile: Optional[sharing.SharingProfile] = None,
        query_text: str = "",
    ) -> list[sharing.SharedSnippet]:
        snippets = self.structured_query(query_text) if query_text else list(self.book)
        return sharing.redact_many(snippets, profile)
