"""Higher-level workflows that combine modules.

These are the "I do this every Tuesday" jobs that don't fit one
module. Each function takes a ``Book`` and does the thing.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Optional

from . import dedup, lint, report, search, tagger, usage
from .snippet import Snippet
from .storage import Book


def auto_tag_all(book: Book, *, max_tags: int = 6) -> int:
    """Run the auto-tagger over every snippet, save results into the book."""
    snippets = list(book)
    changed = 0
    for s in snippets:
        before = list(s.auto_tags)
        tagger.apply_to(s, max_tags=max_tags)
        if before != s.auto_tags:
            book.replace(s)
            changed += 1
    return changed


def dedup_all(book: Book, *, drop_comments: bool = False, dry_run: bool = False) -> int:
    """Find duplicates; if not dry-run, merge them and remove the secondaries."""
    snippets = list(book)
    clusters = dedup.find_duplicates(snippets, drop_comments=drop_comments)
    if dry_run:
        return dedup.total_duplicates(clusters)
    removed = 0
    for c in clusters:
        primary = c.primary()
        for other in c.others():
            dedup.merge_pair(primary, other)
            book.delete(other.id)
            removed += 1
        book.replace(primary)
    return removed


def archive_stale(book: Book, *, days: int = 365) -> int:
    snippets = list(book)
    archived = 0
    for s in usage.stale_snippets(snippets, usage.usage_log(book.data), days=days):
        if s.archived:
            continue
        s.archived = True
        s.touch()
        book.replace(s)
        archived += 1
    return archived


def unarchive_all(book: Book) -> int:
    n = 0
    for s in book:
        if s.archived:
            s.archived = False
            s.touch()
            book.replace(s)
            n += 1
    return n


def summarise(book: Book) -> dict:
    snippets = list(book)
    overview = report.overview(snippets)
    overview["lint_issues"] = len(lint.lint_book(book.data))
    overview["dup_clusters"] = len(dedup.find_duplicates(snippets))
    return overview


def search_and_mark(
    book: Book,
    query: str,
    *,
    favourite: Optional[bool] = None,
    add_tags: Optional[List[str]] = None,
    mode: str = "token",
) -> int:
    add_tags = list(add_tags or [])
    hits = search.search(snippets=list(book), query=query, mode=mode)
    n = 0
    for h in hits:
        s = h.snippet
        changed = False
        if favourite is not None and s.favourite != favourite:
            s.favourite = favourite
            changed = True
        for t in add_tags:
            if t and t not in s.tags:
                s.tags.append(t)
                changed = True
        if changed:
            s.touch()
            book.replace(s)
            n += 1
    return n


def language_breakdown(book: Book) -> Counter:
    return Counter(s.language or "plain" for s in book)


def export_collection(book: Book, name: str) -> List[Snippet]:
    coll = book.get_collection(name)
    if coll is None:
        return []
    out: list = []
    for sid in coll.snippet_ids:
        s = book.get(sid)
        if s is not None:
            out.append(s)
    return out


def merge_collections(book: Book, into: str, sources: Iterable[str]) -> int:
    target = book.get_collection(into)
    if target is None:
        return 0
    added = 0
    for source_name in sources:
        source = book.get_collection(source_name)
        if source is None:
            continue
        for sid in source.snippet_ids:
            if target.add(sid):
                added += 1
    book.upsert_collection(target)
    return added


def healthcheck(book: Book) -> dict:
    """Quick "is anything obviously wrong?" check."""
    snips = list(book)
    return {
        "snippets": len(snips),
        "linted": lint.count_by_code(lint.lint_book(book.data)),
        "duplicates": dedup.total_duplicates(dedup.find_duplicates(snips)),
        "favourites": sum(1 for s in snips if s.favourite),
    }
