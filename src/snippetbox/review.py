"""Review workflow for keeping a snippet library trustworthy."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


PENDING = "pending"
IN_REVIEW = "in_review"
APPROVED = "approved"
CHANGES_REQUESTED = "changes_requested"
REJECTED = "rejected"
STATUSES = {PENDING, IN_REVIEW, APPROVED, CHANGES_REQUESTED, REJECTED}

_TRANSITIONS = {
    PENDING: {IN_REVIEW, APPROVED, REJECTED},
    IN_REVIEW: {APPROVED, CHANGES_REQUESTED, REJECTED, PENDING},
    CHANGES_REQUESTED: {IN_REVIEW, APPROVED, REJECTED},
    APPROVED: {IN_REVIEW},
    REJECTED: {IN_REVIEW},
}


@dataclass(frozen=True)
class ReviewEvent:
    from_status: str
    to_status: str
    at: float
    reviewer: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "from": self.from_status,
            "to": self.to_status,
            "at": self.at,
            "reviewer": self.reviewer,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewEvent":
        return cls(
            from_status=data.get("from", PENDING),
            to_status=data.get("to", PENDING),
            at=float(data.get("at") or 0),
            reviewer=data.get("reviewer", ""),
            note=data.get("note", ""),
        )


@dataclass
class ReviewRecord:
    snippet_id: str
    status: str = PENDING
    requested_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    assignee: str = ""
    priority: int = 0
    labels: List[str] = field(default_factory=list)
    events: List[ReviewEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.snippet_id = (self.snippet_id or "").strip()
        if not self.snippet_id:
            raise ValueError("review snippet_id is blank")
        if self.status not in STATUSES:
            raise ValueError(f"unknown review status: {self.status}")
        self.priority = int(self.priority)
        if not 0 <= self.priority <= 5:
            raise ValueError("review priority must be between 0 and 5")
        self.labels = list(dict.fromkeys(label.strip().lower() for label in self.labels if label.strip()))
        self.events = list(self.events)

    def can_transition(self, status: str) -> bool:
        return status in _TRANSITIONS.get(self.status, set())

    def transition(
        self,
        status: str,
        *,
        reviewer: str = "",
        note: str = "",
        at: Optional[float] = None,
    ) -> ReviewEvent:
        if status not in STATUSES:
            raise ValueError(f"unknown review status: {status}")
        if not self.can_transition(status):
            raise ValueError(f"cannot transition review from {self.status} to {status}")
        timestamp = time.time() if at is None else float(at)
        event = ReviewEvent(
            from_status=self.status,
            to_status=status,
            at=timestamp,
            reviewer=(reviewer or "").strip(),
            note=(note or "").strip(),
        )
        self.status = status
        self.updated_at = timestamp
        self.events.append(event)
        return event

    def age_seconds(self, *, now: Optional[float] = None) -> float:
        reference = time.time() if now is None else float(now)
        return max(0.0, reference - self.requested_at)

    def to_dict(self) -> dict:
        return {
            "snippet_id": self.snippet_id,
            "status": self.status,
            "requested_at": self.requested_at,
            "updated_at": self.updated_at,
            "assignee": self.assignee,
            "priority": self.priority,
            "labels": list(self.labels),
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewRecord":
        return cls(
            snippet_id=data.get("snippet_id", ""),
            status=data.get("status", PENDING),
            requested_at=float(data.get("requested_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            assignee=data.get("assignee", ""),
            priority=int(data.get("priority") or 0),
            labels=list(data.get("labels") or []),
            events=[ReviewEvent.from_dict(item) for item in data.get("events") or []],
        )


class ReviewQueue:
    def __init__(self, records: Iterable[ReviewRecord] = ()) -> None:
        self._records: Dict[str, ReviewRecord] = {}
        for record in records:
            self._records[record.snippet_id] = record

    def request(
        self,
        snippet_id: str,
        *,
        assignee: str = "",
        priority: int = 0,
        labels: Iterable[str] = (),
        replace: bool = False,
    ) -> ReviewRecord:
        if snippet_id in self._records and not replace:
            return self._records[snippet_id]
        record = ReviewRecord(
            snippet_id=snippet_id,
            assignee=(assignee or "").strip(),
            priority=priority,
            labels=list(labels),
        )
        self._records[snippet_id] = record
        return record

    def get(self, snippet_id: str) -> Optional[ReviewRecord]:
        return self._records.get(snippet_id)

    def remove(self, snippet_id: str) -> bool:
        return self._records.pop(snippet_id, None) is not None

    def list(
        self,
        *,
        statuses: Iterable[str] = (),
        assignee: str = "",
        labels: Iterable[str] = (),
    ) -> List[ReviewRecord]:
        wanted_statuses = set(statuses)
        wanted_labels = {label.lower() for label in labels}
        result: list[ReviewRecord] = []
        for record in self._records.values():
            if wanted_statuses and record.status not in wanted_statuses:
                continue
            if assignee and record.assignee.lower() != assignee.lower():
                continue
            if wanted_labels and not wanted_labels.issubset(set(record.labels)):
                continue
            result.append(record)
        result.sort(key=lambda item: (-item.priority, item.requested_at, item.snippet_id))
        return result

    def stale(self, *, older_than_seconds: float, now: Optional[float] = None) -> List[ReviewRecord]:
        reference = time.time() if now is None else float(now)
        return [
            record
            for record in self.list(statuses={PENDING, IN_REVIEW, CHANGES_REQUESTED})
            if reference - record.updated_at >= older_than_seconds
        ]

    def counts(self) -> dict:
        counts = {status: 0 for status in sorted(STATUSES)}
        for record in self._records.values():
            counts[record.status] += 1
        return counts

    def to_list(self) -> list[dict]:
        return [record.to_dict() for record in self.list()]

    @classmethod
    def from_list(cls, data: Iterable[dict]) -> "ReviewQueue":
        records: list[ReviewRecord] = []
        for item in data or []:
            try:
                records.append(ReviewRecord.from_dict(item))
            except (TypeError, ValueError):
                continue
        return cls(records)


def queue_for_book(book) -> ReviewQueue:
    metadata = book.data.setdefault("metadata", {})
    return ReviewQueue.from_list(metadata.get("reviews") or [])


def save_queue(book, queue: ReviewQueue) -> None:
    book.data.setdefault("metadata", {})["reviews"] = queue.to_list()
