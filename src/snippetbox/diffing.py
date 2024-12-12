"""Line-oriented comparison helpers for snippet revisions."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Change:
    """One opcode emitted by ``difflib.SequenceMatcher``."""

    kind: str
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    old_lines: tuple[str, ...] = ()
    new_lines: tuple[str, ...] = ()

    @property
    def old_count(self) -> int:
        return self.old_end - self.old_start

    @property
    def new_count(self) -> int:
        return self.new_end - self.new_start

    def is_change(self) -> bool:
        return self.kind != "equal"


@dataclass
class DiffResult:
    changes: List[Change] = field(default_factory=list)
    old_label: str = "before"
    new_label: str = "after"

    @property
    def additions(self) -> int:
        return sum(change.new_count for change in self.changes if change.kind in {"insert", "replace"})

    @property
    def deletions(self) -> int:
        return sum(change.old_count for change in self.changes if change.kind in {"delete", "replace"})

    @property
    def unchanged(self) -> int:
        return sum(change.old_count for change in self.changes if change.kind == "equal")

    def changed(self) -> bool:
        return any(change.is_change() for change in self.changes)

    def summary(self) -> str:
        return f"+{self.additions} -{self.deletions} ({self.unchanged} unchanged)"

    def unified(self, *, context: int = 3) -> str:
        old: list[str] = []
        new: list[str] = []
        for change in self.changes:
            old.extend(change.old_lines)
            new.extend(change.new_lines)
        lines = difflib.unified_diff(
            old,
            new,
            fromfile=self.old_label,
            tofile=self.new_label,
            n=max(0, context),
            lineterm="",
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "old_label": self.old_label,
            "new_label": self.new_label,
            "additions": self.additions,
            "deletions": self.deletions,
            "unchanged": self.unchanged,
            "changes": [
                {
                    "kind": change.kind,
                    "old_start": change.old_start,
                    "old_end": change.old_end,
                    "new_start": change.new_start,
                    "new_end": change.new_end,
                    "old_lines": list(change.old_lines),
                    "new_lines": list(change.new_lines),
                }
                for change in self.changes
            ],
        }


def _lines(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        return value.splitlines()
    return [str(line).rstrip("\r\n") for line in value]


def compare(
    before: str | Iterable[str],
    after: str | Iterable[str],
    *,
    old_label: str = "before",
    new_label: str = "after",
    ignore_trailing_space: bool = False,
) -> DiffResult:
    old_lines = _lines(before)
    new_lines = _lines(after)
    old_compare = [line.rstrip() for line in old_lines] if ignore_trailing_space else old_lines
    new_compare = [line.rstrip() for line in new_lines] if ignore_trailing_space else new_lines
    matcher = difflib.SequenceMatcher(a=old_compare, b=new_compare, autojunk=False)
    changes: list[Change] = []
    for kind, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        changes.append(
            Change(
                kind=kind,
                old_start=old_start,
                old_end=old_end,
                new_start=new_start,
                new_end=new_end,
                old_lines=tuple(old_lines[old_start:old_end]),
                new_lines=tuple(new_lines[new_start:new_end]),
            )
        )
    return DiffResult(changes=changes, old_label=old_label, new_label=new_label)


def similarity(before: str, after: str) -> float:
    return difflib.SequenceMatcher(a=before, b=after, autojunk=False).ratio()


def changed_line_numbers(result: DiffResult) -> tuple[list[int], list[int]]:
    """Return one-based changed line numbers for old and new text."""
    old_numbers: list[int] = []
    new_numbers: list[int] = []
    for change in result.changes:
        if not change.is_change():
            continue
        old_numbers.extend(range(change.old_start + 1, change.old_end + 1))
        new_numbers.extend(range(change.new_start + 1, change.new_end + 1))
    return old_numbers, new_numbers


def side_by_side(result: DiffResult, *, width: int = 60) -> str:
    """Render a compact two-column diff for terminal reports."""
    width = max(20, width)
    rows: list[str] = []
    for change in result.changes:
        count = max(len(change.old_lines), len(change.new_lines))
        for index in range(count):
            old = change.old_lines[index] if index < len(change.old_lines) else ""
            new = change.new_lines[index] if index < len(change.new_lines) else ""
            marker = " " if change.kind == "equal" else "!"
            rows.append(f"{marker} {old[:width]:<{width}} | {new[:width]}")
    return "\n".join(rows)


def apply_line_replacements(text: str, replacements: Sequence[tuple[int, int, Sequence[str]]]) -> str:
    """Apply non-overlapping zero-based line replacements.

    Replacements are validated before editing and then applied from the bottom
    upwards, so callers can calculate all ranges against the original text.
    """
    lines = text.splitlines()
    ordered = sorted(replacements, key=lambda item: item[0])
    previous_end = 0
    for start, end, _ in ordered:
        if start < 0 or end < start or end > len(lines):
            raise ValueError(f"invalid replacement range: {start}:{end}")
        if start < previous_end:
            raise ValueError("replacement ranges overlap")
        previous_end = end
    for start, end, replacement in reversed(ordered):
        lines[start:end] = [str(line).rstrip("\r\n") for line in replacement]
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix
