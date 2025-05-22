"""Derived statistics for larger snippet libraries."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, median
from typing import Dict, Iterable, List

from .snippet import Snippet


@dataclass(frozen=True)
class Distribution:
    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    p90: float

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "median": self.median,
            "p90": self.p90,
        }


def distribution(values: Iterable[float]) -> Distribution:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return Distribution(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    p90_index = max(0, math.ceil(len(ordered) * 0.9) - 1)
    return Distribution(
        count=len(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=mean(ordered),
        median=median(ordered),
        p90=ordered[p90_index],
    )


@dataclass
class LibraryStats:
    snippet_count: int
    active_count: int
    favourite_count: int
    language_counts: Dict[str, int] = field(default_factory=dict)
    tag_counts: Dict[str, int] = field(default_factory=dict)
    body_characters: Distribution = field(default_factory=lambda: distribution([]))
    body_lines: Distribution = field(default_factory=lambda: distribution([]))
    usage_counts: Distribution = field(default_factory=lambda: distribution([]))
    tag_counts_per_snippet: Distribution = field(default_factory=lambda: distribution([]))

    def to_dict(self) -> dict:
        return {
            "snippet_count": self.snippet_count,
            "active_count": self.active_count,
            "archived_count": self.snippet_count - self.active_count,
            "favourite_count": self.favourite_count,
            "language_counts": dict(self.language_counts),
            "tag_counts": dict(self.tag_counts),
            "body_characters": self.body_characters.to_dict(),
            "body_lines": self.body_lines.to_dict(),
            "usage_counts": self.usage_counts.to_dict(),
            "tag_counts_per_snippet": self.tag_counts_per_snippet.to_dict(),
        }


def compute(snippets: Iterable[Snippet]) -> LibraryStats:
    snippets = list(snippets)
    languages = Counter((snippet.language or "plain").lower() for snippet in snippets)
    tags = Counter(tag.lower() for snippet in snippets for tag in snippet.all_tags())
    return LibraryStats(
        snippet_count=len(snippets),
        active_count=sum(not snippet.archived for snippet in snippets),
        favourite_count=sum(snippet.favourite for snippet in snippets),
        language_counts=dict(languages.most_common()),
        tag_counts=dict(tags.most_common()),
        body_characters=distribution(len(snippet.body) for snippet in snippets),
        body_lines=distribution(snippet.line_count() for snippet in snippets),
        usage_counts=distribution(snippet.used_count for snippet in snippets),
        tag_counts_per_snippet=distribution(len(snippet.all_tags()) for snippet in snippets),
    )


def created_by_month(snippets: Iterable[Snippet]) -> Dict[str, int]:
    counts: Counter = Counter()
    for snippet in snippets:
        value = datetime.fromtimestamp(snippet.created_at, tz=timezone.utc)
        counts[f"{value.year:04d}-{value.month:02d}"] += 1
    return dict(sorted(counts.items()))


def updated_by_month(snippets: Iterable[Snippet]) -> Dict[str, int]:
    counts: Counter = Counter()
    for snippet in snippets:
        value = datetime.fromtimestamp(snippet.updated_at, tz=timezone.utc)
        counts[f"{value.year:04d}-{value.month:02d}"] += 1
    return dict(sorted(counts.items()))


def language_tag_matrix(snippets: Iterable[Snippet]) -> Dict[str, Dict[str, int]]:
    matrix: dict[str, Counter] = defaultdict(Counter)
    for snippet in snippets:
        language = (snippet.language or "plain").lower()
        for tag in snippet.all_tags():
            matrix[language][tag.lower()] += 1
    return {
        language: dict(counter.most_common()) for language, counter in sorted(matrix.items())
    }


def cooccurring_tags(snippets: Iterable[Snippet], *, minimum: int = 2) -> List[tuple[str, str, int]]:
    counts: Counter = Counter()
    for snippet in snippets:
        tags = sorted(set(tag.lower() for tag in snippet.all_tags()))
        for index, left in enumerate(tags):
            for right in tags[index + 1 :]:
                counts[(left, right)] += 1
    rows = [(left, right, count) for (left, right), count in counts.items() if count >= minimum]
    return sorted(rows, key=lambda row: (-row[2], row[0], row[1]))


def orphan_tags(snippets: Iterable[Snippet], *, maximum_uses: int = 1) -> List[str]:
    counts = Counter(tag.lower() for snippet in snippets for tag in snippet.all_tags())
    return sorted(tag for tag, count in counts.items() if count <= maximum_uses)


def language_share(snippets: Iterable[Snippet]) -> Dict[str, float]:
    counts = Counter((snippet.language or "plain").lower() for snippet in snippets)
    total = sum(counts.values())
    if not total:
        return {}
    return {language: count / total for language, count in counts.most_common()}


def concentration(snippets: Iterable[Snippet]) -> float:
    """Herfindahl index for language concentration (0 diverse, 1 uniform)."""
    return sum(share * share for share in language_share(snippets).values())


def freshness(snippets: Iterable[Snippet], *, now: float, half_life_days: float = 180.0) -> float:
    snippets = list(snippets)
    if not snippets:
        return 0.0
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    scores: list[float] = []
    for snippet in snippets:
        age_days = max(0.0, now - snippet.updated_at) / 86400
        scores.append(math.pow(0.5, age_days / half_life_days))
    return mean(scores)


def growth_rate(monthly: Dict[str, int], *, periods: int = 3) -> float:
    """Average month-over-month growth over the newest periods."""
    if periods < 1:
        raise ValueError("periods must be positive")
    values = [count for _, count in sorted(monthly.items())]
    if len(values) < 2:
        return 0.0
    values = values[-(periods + 1) :]
    rates: list[float] = []
    for previous, current in zip(values, values[1:]):
        if previous == 0:
            rates.append(1.0 if current else 0.0)
        else:
            rates.append((current - previous) / previous)
    return mean(rates) if rates else 0.0


def top_snippets(snippets: Iterable[Snippet], *, limit: int = 10) -> List[Snippet]:
    return sorted(
        snippets,
        key=lambda snippet: (-snippet.used_count, -int(snippet.favourite), -snippet.updated_at, snippet.id),
    )[: max(0, limit)]


def render_summary(library_stats: LibraryStats) -> str:
    rows = [
        f"snippets: {library_stats.snippet_count}",
        f"active: {library_stats.active_count}",
        f"favourites: {library_stats.favourite_count}",
        f"languages: {len(library_stats.language_counts)}",
        f"tags: {len(library_stats.tag_counts)}",
        f"median lines: {library_stats.body_lines.median:.1f}",
        f"median uses: {library_stats.usage_counts.median:.1f}",
    ]
    return "\n".join(rows)
