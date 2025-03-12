"""Configurable quality policies for snippet libraries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

from .snippet import Snippet


SEVERITIES = {"info", "warning", "error"}


@dataclass(frozen=True)
class PolicyIssue:
    code: str
    message: str
    severity: str = "warning"
    snippet_id: str = ""
    field: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")


@dataclass(frozen=True)
class SnippetPolicy:
    require_title: bool = True
    require_language: bool = True
    require_tags: bool = False
    minimum_body_characters: int = 1
    maximum_body_characters: int = 200_000
    maximum_title_characters: int = 200
    maximum_tags: int = 20
    allowed_languages: tuple[str, ...] = ()
    forbidden_tag_prefixes: tuple[str, ...] = ("private:",)
    forbidden_patterns: tuple[str, ...] = ()
    stale_after_days: int = 0

    def __post_init__(self) -> None:
        if self.minimum_body_characters < 0:
            raise ValueError("minimum body characters must not be negative")
        if self.maximum_body_characters < self.minimum_body_characters:
            raise ValueError("maximum body characters is below the minimum")
        if self.maximum_title_characters < 1:
            raise ValueError("maximum title characters must be positive")
        if self.maximum_tags < 0:
            raise ValueError("maximum tags must not be negative")
        if self.stale_after_days < 0:
            raise ValueError("stale_after_days must not be negative")


def evaluate(snippet: Snippet, policy: Optional[SnippetPolicy] = None, *, now: float = 0) -> List[PolicyIssue]:
    policy = policy or SnippetPolicy()
    issues: list[PolicyIssue] = []

    def add(code: str, message: str, *, severity: str = "warning", field: str = "") -> None:
        issues.append(PolicyIssue(code, message, severity, snippet.id, field))

    if policy.require_title and not snippet.title.strip():
        add("missing_title", "snippet title is required", severity="error", field="title")
    if policy.require_language and not snippet.language.strip():
        add("missing_language", "snippet language is required", severity="error", field="language")
    if policy.require_tags and not snippet.all_tags():
        add("missing_tags", "at least one tag is required", field="tags")
    body_length = len(snippet.body)
    if body_length < policy.minimum_body_characters:
        add(
            "body_too_short",
            f"body has {body_length} characters; minimum is {policy.minimum_body_characters}",
            field="body",
        )
    if body_length > policy.maximum_body_characters:
        add(
            "body_too_long",
            f"body has {body_length} characters; maximum is {policy.maximum_body_characters}",
            severity="error",
            field="body",
        )
    if len(snippet.title) > policy.maximum_title_characters:
        add("title_too_long", "title exceeds policy limit", field="title")
    tags = snippet.all_tags()
    if len(tags) > policy.maximum_tags:
        add("too_many_tags", f"snippet has {len(tags)} tags; maximum is {policy.maximum_tags}", field="tags")
    if policy.allowed_languages:
        allowed = {language.lower() for language in policy.allowed_languages}
        if snippet.language.lower() not in allowed:
            add("language_not_allowed", f"language {snippet.language!r} is not allowed", field="language")
    for tag in tags:
        for prefix in policy.forbidden_tag_prefixes:
            if tag.lower().startswith(prefix.lower()):
                add("forbidden_tag", f"tag {tag!r} uses forbidden prefix {prefix!r}", field="tags")
    haystack = "\n".join((snippet.title, snippet.body, snippet.notes, snippet.source))
    for pattern in policy.forbidden_patterns:
        try:
            matched = re.search(pattern, haystack, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"invalid policy pattern {pattern!r}: {exc}") from exc
        if matched:
            add("forbidden_content", f"content matches forbidden pattern {pattern!r}", severity="error")
    if policy.stale_after_days and now:
        cutoff = now - policy.stale_after_days * 86400
        if snippet.updated_at < cutoff:
            add("stale", f"snippet has not been updated in {policy.stale_after_days} days", severity="info")
    return issues


def evaluate_many(
    snippets: Iterable[Snippet], policy: Optional[SnippetPolicy] = None, *, now: float = 0
) -> List[PolicyIssue]:
    issues: list[PolicyIssue] = []
    for snippet in snippets:
        issues.extend(evaluate(snippet, policy, now=now))
    return issues


def has_errors(issues: Iterable[PolicyIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def counts(issues: Iterable[PolicyIssue]) -> dict:
    result = {severity: 0 for severity in sorted(SEVERITIES)}
    for issue in issues:
        result[issue.severity] = result.get(issue.severity, 0) + 1
    return result


def render(issues: Iterable[PolicyIssue]) -> str:
    rows: list[str] = []
    for issue in sorted(issues, key=lambda item: (item.snippet_id, item.severity, item.code)):
        target = f" [{issue.snippet_id}]" if issue.snippet_id else ""
        field = f" ({issue.field})" if issue.field else ""
        rows.append(f"{issue.severity.upper():7} {issue.code}{target}{field}: {issue.message}")
    return "\n".join(rows)


def policy_to_dict(policy: SnippetPolicy) -> dict:
    return {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in ((name, getattr(policy, name)) for name in SnippetPolicy.__dataclass_fields__)
    }


def policy_from_dict(data: Mapping[str, object]) -> SnippetPolicy:
    allowed = set(SnippetPolicy.__dataclass_fields__)
    values = {key: value for key, value in (data or {}).items() if key in allowed}
    for key in ("allowed_languages", "forbidden_tag_prefixes", "forbidden_patterns"):
        if key in values:
            values[key] = tuple(values[key] or ())
    return SnippetPolicy(**values)


def combine(*policies: SnippetPolicy) -> SnippetPolicy:
    """Build a strict policy using the strongest limit from each input."""
    if not policies:
        return SnippetPolicy()
    languages = [set(policy.allowed_languages) for policy in policies if policy.allowed_languages]
    allowed_languages = tuple(sorted(set.intersection(*languages))) if languages else ()
    return SnippetPolicy(
        require_title=any(policy.require_title for policy in policies),
        require_language=any(policy.require_language for policy in policies),
        require_tags=any(policy.require_tags for policy in policies),
        minimum_body_characters=max(policy.minimum_body_characters for policy in policies),
        maximum_body_characters=min(policy.maximum_body_characters for policy in policies),
        maximum_title_characters=min(policy.maximum_title_characters for policy in policies),
        maximum_tags=min(policy.maximum_tags for policy in policies),
        allowed_languages=allowed_languages,
        forbidden_tag_prefixes=tuple(
            sorted({value for policy in policies for value in policy.forbidden_tag_prefixes})
        ),
        forbidden_patterns=tuple(
            dict.fromkeys(value for policy in policies for value in policy.forbidden_patterns)
        ),
        stale_after_days=min(
            (policy.stale_after_days for policy in policies if policy.stale_after_days),
            default=0,
        ),
    )
