"""Explainable quality scoring for individual snippets and libraries."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Iterable, List, Optional

from .sharing import scan as scan_sensitive
from .snippet import Snippet


DIMENSIONS = ("completeness", "readability", "discoverability", "freshness", "safety")


@dataclass(frozen=True)
class QualitySignal:
    dimension: str
    code: str
    points: float
    maximum: float
    message: str

    def __post_init__(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"unknown quality dimension: {self.dimension}")
        if self.maximum <= 0:
            raise ValueError("quality signal maximum must be positive")
        if not 0 <= self.points <= self.maximum:
            raise ValueError("quality signal points must be within its maximum")

    @property
    def ratio(self) -> float:
        return self.points / self.maximum


@dataclass
class QualityScore:
    snippet_id: str
    signals: List[QualitySignal] = field(default_factory=list)

    @property
    def score(self) -> float:
        maximum = sum(signal.maximum for signal in self.signals)
        return (sum(signal.points for signal in self.signals) / maximum * 100) if maximum else 0.0

    @property
    def grade(self) -> str:
        value = self.score
        if value >= 90:
            return "A"
        if value >= 80:
            return "B"
        if value >= 70:
            return "C"
        if value >= 60:
            return "D"
        return "F"

    def dimension_scores(self) -> Dict[str, float]:
        result: dict[str, float] = {}
        for dimension in DIMENSIONS:
            signals = [signal for signal in self.signals if signal.dimension == dimension]
            maximum = sum(signal.maximum for signal in signals)
            result[dimension] = (
                sum(signal.points for signal in signals) / maximum * 100 if maximum else 0.0
            )
        return result

    def suggestions(self) -> List[str]:
        return [
            signal.message
            for signal in sorted(self.signals, key=lambda item: (item.ratio, item.dimension, item.code))
            if signal.ratio < 1.0
        ]

    def to_dict(self) -> dict:
        return {
            "snippet_id": self.snippet_id,
            "score": round(self.score, 2),
            "grade": self.grade,
            "dimensions": {key: round(value, 2) for key, value in self.dimension_scores().items()},
            "signals": [
                {
                    "dimension": signal.dimension,
                    "code": signal.code,
                    "points": signal.points,
                    "maximum": signal.maximum,
                    "message": signal.message,
                }
                for signal in self.signals
            ],
        }


@dataclass(frozen=True)
class QualityProfile:
    minimum_title_length: int = 4
    maximum_title_length: int = 100
    minimum_body_length: int = 10
    preferred_maximum_lines: int = 200
    stale_after_days: int = 365
    require_tags: bool = True
    require_language: bool = True
    penalise_sensitive_content: bool = True

    def __post_init__(self) -> None:
        if self.minimum_title_length < 0 or self.maximum_title_length < self.minimum_title_length:
            raise ValueError("invalid title limits")
        if self.minimum_body_length < 0:
            raise ValueError("minimum body length must not be negative")
        if self.preferred_maximum_lines < 1:
            raise ValueError("preferred maximum lines must be positive")
        if self.stale_after_days < 1:
            raise ValueError("stale_after_days must be positive")


def _signal(dimension: str, code: str, passed: bool, maximum: float, message: str) -> QualitySignal:
    return QualitySignal(dimension, code, maximum if passed else 0.0, maximum, message)


def score_snippet(
    snippet: Snippet,
    *,
    profile: Optional[QualityProfile] = None,
    now: Optional[float] = None,
) -> QualityScore:
    profile = profile or QualityProfile()
    reference = time.time() if now is None else float(now)
    title_length = len(snippet.title.strip())
    body_length = len(snippet.body.strip())
    line_count = snippet.line_count()
    tags = snippet.all_tags()
    signals: list[QualitySignal] = []

    signals.append(
        _signal(
            "completeness",
            "has_title",
            title_length >= profile.minimum_title_length,
            10,
            f"use a title with at least {profile.minimum_title_length} characters",
        )
    )
    signals.append(
        _signal(
            "completeness",
            "has_body",
            body_length >= profile.minimum_body_length,
            15,
            f"include at least {profile.minimum_body_length} characters of snippet content",
        )
    )
    signals.append(
        _signal(
            "completeness",
            "known_language",
            bool(snippet.language.strip()) if profile.require_language else True,
            5,
            "set a language instead of leaving it blank",
        )
    )
    signals.append(
        _signal(
            "readability",
            "concise_title",
            title_length <= profile.maximum_title_length,
            8,
            f"keep the title under {profile.maximum_title_length} characters",
        )
    )
    signals.append(
        _signal(
            "readability",
            "bounded_body",
            line_count <= profile.preferred_maximum_lines,
            7,
            f"split snippets longer than {profile.preferred_maximum_lines} lines",
        )
    )
    has_tabs_and_spaces = bool(re.search(r"(?m)^(?:\t+ +| +\t+)", snippet.body))
    signals.append(
        _signal(
            "readability",
            "consistent_indentation",
            not has_tabs_and_spaces,
            5,
            "avoid mixing tabs and spaces at the start of a line",
        )
    )
    signals.append(
        _signal(
            "discoverability",
            "has_tags",
            bool(tags) if profile.require_tags else True,
            10,
            "add at least one searchable tag",
        )
    )
    signals.append(
        _signal(
            "discoverability",
            "has_slug",
            bool(snippet.slug.strip()),
            5,
            "assign a stable slug",
        )
    )
    searchable_context = bool(snippet.notes.strip() or snippet.source.strip() or len(tags) >= 2)
    signals.append(
        _signal(
            "discoverability",
            "has_context",
            searchable_context,
            5,
            "add notes, a source, or a second tag to explain when the snippet is useful",
        )
    )

    age_days = max(0.0, reference - snippet.updated_at) / 86400
    freshness_ratio = math.pow(0.5, age_days / profile.stale_after_days)
    signals.append(
        QualitySignal(
            "freshness",
            "recently_updated",
            points=10 * freshness_ratio,
            maximum=10,
            message=f"review snippets that have not changed in {profile.stale_after_days} days",
        )
    )
    signals.append(
        _signal(
            "freshness",
            "used",
            snippet.used_count > 0,
            5,
            "mark the snippet as used after verifying it still works",
        )
    )

    sensitive_findings = scan_sensitive(snippet) if profile.penalise_sensitive_content else []
    signals.append(
        _signal(
            "safety",
            "no_sensitive_fields",
            not sensitive_findings,
            15,
            "remove credentials, personal data, or private metadata before sharing",
        )
    )
    return QualityScore(snippet_id=snippet.id, signals=signals)


@dataclass
class LibraryQuality:
    scores: List[QualityScore] = field(default_factory=list)

    @property
    def average(self) -> float:
        return mean(score.score for score in self.scores) if self.scores else 0.0

    @property
    def minimum(self) -> float:
        return min((score.score for score in self.scores), default=0.0)

    def grade_counts(self) -> Dict[str, int]:
        counts = {grade: 0 for grade in "ABCDF"}
        for score in self.scores:
            counts[score.grade] += 1
        return counts

    def below(self, threshold: float) -> List[QualityScore]:
        return sorted(
            (score for score in self.scores if score.score < threshold),
            key=lambda item: (item.score, item.snippet_id),
        )

    def dimension_averages(self) -> Dict[str, float]:
        if not self.scores:
            return {dimension: 0.0 for dimension in DIMENSIONS}
        return {
            dimension: mean(score.dimension_scores()[dimension] for score in self.scores)
            for dimension in DIMENSIONS
        }

    def to_dict(self) -> dict:
        return {
            "average": round(self.average, 2),
            "minimum": round(self.minimum, 2),
            "grade_counts": self.grade_counts(),
            "dimension_averages": {
                key: round(value, 2) for key, value in self.dimension_averages().items()
            },
            "scores": [score.to_dict() for score in self.scores],
        }


def score_library(
    snippets: Iterable[Snippet],
    *,
    profile: Optional[QualityProfile] = None,
    now: Optional[float] = None,
) -> LibraryQuality:
    scores = [score_snippet(snippet, profile=profile, now=now) for snippet in snippets]
    scores.sort(key=lambda item: item.snippet_id)
    return LibraryQuality(scores)


def render(score: QualityScore) -> str:
    rows = [f"{score.snippet_id}: {score.score:.1f}/100 ({score.grade})"]
    dimensions = score.dimension_scores()
    for dimension in DIMENSIONS:
        rows.append(f"  {dimension:<16} {dimensions[dimension]:5.1f}")
    suggestions = score.suggestions()
    if suggestions:
        rows.append("  suggestions:")
        rows.extend(f"    - {suggestion}" for suggestion in suggestions)
    return "\n".join(rows)
