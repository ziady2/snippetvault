"""Optional audit log.

Off by default. Off because I forgot it existed for the first six
months. When it's on, every mutating operation appends a JSON line
to ``<book_dir>/audit.log``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from .errors import AuditError


@dataclass
class AuditEntry:
    action: str
    target: str = ""
    user: str = ""
    at: float = field(default_factory=lambda: time.time())
    extra: dict = field(default_factory=dict)

    def to_line(self) -> str:
        d: dict = {"action": self.action, "at": self.at}
        if self.target:
            d["target"] = self.target
        if self.user:
            d["user"] = self.user
        if self.extra:
            d["extra"] = self.extra
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_line(cls, line: str) -> Optional["AuditEntry"]:
        line = (line or "").strip()
        if not line:
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        return cls(
            action=str(data.get("action") or ""),
            target=str(data.get("target") or ""),
            user=str(data.get("user") or ""),
            at=float(data.get("at") or 0.0),
            extra=dict(data.get("extra") or {}),
        )


class AuditLog:
    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled

    def record(self, action: str, *, target: str = "", user: str = "", **extra) -> Optional[AuditEntry]:
        if not self.enabled:
            return None
        if not action:
            raise AuditError("audit action is empty")
        entry = AuditEntry(action=action, target=target, user=user, extra=dict(extra))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(entry.to_line() + "\n")
        return entry

    def read(self) -> List[AuditEntry]:
        if not self.path.exists():
            return []
        out: list = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                e = AuditEntry.from_line(line)
                if e is not None:
                    out.append(e)
        return out

    def actions(self) -> List[str]:
        return [e.action for e in self.read()]

    def truncate(self) -> None:
        if self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                # bare try/except because Windows likes to lock files
                pass

    def size_bytes(self) -> int:
        if not self.path.exists():
            return 0
        return self.path.stat().st_size

    def filter_by_action(self, action: str) -> List[AuditEntry]:
        return [e for e in self.read() if e.action == action]

    def filter_since(self, since: float) -> List[AuditEntry]:
        return [e for e in self.read() if e.at >= since]

    def latest(self, n: int = 10) -> List[AuditEntry]:
        return self.read()[-n:]

    def count(self) -> int:
        return len(self.read())


def default_audit_path(book_path: Path) -> Path:
    return Path(book_path).parent / "audit.log"


def is_enabled(book_data: dict) -> bool:
    return bool((book_data.get("metadata") or {}).get("audit_enabled"))


def set_enabled(book_data: dict, enabled: bool) -> None:
    book_data.setdefault("metadata", {})["audit_enabled"] = bool(enabled)


def replay(entries: Iterable[AuditEntry]) -> dict:
    """Build a small summary dict from a list of entries.

    This is what ``snippetbox audit summary`` shows.
    """
    counts: dict = {}
    last_seen: dict = {}
    for e in entries:
        counts[e.action] = counts.get(e.action, 0) + 1
        last_seen[e.action] = max(last_seen.get(e.action, 0.0), e.at)
    return {"counts": counts, "last_seen": last_seen}
