"""Retention plans for old, unused, or superseded snippets."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .snippet import Snippet


ARCHIVE = "archive"
DELETE = "delete"
KEEP = "keep"


@dataclass(frozen=True)
class RetentionPolicy:
    archive_after_days: int = 365
    delete_archived_after_days: int = 730
    minimum_uses_to_keep: int = 1
    keep_favourites: bool = True
    keep_tag_prefixes: tuple[str, ...] = ("keep:",)
    ignore_languages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.archive_after_days < 0 or self.delete_archived_after_days < 0:
            raise ValueError("retention days must not be negative")
        if self.minimum_uses_to_keep < 0:
            raise ValueError("minimum uses must not be negative")
        if self.delete_archived_after_days and self.archive_after_days:
            if self.delete_archived_after_days < self.archive_after_days:
                raise ValueError("delete retention must not be shorter than archive retention")


@dataclass(frozen=True)
class RetentionDecision:
    snippet_id: str
    action: str
    reason: str
    age_days: int


@dataclass
class RetentionPlan:
    decisions: List[RetentionDecision] = field(default_factory=list)

    def for_action(self, action: str) -> List[RetentionDecision]:
        return [decision for decision in self.decisions if decision.action == action]

    def counts(self) -> dict:
        return {
            action: len(self.for_action(action)) for action in (KEEP, ARCHIVE, DELETE)
        }

    def render(self) -> str:
        rows = [
            f"{decision.snippet_id:<16} {decision.action:<8} {decision.age_days:>5}d  {decision.reason}"
            for decision in self.decisions
        ]
        counts = self.counts()
        rows.append(f"keep={counts[KEEP]} archive={counts[ARCHIVE]} delete={counts[DELETE]}")
        return "\n".join(rows)


def decide(snippet: Snippet, policy: RetentionPolicy, *, now: Optional[float] = None) -> RetentionDecision:
    reference = time.time() if now is None else float(now)
    age_days = int(max(0.0, reference - snippet.updated_at) // 86400)
    tags = [tag.lower() for tag in snippet.all_tags()]
    if policy.keep_favourites and snippet.favourite:
        return RetentionDecision(snippet.id, KEEP, "favourite", age_days)
    if any(
        tag.startswith(prefix.lower()) for tag in tags for prefix in policy.keep_tag_prefixes
    ):
        return RetentionDecision(snippet.id, KEEP, "protected tag", age_days)
    if snippet.language.lower() in {language.lower() for language in policy.ignore_languages}:
        return RetentionDecision(snippet.id, KEEP, "ignored language", age_days)
    if snippet.used_count >= policy.minimum_uses_to_keep:
        return RetentionDecision(snippet.id, KEEP, "usage threshold", age_days)
    if snippet.archived and policy.delete_archived_after_days:
        if age_days >= policy.delete_archived_after_days:
            return RetentionDecision(snippet.id, DELETE, "archived beyond retention", age_days)
    if not snippet.archived and policy.archive_after_days:
        if age_days >= policy.archive_after_days:
            return RetentionDecision(snippet.id, ARCHIVE, "inactive beyond archive threshold", age_days)
    return RetentionDecision(snippet.id, KEEP, "inside retention window", age_days)


def plan(
    snippets: Iterable[Snippet],
    policy: Optional[RetentionPolicy] = None,
    *,
    now: Optional[float] = None,
) -> RetentionPlan:
    policy = policy or RetentionPolicy()
    decisions = [decide(snippet, policy, now=now) for snippet in snippets]
    decisions.sort(key=lambda item: (item.action, -item.age_days, item.snippet_id))
    return RetentionPlan(decisions)


def apply(book, retention_plan: RetentionPlan, *, save: bool = False) -> dict:
    archived = 0
    deleted = 0
    for decision in retention_plan.decisions:
        if decision.action == DELETE:
            deleted += int(book.delete(decision.snippet_id))
        elif decision.action == ARCHIVE:
            snippet = book.get(decision.snippet_id)
            if snippet is not None and not snippet.archived:
                snippet.archived = True
                snippet.touch()
                archived += int(book.replace(snippet))
    if (archived or deleted) and save:
        book.save()
    return {"archived": archived, "deleted": deleted}


def policy_to_dict(policy: RetentionPolicy) -> dict:
    return {
        "archive_after_days": policy.archive_after_days,
        "delete_archived_after_days": policy.delete_archived_after_days,
        "minimum_uses_to_keep": policy.minimum_uses_to_keep,
        "keep_favourites": policy.keep_favourites,
        "keep_tag_prefixes": list(policy.keep_tag_prefixes),
        "ignore_languages": list(policy.ignore_languages),
    }


def policy_from_dict(data: dict) -> RetentionPolicy:
    return RetentionPolicy(
        archive_after_days=int(data.get("archive_after_days", 365)),
        delete_archived_after_days=int(data.get("delete_archived_after_days", 730)),
        minimum_uses_to_keep=int(data.get("minimum_uses_to_keep", 1)),
        keep_favourites=bool(data.get("keep_favourites", True)),
        keep_tag_prefixes=tuple(data.get("keep_tag_prefixes") or ("keep:",)),
        ignore_languages=tuple(data.get("ignore_languages") or ()),
    )
