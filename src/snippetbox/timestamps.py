"""Timestamp parsing and deterministic time-window helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


UTC = timezone.utc
_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdw])$", re.IGNORECASE)
_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def ensure_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(float(value), tz=UTC)


def to_timestamp(value: datetime) -> float:
    return ensure_utc(value).timestamp()


def format_iso(value: datetime, *, timespec: str = "seconds") -> str:
    """Format a UTC timestamp using ``Z`` instead of ``+00:00``."""
    text = ensure_utc(value).isoformat(timespec=timespec)
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def parse_iso(text: str) -> datetime:
    """Parse an ISO-8601 timestamp, date, or ``Z``-suffixed value."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("timestamp is blank")
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {text!r}") from exc
    return ensure_utc(value)


def parse_duration(text: str) -> timedelta:
    """Parse compact durations such as ``30m``, ``12h`` and ``7d``."""
    match = _DURATION_RE.fullmatch((text or "").strip())
    if not match:
        raise ValueError(f"invalid duration: {text!r}")
    seconds = int(match.group("value")) * _UNIT_SECONDS[match.group("unit").lower()]
    return timedelta(seconds=seconds)


def format_duration(value: timedelta) -> str:
    """Format a duration using the largest exact compact unit."""
    seconds = int(value.total_seconds())
    if seconds < 0:
        raise ValueError("duration must not be negative")
    for suffix, unit in (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % unit == 0:
            return f"{seconds // unit}{suffix}"
    return f"{seconds}s"


@dataclass(frozen=True)
class TimeWindow:
    """An inclusive start, exclusive end interval."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start = ensure_utc(self.start)
        end = ensure_utc(self.end)
        if end < start:
            raise ValueError("window end precedes start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    @classmethod
    def ending_at(cls, end: datetime, duration: timedelta) -> "TimeWindow":
        if duration.total_seconds() < 0:
            raise ValueError("duration must not be negative")
        end = ensure_utc(end)
        return cls(start=end - duration, end=end)

    def contains(self, value: datetime) -> bool:
        value = ensure_utc(value)
        return self.start <= value < self.end

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: "TimeWindow") -> Optional["TimeWindow"]:
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        if end <= start:
            return None
        return TimeWindow(start, end)

    def duration(self) -> timedelta:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"start": format_iso(self.start), "end": format_iso(self.end)}

    @classmethod
    def from_dict(cls, data: dict) -> "TimeWindow":
        return cls(parse_iso(data["start"]), parse_iso(data["end"]))


def newest(values: Iterable[datetime]) -> Optional[datetime]:
    prepared = [ensure_utc(value) for value in values]
    return max(prepared) if prepared else None


def oldest(values: Iterable[datetime]) -> Optional[datetime]:
    prepared = [ensure_utc(value) for value in values]
    return min(prepared) if prepared else None


def age_seconds(timestamp: float, *, now: Optional[datetime] = None) -> float:
    reference = ensure_utc(now) if now is not None else utc_now()
    return max(0.0, (reference - from_timestamp(timestamp)).total_seconds())


def bucket_day(timestamp: float) -> str:
    return from_timestamp(timestamp).date().isoformat()


def bucket_month(timestamp: float) -> str:
    value = from_timestamp(timestamp)
    return f"{value.year:04d}-{value.month:02d}"
