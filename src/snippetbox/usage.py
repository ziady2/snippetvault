"""Track which snippets get used.

Each call to ``mark_used`` increments a counter on the snippet and
writes a stub event into a usage log inside the book metadata. The
log is bounded; we keep the last ``MAX_EVENTS`` events.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .snippet import Snippet


MAX_EVENTS = 500


@dataclass
class UsageEvent:
    snippet_id: str
    at: float = field(default_factory=lambda: time.time())
    note: str = ""

    def to_dict(self) -> dict:
        d: dict = {"id": self.snippet_id, "at": self.at}
        if self.note:
            d["note"] = self.note
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "UsageEvent":
        return cls(
            snippet_id=data.get("id", ""),
            at=float(data.get("at") or 0.0),
            note=data.get("note", "") or "",
        )


def record_use(book_data: dict, snippet_id: str, *, note: str = "") -> UsageEvent:
    if "metadata" not in book_data:
        book_data["metadata"] = {}
    log = book_data["metadata"].setdefault("usage_log", [])
    event = UsageEvent(snippet_id=snippet_id, note=note)
    log.append(event.to_dict())
    if len(log) > MAX_EVENTS:
        del log[: len(log) - MAX_EVENTS]
    return event


def usage_log(book_data: dict) -> List[UsageEvent]:
    raw = (book_data.get("metadata") or {}).get("usage_log") or []
    return [UsageEvent.from_dict(e) for e in raw]


def usage_counts(events: Iterable[UsageEvent]) -> Counter:
    return Counter(e.snippet_id for e in events if e.snippet_id)


def top_used(events: Iterable[UsageEvent], n: int = 10) -> List[tuple]:
    return usage_counts(events).most_common(n)


def usage_for(events: Iterable[UsageEvent], snippet_id: str) -> int:
    return usage_counts(events).get(snippet_id, 0)


def latest_use(events: Iterable[UsageEvent], snippet_id: str) -> Optional[float]:
    times = [e.at for e in events if e.snippet_id == snippet_id]
    if not times:
        return None
    return max(times)


def first_use(events: Iterable[UsageEvent], snippet_id: str) -> Optional[float]:
    times = [e.at for e in events if e.snippet_id == snippet_id]
    if not times:
        return None
    return min(times)


def trim_log(book_data: dict, *, keep: int = MAX_EVENTS) -> int:
    log = (book_data.get("metadata") or {}).get("usage_log") or []
    if len(log) <= keep:
        return 0
    removed = len(log) - keep
    del log[:removed]
    return removed


def reset(book_data: dict) -> None:
    if "metadata" in book_data:
        book_data["metadata"]["usage_log"] = []


def stale_snippets(snippets: Iterable[Snippet], events: Iterable[UsageEvent], *, days: int = 180) -> List[Snippet]:
    """Snippets not used in the last N days."""
    cutoff = time.time() - days * 86400
    used: dict = {}
    for e in events:
        used[e.snippet_id] = max(used.get(e.snippet_id, 0.0), e.at)
    out: list = []
    for s in snippets:
        last = used.get(s.id) or s.updated_at
        if last < cutoff:
            out.append(s)
    return out


def export_log_csv(events: Iterable[UsageEvent]) -> str:
    out: list = ["id,at,note"]
    for e in events:
        note = (e.note or "").replace(",", " ").replace("\n", " ")
        out.append(f"{e.snippet_id},{e.at:.0f},{note}")
    return "\n".join(out)


def import_log_csv(text: str) -> List[UsageEvent]:
    lines = (text or "").strip().splitlines()
    if not lines:
        return []
    head = lines[0].lower().split(",")
    if "id" not in head:
        return []
    out: list = []
    for line in lines[1:]:
        parts = line.split(",", 2)
        if len(parts) < 2:
            continue
        try:
            at = float(parts[1])
        except ValueError:
            continue
        note = parts[2] if len(parts) > 2 else ""
        out.append(UsageEvent(snippet_id=parts[0], at=at, note=note))
    return out
