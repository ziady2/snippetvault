"""Three-way sync planning for two independently edited snippet books."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .snapshot import checksum
from .snippet import Snippet


UNCHANGED = "unchanged"
ADD_LOCAL = "add_local"
ADD_REMOTE = "add_remote"
TAKE_LOCAL = "take_local"
TAKE_REMOTE = "take_remote"
DELETE_LOCAL = "delete_local"
DELETE_REMOTE = "delete_remote"
CONFLICT = "conflict"


def _digest(snippet: Optional[Snippet]) -> str:
    return checksum(snippet.to_dict()) if snippet is not None else ""


@dataclass
class SyncItem:
    snippet_id: str
    action: str
    base: Optional[Snippet] = None
    local: Optional[Snippet] = None
    remote: Optional[Snippet] = None
    reason: str = ""

    @property
    def conflict(self) -> bool:
        return self.action == CONFLICT

    def chosen(self) -> Optional[Snippet]:
        if self.action in {ADD_LOCAL, TAKE_LOCAL, DELETE_REMOTE}:
            return self.local
        if self.action in {ADD_REMOTE, TAKE_REMOTE, DELETE_LOCAL}:
            return self.remote
        if self.action == UNCHANGED:
            return self.local or self.remote or self.base
        return None

    def to_dict(self) -> dict:
        return {
            "snippet_id": self.snippet_id,
            "action": self.action,
            "reason": self.reason,
            "base_checksum": _digest(self.base),
            "local_checksum": _digest(self.local),
            "remote_checksum": _digest(self.remote),
        }


@dataclass
class SyncPlan:
    items: List[SyncItem] = field(default_factory=list)

    @property
    def conflicts(self) -> List[SyncItem]:
        return [item for item in self.items if item.conflict]

    @property
    def clean(self) -> bool:
        return not self.conflicts

    def counts(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.action] = counts.get(item.action, 0) + 1
        return dict(sorted(counts.items()))

    def resolve(self, snippet_id: str, choice: str) -> bool:
        if choice not in {"local", "remote", "base", "delete"}:
            raise ValueError(f"invalid sync resolution: {choice}")
        for item in self.items:
            if item.snippet_id != snippet_id or not item.conflict:
                continue
            if choice == "local":
                item.action = TAKE_LOCAL if item.local is not None else DELETE_LOCAL
            elif choice == "remote":
                item.action = TAKE_REMOTE if item.remote is not None else DELETE_REMOTE
            elif choice == "base":
                item.action = UNCHANGED
                item.local = item.base
                item.remote = item.base
            else:
                item.action = DELETE_LOCAL
                item.local = None
                item.remote = None
            item.reason = f"resolved using {choice}"
            return True
        return False

    def render(self) -> str:
        rows: list[str] = []
        for item in sorted(self.items, key=lambda value: value.snippet_id):
            marker = "!" if item.conflict else " "
            rows.append(f"{marker} {item.snippet_id:<16} {item.action:<14} {item.reason}")
        counts = " ".join(f"{name}={count}" for name, count in self.counts().items())
        rows.append(counts)
        return "\n".join(rows)


def _index(snippets: Iterable[Snippet]) -> Dict[str, Snippet]:
    return {snippet.id: snippet for snippet in snippets}


def plan(
    base: Iterable[Snippet],
    local: Iterable[Snippet],
    remote: Iterable[Snippet],
) -> SyncPlan:
    base_by_id = _index(base)
    local_by_id = _index(local)
    remote_by_id = _index(remote)
    identifiers = sorted(set(base_by_id) | set(local_by_id) | set(remote_by_id))
    items: list[SyncItem] = []

    for identifier in identifiers:
        base_item = base_by_id.get(identifier)
        local_item = local_by_id.get(identifier)
        remote_item = remote_by_id.get(identifier)
        base_hash = _digest(base_item)
        local_hash = _digest(local_item)
        remote_hash = _digest(remote_item)

        if local_hash == remote_hash:
            action, reason = UNCHANGED, "both sides agree"
        elif base_item is None:
            if local_item is None:
                action, reason = ADD_REMOTE, "new on remote"
            elif remote_item is None:
                action, reason = ADD_LOCAL, "new on local"
            else:
                action, reason = CONFLICT, "same id was added differently"
        elif local_item is None and remote_item is None:
            action, reason = UNCHANGED, "deleted on both sides"
        elif local_item is None:
            if remote_hash == base_hash:
                action, reason = DELETE_REMOTE, "deleted locally"
            else:
                action, reason = CONFLICT, "deleted locally and changed remotely"
        elif remote_item is None:
            if local_hash == base_hash:
                action, reason = DELETE_LOCAL, "deleted remotely"
            else:
                action, reason = CONFLICT, "changed locally and deleted remotely"
        elif local_hash == base_hash:
            action, reason = TAKE_REMOTE, "changed only on remote"
        elif remote_hash == base_hash:
            action, reason = TAKE_LOCAL, "changed only on local"
        else:
            action, reason = CONFLICT, "changed differently on both sides"
        items.append(
            SyncItem(
                snippet_id=identifier,
                action=action,
                base=base_item,
                local=local_item,
                remote=remote_item,
                reason=reason,
            )
        )
    return SyncPlan(items)


def merged(plan_result: SyncPlan, *, allow_conflicts: bool = False) -> List[Snippet]:
    if plan_result.conflicts and not allow_conflicts:
        identifiers = ", ".join(item.snippet_id for item in plan_result.conflicts)
        raise ValueError(f"sync plan has unresolved conflicts: {identifiers}")
    result: list[Snippet] = []
    for item in sorted(plan_result.items, key=lambda value: value.snippet_id):
        chosen = item.chosen()
        if chosen is not None:
            result.append(Snippet.from_dict(copy.deepcopy(chosen.to_dict())))
    return result


def changed_ids(plan_result: SyncPlan) -> List[str]:
    return [
        item.snippet_id
        for item in plan_result.items
        if item.action not in {UNCHANGED}
    ]
