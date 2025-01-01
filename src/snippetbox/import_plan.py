"""Preview imports and resolve id, slug, and content collisions."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .identifiers import unique_slug
from .snippet import Snippet


ADD = "add"
SKIP = "skip"
REPLACE = "replace"
RENAME = "rename"
CONFLICT = "conflict"
ACTIONS = {ADD, SKIP, REPLACE, RENAME, CONFLICT}


@dataclass
class ImportItem:
    incoming: Snippet
    action: str
    existing: Optional[Snippet] = None
    reason: str = ""
    original_slug: str = ""

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"unknown import action: {self.action}")

    @property
    def conflict(self) -> bool:
        return self.action == CONFLICT

    def resolve(self, action: str) -> None:
        if action not in {SKIP, REPLACE, RENAME}:
            raise ValueError(f"invalid conflict resolution: {action}")
        if not self.conflict:
            raise ValueError("import item is not a conflict")
        self.action = action
        self.reason = f"conflict resolved using {action}"


@dataclass
class ImportPlan:
    items: List[ImportItem] = field(default_factory=list)

    @property
    def conflicts(self) -> List[ImportItem]:
        return [item for item in self.items if item.conflict]

    @property
    def ready(self) -> bool:
        return not self.conflicts

    def counts(self) -> dict:
        counts = {action: 0 for action in sorted(ACTIONS)}
        for item in self.items:
            counts[item.action] += 1
        return counts

    def resolve_all(self, action: str) -> int:
        resolved = 0
        for item in self.conflicts:
            item.resolve(action)
            resolved += 1
        return resolved

    def render(self) -> str:
        rows: list[str] = []
        for item in self.items:
            marker = "!" if item.conflict else " "
            rows.append(
                f"{marker} {item.incoming.id:<16} {item.action:<9} "
                f"{item.incoming.slug:<24} {item.reason}"
            )
        counts = self.counts()
        rows.append(" ".join(f"{action}={counts[action]}" for action in sorted(ACTIONS)))
        return "\n".join(rows)


def _same_content(left: Snippet, right: Snippet) -> bool:
    return left.fingerprint() == right.fingerprint()


def plan(
    existing: Iterable[Snippet],
    incoming: Iterable[Snippet],
    *,
    id_strategy: str = CONFLICT,
    slug_strategy: str = RENAME,
    skip_duplicate_content: bool = True,
) -> ImportPlan:
    if id_strategy not in {CONFLICT, SKIP, REPLACE}:
        raise ValueError("id_strategy must be conflict, skip, or replace")
    if slug_strategy not in {CONFLICT, SKIP, RENAME}:
        raise ValueError("slug_strategy must be conflict, skip, or rename")
    existing = list(existing)
    by_id = {snippet.id: snippet for snippet in existing}
    by_slug = {snippet.slug.lower(): snippet for snippet in existing if snippet.slug}
    by_fingerprint = {snippet.fingerprint(): snippet for snippet in existing}
    occupied = [snippet.slug for snippet in existing if snippet.slug]
    items: list[ImportItem] = []

    for original in incoming:
        candidate = Snippet.from_dict(copy.deepcopy(original.to_dict()))
        existing_id = by_id.get(candidate.id)
        existing_slug = by_slug.get(candidate.slug.lower()) if candidate.slug else None
        existing_content = by_fingerprint.get(candidate.fingerprint())

        if existing_id is not None:
            if _same_content(existing_id, candidate):
                action, reason = SKIP, "id and content already exist"
            else:
                action, reason = id_strategy, "id collides with different content"
        elif skip_duplicate_content and existing_content is not None:
            action, reason = SKIP, f"same content already exists as {existing_content.id}"
        elif existing_slug is not None:
            action, reason = slug_strategy, f"slug already belongs to {existing_slug.id}"
        else:
            action, reason = ADD, "new snippet"

        original_slug = candidate.slug
        if action == RENAME:
            candidate.slug = unique_slug(candidate.title, occupied, fallback=candidate.id[:8])
            reason = f"renamed slug from {original_slug!r}"
        if action in {ADD, RENAME, REPLACE} and candidate.slug:
            occupied.append(candidate.slug)
            by_slug[candidate.slug.lower()] = candidate
        if action in {ADD, RENAME}:
            by_id[candidate.id] = candidate
            by_fingerprint[candidate.fingerprint()] = candidate
        items.append(
            ImportItem(
                incoming=candidate,
                action=action,
                existing=existing_id or existing_slug or existing_content,
                reason=reason,
                original_slug=original_slug,
            )
        )
    return ImportPlan(items)


def apply(book, import_plan: ImportPlan, *, save: bool = False) -> dict:
    if import_plan.conflicts:
        identifiers = ", ".join(item.incoming.id for item in import_plan.conflicts)
        raise ValueError(f"import plan has unresolved conflicts: {identifiers}")
    counts = {ADD: 0, SKIP: 0, REPLACE: 0, RENAME: 0}
    for item in import_plan.items:
        if item.action == SKIP:
            counts[SKIP] += 1
            continue
        if item.action == REPLACE:
            if book.replace(item.incoming):
                counts[REPLACE] += 1
            else:
                book.add(item.incoming)
                counts[ADD] += 1
            continue
        book.add(item.incoming)
        counts[item.action] += 1
    if any(counts[action] for action in (ADD, REPLACE, RENAME)) and save:
        book.save()
    return counts
