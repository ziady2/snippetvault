"""Composable ranking profiles for snippet search results."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .snippet import Snippet


@dataclass(frozen=True)
class RankingProfile:
    title_weight: float = 4.0
    body_weight: float = 1.0
    tag_weight: float = 2.0
    language_weight: float = 1.0
    favourite_bonus: float = 1.5
    usage_weight: float = 0.35
    recency_weight: float = 1.0
    recency_half_life_days: float = 90.0

    def __post_init__(self) -> None:
        for name in (
            "title_weight",
            "body_weight",
            "tag_weight",
            "language_weight",
            "favourite_bonus",
            "usage_weight",
            "recency_weight",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.recency_half_life_days <= 0:
            raise ValueError("recency_half_life_days must be positive")


@dataclass
class RankedSnippet:
    snippet: Snippet
    score: float
    signals: Dict[str, float] = field(default_factory=dict)

    def explanation(self) -> str:
        details = ", ".join(f"{name}={value:.2f}" for name, value in sorted(self.signals.items()))
        return f"score={self.score:.2f}" + (f" ({details})" if details else "")


def tokenise(text: str) -> list[str]:
    return [part for part in (text or "").lower().split() if part]


def _token_hits(text: str, tokens: Iterable[str]) -> int:
    haystack = (text or "").lower()
    return sum(1 for token in tokens if token in haystack)


def _recency_score(updated_at: float, *, now: float, half_life_days: float) -> float:
    age_days = max(0.0, now - float(updated_at)) / 86400.0
    return math.pow(0.5, age_days / half_life_days)


def score(
    snippet: Snippet,
    query: str,
    *,
    profile: Optional[RankingProfile] = None,
    now: Optional[float] = None,
) -> RankedSnippet:
    profile = profile or RankingProfile()
    reference_time = time.time() if now is None else float(now)
    tokens = tokenise(query)
    signals: dict[str, float] = {}

    title_hits = _token_hits(snippet.title, tokens)
    body_hits = _token_hits(snippet.body, tokens)
    tag_hits = _token_hits(" ".join(snippet.all_tags()), tokens)
    language_hits = _token_hits(snippet.language, tokens)
    if title_hits:
        signals["title"] = title_hits * profile.title_weight
    if body_hits:
        signals["body"] = body_hits * profile.body_weight
    if tag_hits:
        signals["tags"] = tag_hits * profile.tag_weight
    if language_hits:
        signals["language"] = language_hits * profile.language_weight
    if snippet.favourite:
        signals["favourite"] = profile.favourite_bonus
    if snippet.used_count:
        signals["usage"] = math.log1p(snippet.used_count) * profile.usage_weight
    signals["recency"] = _recency_score(
        snippet.updated_at,
        now=reference_time,
        half_life_days=profile.recency_half_life_days,
    ) * profile.recency_weight
    if tokens and not any(key in signals for key in ("title", "body", "tags", "language")):
        total = 0.0
    else:
        total = sum(signals.values())
    return RankedSnippet(snippet=snippet, score=total, signals=signals)


def rank(
    snippets: Iterable[Snippet],
    query: str = "",
    *,
    profile: Optional[RankingProfile] = None,
    now: Optional[float] = None,
    minimum_score: float = 0.0,
    limit: Optional[int] = None,
) -> List[RankedSnippet]:
    ranked = [score(snippet, query, profile=profile, now=now) for snippet in snippets]
    ranked = [item for item in ranked if item.score >= minimum_score]
    ranked.sort(
        key=lambda item: (
            -item.score,
            -item.snippet.updated_at,
            item.snippet.title.lower(),
            item.snippet.id,
        )
    )
    return ranked if limit is None else ranked[: max(0, limit)]


def normalise_scores(items: Iterable[RankedSnippet]) -> List[RankedSnippet]:
    items = list(items)
    maximum = max((item.score for item in items), default=0.0)
    if maximum <= 0:
        return items
    return [
        RankedSnippet(
            snippet=item.snippet,
            score=item.score / maximum,
            signals=dict(item.signals),
        )
        for item in items
    ]


def diversify(items: Iterable[RankedSnippet], *, per_language: int = 3) -> List[RankedSnippet]:
    """Preserve rank order while limiting domination by one language."""
    if per_language < 1:
        return []
    counts: dict[str, int] = {}
    result: list[RankedSnippet] = []
    for item in items:
        language = item.snippet.language or "plain"
        if counts.get(language, 0) >= per_language:
            continue
        counts[language] = counts.get(language, 0) + 1
        result.append(item)
    return result


def profile_from_dict(data: dict) -> RankingProfile:
    allowed = set(RankingProfile.__dataclass_fields__)
    values = {key: float(value) for key, value in (data or {}).items() if key in allowed}
    return RankingProfile(**values)


def profile_to_dict(profile: RankingProfile) -> dict:
    return {name: getattr(profile, name) for name in RankingProfile.__dataclass_fields__}
