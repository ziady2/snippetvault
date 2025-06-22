"""Composable, previewable transformations for snippet text."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping

from .diffing import DiffResult, compare
from .snippet import Snippet


TRANSFORMS = {
    "normalise_newlines",
    "trim_trailing_space",
    "strip_blank_edges",
    "dedent",
    "tabs_to_spaces",
    "ensure_final_newline",
    "replace",
    "regex_replace",
}


@dataclass(frozen=True)
class Transform:
    kind: str
    value: str = ""
    replacement: str = ""
    options: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in TRANSFORMS:
            raise ValueError(f"unknown transform: {self.kind}")
        if self.kind in {"replace", "regex_replace"} and not self.value:
            raise ValueError(f"transform {self.kind} requires a search value")
        if self.kind == "tabs_to_spaces":
            width = int(self.options.get("width", 4))
            if not 1 <= width <= 16:
                raise ValueError("tab width must be between 1 and 16")


@dataclass
class TransformStep:
    transform: Transform
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after

    def diff(self) -> DiffResult:
        return compare(self.before, self.after, old_label="before", new_label=self.transform.kind)


@dataclass
class TransformResult:
    original: str
    text: str
    steps: List[TransformStep] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.original != self.text

    @property
    def changed_steps(self) -> List[TransformStep]:
        return [step for step in self.steps if step.changed]

    def summary(self) -> dict:
        result = compare(self.original, self.text)
        return {
            "changed": self.changed,
            "steps": len(self.steps),
            "changed_steps": len(self.changed_steps),
            "additions": result.additions,
            "deletions": result.deletions,
        }


def apply_one(text: str, transform: Transform) -> str:
    if transform.kind == "normalise_newlines":
        return text.replace("\r\n", "\n").replace("\r", "\n")
    if transform.kind == "trim_trailing_space":
        suffix = "\n" if text.endswith(("\n", "\r")) else ""
        return "\n".join(line.rstrip() for line in text.splitlines()) + suffix
    if transform.kind == "strip_blank_edges":
        return text.strip("\r\n")
    if transform.kind == "dedent":
        return textwrap.dedent(text)
    if transform.kind == "tabs_to_spaces":
        return text.expandtabs(int(transform.options.get("width", 4)))
    if transform.kind == "ensure_final_newline":
        return text.rstrip("\r\n") + "\n" if text else ""
    if transform.kind == "replace":
        count = int(transform.options.get("count", -1))
        return text.replace(transform.value, transform.replacement, count)
    if transform.kind == "regex_replace":
        flags = 0
        if transform.options.get("ignore_case"):
            flags |= re.IGNORECASE
        if transform.options.get("multiline"):
            flags |= re.MULTILINE
        if transform.options.get("dotall"):
            flags |= re.DOTALL
        count = int(transform.options.get("count", 0))
        try:
            return re.sub(transform.value, transform.replacement, text, count=count, flags=flags)
        except re.error as exc:
            raise ValueError(f"invalid transform regex {transform.value!r}: {exc}") from exc
    raise ValueError(f"unknown transform: {transform.kind}")


def apply(text: str, transforms: Iterable[Transform]) -> TransformResult:
    current = text or ""
    steps: list[TransformStep] = []
    for transform in transforms:
        before = current
        current = apply_one(current, transform)
        steps.append(TransformStep(transform=transform, before=before, after=current))
    return TransformResult(original=text or "", text=current, steps=steps)


def apply_to_snippet(
    snippet: Snippet,
    transforms: Iterable[Transform],
    *,
    touch: bool = True,
) -> tuple[Snippet, TransformResult]:
    result = apply(snippet.body, transforms)
    copy = Snippet.from_dict(snippet.to_dict())
    copy.body = result.text
    if result.changed and touch:
        copy.touch()
    return copy, result


def parse(specifications: Iterable[str]) -> List[Transform]:
    """Parse CLI-friendly forms like ``replace=old=>new``."""
    transforms: list[Transform] = []
    for specification in specifications:
        kind, separator, payload = specification.partition("=")
        kind = kind.strip().lower().replace("-", "_")
        if kind in {"replace", "regex_replace"}:
            if not separator or "=>" not in payload:
                raise ValueError(f"{kind} must use {kind}=SEARCH=>REPLACEMENT")
            value, replacement = payload.split("=>", 1)
            transforms.append(Transform(kind, value=value, replacement=replacement))
        elif kind == "tabs_to_spaces":
            width = int(payload) if separator and payload else 4
            transforms.append(Transform(kind, options={"width": width}))
        else:
            if separator and payload:
                raise ValueError(f"transform {kind} does not accept a value")
            transforms.append(Transform(kind))
    return transforms


def default_cleanup() -> List[Transform]:
    return [
        Transform("normalise_newlines"),
        Transform("trim_trailing_space"),
        Transform("strip_blank_edges"),
        Transform("ensure_final_newline"),
    ]


def render(result: TransformResult, *, include_diff: bool = False) -> str:
    summary = result.summary()
    rows = [
        f"changed: {'yes' if summary['changed'] else 'no'}",
        f"steps: {summary['steps']} ({summary['changed_steps']} changed text)",
        f"lines: +{summary['additions']} -{summary['deletions']}",
    ]
    for step in result.steps:
        rows.append(f"  {'*' if step.changed else '-'} {step.transform.kind}")
    if include_diff and result.changed:
        rows.extend(("", compare(result.original, result.text).unified()))
    return "\n".join(rows)
