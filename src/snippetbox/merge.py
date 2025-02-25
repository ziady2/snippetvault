"""Merge two books.

Given a "base" book and an "incoming" book, return a new book where
incoming snippets have been appended, with conflicts resolved
according to a strategy:

- ``keep-base``: skip incoming snippets that collide with base ids.
- ``prefer-incoming``: replace base entry with incoming.
- ``newer-wins``: take whichever has a higher ``updated_at``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .errors import SnippetboxError
from .snippet import Snippet


STRATEGIES = ("keep-base", "prefer-incoming", "newer-wins")


@dataclass
class MergeReport:
    added: int = 0
    replaced: int = 0
    skipped: int = 0
    conflicts: List[str] = None

    def __post_init__(self) -> None:
        if self.conflicts is None:
            self.conflicts = []

    def total(self) -> int:
        return self.added + self.replaced + self.skipped

    def summary(self) -> str:
        return (
            f"added={self.added} replaced={self.replaced} "
            f"skipped={self.skipped} conflicts={len(self.conflicts)}"
        )


def merge_books(base: dict, incoming: dict, *, strategy: str = "newer-wins") -> Tuple[dict, MergeReport]:
    if strategy not in STRATEGIES:
        raise SnippetboxError(f"unknown merge strategy: {strategy}")
    base_snips: dict = {s.get("id"): s for s in base.get("snippets") or []}
    report = MergeReport()
    out_snips: list = list(base.get("snippets") or [])
    out_index: dict = {s.get("id"): i for i, s in enumerate(out_snips)}

    for raw in incoming.get("snippets") or []:
        sid = raw.get("id")
        if not sid:
            # treat as new even if id is missing
            out_snips.append(raw)
            report.added += 1
            continue
        if sid not in base_snips:
            out_snips.append(raw)
            out_index[sid] = len(out_snips) - 1
            report.added += 1
            continue
        existing = base_snips[sid]
        if strategy == "keep-base":
            report.skipped += 1
            report.conflicts.append(sid)
        elif strategy == "prefer-incoming":
            out_snips[out_index[sid]] = raw
            report.replaced += 1
            report.conflicts.append(sid)
        else:
            # newer-wins
            ours = float(existing.get("updated_at") or 0.0)
            theirs = float(raw.get("updated_at") or 0.0)
            if theirs > ours:
                out_snips[out_index[sid]] = raw
                report.replaced += 1
            else:
                report.skipped += 1
            report.conflicts.append(sid)

    new_book = dict(base)
    new_book["snippets"] = out_snips
    return new_book, report


def diff_book(base: dict, incoming: dict) -> dict:
    base_ids = {s.get("id") for s in base.get("snippets") or []}
    inc_ids = {s.get("id") for s in incoming.get("snippets") or []}
    return {
        "added": sorted(inc_ids - base_ids),
        "removed": sorted(base_ids - inc_ids),
        "common": sorted(base_ids & inc_ids),
    }


def conflicts(base: dict, incoming: dict) -> List[str]:
    base_ids = {s.get("id") for s in base.get("snippets") or []}
    inc_ids = {s.get("id") for s in incoming.get("snippets") or []}
    return sorted(base_ids & inc_ids)


def merge_snippet(base: Snippet, incoming: Snippet, *, strategy: str = "newer-wins") -> Snippet:
    if strategy == "keep-base":
        return base
    if strategy == "prefer-incoming":
        return incoming
    return incoming if incoming.updated_at > base.updated_at else base


def can_merge(base: dict, incoming: dict) -> bool:
    return base.get("schema_version") == incoming.get("schema_version")
