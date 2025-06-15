"""Activity timeline assembled from snippet and workflow events."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .snippet import Snippet


@dataclass(frozen=True)
class TimelineEvent:
    kind: str
    at: float
    entity_id: str = ""
    title: str = ""
    actor: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (self.kind or "").strip():
            raise ValueError("timeline event kind is blank")

    @property
    def day(self) -> str:
        return datetime.fromtimestamp(self.at, tz=timezone.utc).date().isoformat()

    @property
    def month(self) -> str:
        value = datetime.fromtimestamp(self.at, tz=timezone.utc)
        return f"{value.year:04d}-{value.month:02d}"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "at": self.at,
            "entity_id": self.entity_id,
            "title": self.title,
            "actor": self.actor,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimelineEvent":
        return cls(
            kind=data.get("kind", ""),
            at=float(data.get("at") or 0),
            entity_id=data.get("entity_id", ""),
            title=data.get("title", ""),
            actor=data.get("actor", ""),
            details=dict(data.get("details") or {}),
        )


def from_snippets(snippets: Iterable[Snippet]) -> List[TimelineEvent]:
    events: list[TimelineEvent] = []
    for snippet in snippets:
        title = snippet.title or snippet.slug or snippet.id
        events.append(
            TimelineEvent(
                kind="snippet_created",
                at=snippet.created_at,
                entity_id=snippet.id,
                title=title,
            )
        )
        if snippet.updated_at > snippet.created_at:
            events.append(
                TimelineEvent(
                    kind="snippet_updated",
                    at=snippet.updated_at,
                    entity_id=snippet.id,
                    title=title,
                )
            )
    return sorted(events, key=lambda event: (event.at, event.kind, event.entity_id))


def merge(*event_groups: Iterable[TimelineEvent]) -> List[TimelineEvent]:
    events = [event for group in event_groups for event in group]
    return sorted(events, key=lambda event: (event.at, event.kind, event.entity_id))


def between(
    events: Iterable[TimelineEvent],
    *,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> List[TimelineEvent]:
    return [
        event
        for event in events
        if (start is None or event.at >= start) and (end is None or event.at < end)
    ]


def filter_events(
    events: Iterable[TimelineEvent],
    *,
    kinds: Iterable[str] = (),
    actor: str = "",
    entity_id: str = "",
) -> List[TimelineEvent]:
    wanted_kinds = set(kinds)
    return [
        event
        for event in events
        if (not wanted_kinds or event.kind in wanted_kinds)
        and (not actor or event.actor.lower() == actor.lower())
        and (not entity_id or event.entity_id == entity_id)
    ]


def group_by_day(events: Iterable[TimelineEvent]) -> Dict[str, List[TimelineEvent]]:
    groups: dict[str, list[TimelineEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda item: item.at):
        groups[event.day].append(event)
    return dict(groups)


def counts_by_kind(events: Iterable[TimelineEvent]) -> Counter:
    return Counter(event.kind for event in events)


def counts_by_month(events: Iterable[TimelineEvent]) -> Counter:
    return Counter(event.month for event in events)


def busiest_days(events: Iterable[TimelineEvent], *, limit: int = 10) -> list[tuple[str, int]]:
    counts = Counter(event.day for event in events)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[: max(0, limit)]


def render_text(events: Iterable[TimelineEvent], *, newest_first: bool = True) -> str:
    ordered = sorted(events, key=lambda event: event.at, reverse=newest_first)
    rows: list[str] = []
    for event in ordered:
        timestamp = datetime.fromtimestamp(event.at, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")
        actor = f" by {event.actor}" if event.actor else ""
        title = event.title or event.entity_id or "(unknown)"
        rows.append(f"{timestamp}  {event.kind:<20}  {title}{actor}")
    return "\n".join(rows)


def to_list(events: Iterable[TimelineEvent]) -> list[dict]:
    return [event.to_dict() for event in sorted(events, key=lambda item: item.at)]


def from_list(data: Iterable[dict]) -> List[TimelineEvent]:
    events: list[TimelineEvent] = []
    for item in data or []:
        try:
            events.append(TimelineEvent.from_dict(item))
        except (TypeError, ValueError):
            continue
    return sorted(events, key=lambda event: event.at)
