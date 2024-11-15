"""Plan and apply repeatable batch edits to snippets."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional

from .snippet import Snippet
from .tag import normalise as normalise_tag


OPERATIONS = {
    "add_tag",
    "remove_tag",
    "set_language",
    "archive",
    "unarchive",
    "favourite",
    "unfavourite",
    "set_source",
    "clear_notes",
}


@dataclass(frozen=True)
class BatchOperation:
    kind: str
    value: str = ""

    def __post_init__(self) -> None:
        if self.kind not in OPERATIONS:
            raise ValueError(f"unknown batch operation: {self.kind}")
        if self.kind in {"add_tag", "remove_tag", "set_language", "set_source"} and not self.value.strip():
            raise ValueError(f"batch operation {self.kind} requires a value")


@dataclass
class BatchChange:
    snippet_id: str
    before: dict
    after: dict
    operations: List[BatchOperation] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def fields_changed(self) -> list[str]:
        return sorted(
            key for key in set(self.before) | set(self.after) if self.before.get(key) != self.after.get(key)
        )


@dataclass
class BatchPlan:
    changes: List[BatchChange] = field(default_factory=list)

    @property
    def selected_count(self) -> int:
        return len(self.changes)

    @property
    def changed_count(self) -> int:
        return sum(change.changed for change in self.changes)

    def changed(self) -> List[BatchChange]:
        return [change for change in self.changes if change.changed]

    def summary(self) -> dict:
        fields: dict[str, int] = {}
        for change in self.changed():
            for field_name in change.fields_changed():
                fields[field_name] = fields.get(field_name, 0) + 1
        return {
            "selected": self.selected_count,
            "changed": self.changed_count,
            "fields": dict(sorted(fields.items())),
        }


def _apply_one(snippet: Snippet, operation: BatchOperation) -> None:
    if operation.kind == "add_tag":
        tag = normalise_tag(operation.value)
        if tag and tag not in snippet.tags:
            snippet.tags.append(tag)
    elif operation.kind == "remove_tag":
        target = normalise_tag(operation.value)
        snippet.tags = [tag for tag in snippet.tags if normalise_tag(tag) != target]
        snippet.auto_tags = [tag for tag in snippet.auto_tags if normalise_tag(tag) != target]
    elif operation.kind == "set_language":
        snippet.language = operation.value.strip().lower()
    elif operation.kind == "archive":
        snippet.archived = True
    elif operation.kind == "unarchive":
        snippet.archived = False
    elif operation.kind == "favourite":
        snippet.favourite = True
    elif operation.kind == "unfavourite":
        snippet.favourite = False
    elif operation.kind == "set_source":
        snippet.source = operation.value.strip()
    elif operation.kind == "clear_notes":
        snippet.notes = ""


def apply_operations(snippet: Snippet, operations: Iterable[BatchOperation], *, touch: bool = True) -> Snippet:
    result = Snippet.from_dict(copy.deepcopy(snippet.to_dict()))
    before = result.to_dict()
    for operation in operations:
        _apply_one(result, operation)
    if touch and result.to_dict() != before:
        result.touch()
    return result


def plan(
    snippets: Iterable[Snippet],
    operations: Iterable[BatchOperation],
    *,
    predicate: Optional[Callable[[Snippet], bool]] = None,
    touch: bool = False,
) -> BatchPlan:
    operations = list(operations)
    changes: list[BatchChange] = []
    for snippet in snippets:
        if predicate is not None and not predicate(snippet):
            continue
        result = apply_operations(snippet, operations, touch=touch)
        changes.append(
            BatchChange(
                snippet_id=snippet.id,
                before=snippet.to_dict(),
                after=result.to_dict(),
                operations=list(operations),
            )
        )
    return BatchPlan(changes)


def apply_to_book(book, batch_plan: BatchPlan, *, save: bool = False) -> int:
    changed = 0
    for change in batch_plan.changed():
        snippet = Snippet.from_dict(change.after)
        if book.replace(snippet):
            changed += 1
    if changed and save:
        book.save()
    return changed


def parse_operations(items: Iterable[str]) -> List[BatchOperation]:
    operations: list[BatchOperation] = []
    for item in items:
        kind, separator, value = item.partition("=")
        kind = kind.strip().lower().replace("-", "_")
        if not separator:
            value = ""
        operations.append(BatchOperation(kind=kind, value=value))
    return operations


def render_plan(batch_plan: BatchPlan) -> str:
    rows: list[str] = []
    for change in batch_plan.changes:
        status = "change" if change.changed else "unchanged"
        fields = ",".join(change.fields_changed()) or "-"
        rows.append(f"{change.snippet_id}  {status:<9}  {fields}")
    summary = batch_plan.summary()
    rows.append(f"selected={summary['selected']} changed={summary['changed']}")
    return "\n".join(rows)
