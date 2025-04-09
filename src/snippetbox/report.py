"""Statistical reports about a book.

Used by ``snippetbox report``. None of these produce output you'd
show a manager; they're for the kind of "wait, why do I have so many
SQL snippets?" curiosity questions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List

from .markdown_render import render_table
from .snippet import Snippet


@dataclass
class Report:
    title: str
    rows: List[tuple] = field(default_factory=list)
    headers: tuple = ()

    def to_markdown(self) -> str:
        if not self.rows:
            return f"# {self.title}\n\n_(empty)_\n"
        return f"# {self.title}\n\n" + render_table(self.rows, self.headers) + "\n"

    def to_text(self) -> str:
        if not self.rows:
            return f"{self.title}: (empty)"
        out: list = [self.title, ""]
        if self.headers:
            out.append(" | ".join(self.headers))
            out.append("-" * 40)
        for row in self.rows:
            out.append(" | ".join(str(c) for c in row))
        return "\n".join(out)


def by_language(snippets: Iterable[Snippet]) -> Report:
    counter: Counter = Counter(s.language or "plain" for s in snippets)
    rows = [(lang, count) for lang, count in counter.most_common()]
    return Report(title="Snippets by language", headers=("language", "count"), rows=rows)


def by_tag(snippets: Iterable[Snippet], *, include_auto: bool = True) -> Report:
    counter: Counter = Counter()
    for s in snippets:
        for t in s.tags:
            counter[t] += 1
        if include_auto:
            for t in s.auto_tags:
                counter[t] += 1
    rows = counter.most_common()
    return Report(title="Snippets by tag", headers=("tag", "count"), rows=rows)


def line_counts(snippets: Iterable[Snippet]) -> Report:
    rows: list = []
    for s in snippets:
        rows.append((s.title or s.slug or s.id, s.line_count(), s.char_count()))
    rows.sort(key=lambda r: -r[1])
    return Report(title="Line counts", headers=("snippet", "lines", "chars"), rows=rows[:50])


def usage_top(snippets: Iterable[Snippet], n: int = 10) -> Report:
    sorted_snips = sorted(snippets, key=lambda s: -s.used_count)
    rows = [(s.title or s.slug or s.id, s.used_count) for s in sorted_snips[:n]]
    return Report(title=f"Top {n} most-used", headers=("snippet", "used_count"), rows=rows)


def stale(snippets: Iterable[Snippet], *, days: int = 365) -> Report:
    import time as _t

    cutoff = _t.time() - days * 86400
    rows: list = []
    for s in snippets:
        if s.updated_at < cutoff:
            rows.append((s.title or s.slug or s.id, int(_t.time() - s.updated_at) // 86400))
    rows.sort(key=lambda r: -r[1])
    return Report(title=f"Snippets not touched in {days}+ days", headers=("snippet", "days"), rows=rows)


def coverage(snippets: Iterable[Snippet]) -> Report:
    """Where does each language stand re: tagged-vs-untagged."""
    counters: dict = {}
    for s in snippets:
        bucket = counters.setdefault(s.language or "plain", [0, 0])
        bucket[0] += 1
        if s.tags or s.auto_tags:
            bucket[1] += 1
    rows: list = []
    for lang, (total, tagged) in counters.items():
        pct = (tagged / total * 100) if total else 0.0
        rows.append((lang, total, tagged, f"{pct:.0f}%"))
    rows.sort(key=lambda r: -r[1])
    return Report(
        title="Tag coverage by language",
        headers=("language", "snippets", "tagged", "%"),
        rows=rows,
    )


def empty_tags(snippets: Iterable[Snippet]) -> Report:
    rows: list = []
    for s in snippets:
        if not (s.tags or s.auto_tags):
            rows.append((s.id, s.title or s.slug or "(untitled)", s.language))
    return Report(title="Snippets with no tags", headers=("id", "title", "language"), rows=rows)


def overview(snippets: Iterable[Snippet]) -> dict:
    snippets = list(snippets)
    return {
        "total": len(snippets),
        "languages": len({s.language for s in snippets}),
        "tagged": sum(1 for s in snippets if s.tags or s.auto_tags),
        "favourites": sum(1 for s in snippets if s.favourite),
        "archived": sum(1 for s in snippets if s.archived),
        "total_chars": sum(s.char_count() for s in snippets),
        "total_lines": sum(s.line_count() for s in snippets),
    }


def histogram_languages(snippets: Iterable[Snippet], *, width: int = 30) -> str:
    counter: Counter = Counter(s.language or "plain" for s in snippets)
    if not counter:
        return ""
    top = counter.most_common()
    biggest = top[0][1]
    out: list = []
    for lang, count in top:
        bar = "#" * max(1, int(width * count / biggest))
        out.append(f"{lang:<14} {bar} {count}")
    return "\n".join(out)
