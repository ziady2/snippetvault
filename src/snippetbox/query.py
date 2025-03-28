"""Structured query language for snippet collections.

The basic search module is intentionally small.  Structured queries add field
filters while preserving plain terms::

    lang:python tag:async "http client" -archived:true updated>=2025-01-01

Terms are combined with AND semantics.  Repeated values for the same field are
treated as alternatives, which makes ``tag:web tag:http`` useful without a
separate OR syntax.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Sequence

from .errors import SearchError
from .snippet import Snippet
from .timestamps import parse_iso


_FILTER_RE = re.compile(
    r"^(?P<field>[a-z][a-z0-9_-]*)(?P<operator>:|!=|>=|<=|>|<)(?P<value>.*)$",
    re.IGNORECASE,
)
_ALIASES = {
    "lang": "language",
    "fav": "favourite",
    "favorite": "favourite",
    "id": "id",
    "slug": "slug",
    "tag": "tag",
    "source": "source",
    "author": "author",
    "created": "created",
    "updated": "updated",
    "archived": "archived",
    "favourite": "favourite",
    "language": "language",
    "uses": "uses",
}
_BOOLEAN_TRUE = {"1", "true", "yes", "on"}
_BOOLEAN_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Clause:
    field: str
    value: str
    operator: str = ":"
    negated: bool = False

    def __post_init__(self) -> None:
        canonical = _ALIASES.get((self.field or "").lower())
        if canonical is None:
            raise SearchError(f"unknown query field: {self.field}")
        if self.operator not in {":", "!=", ">=", "<=", ">", "<"}:
            raise SearchError(f"unsupported query operator: {self.operator}")
        if not str(self.value).strip():
            raise SearchError(f"missing value for query field: {canonical}")
        object.__setattr__(self, "field", canonical)
        object.__setattr__(self, "value", str(self.value).strip())


@dataclass
class Query:
    terms: List[str] = field(default_factory=list)
    clauses: List[Clause] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.terms and not self.clauses

    def fields(self) -> set[str]:
        return {clause.field for clause in self.clauses}

    def values(self, field_name: str) -> list[str]:
        canonical = _ALIASES.get(field_name.lower(), field_name.lower())
        return [clause.value for clause in self.clauses if clause.field == canonical]

    def render(self) -> str:
        parts = [shlex.quote(term) if " " in term else term for term in self.terms]
        for clause in self.clauses:
            prefix = "-" if clause.negated else ""
            value = shlex.quote(clause.value) if " " in clause.value else clause.value
            parts.append(f"{prefix}{clause.field}{clause.operator}{value}")
        return " ".join(parts)


def parse(text: str) -> Query:
    """Parse query text into terms and typed clauses."""
    try:
        tokens = shlex.split(text or "")
    except ValueError as exc:
        raise SearchError(f"invalid query quoting: {exc}") from exc
    query = Query()
    for token in tokens:
        negated = token.startswith("-") and len(token) > 1
        candidate = token[1:] if negated else token
        match = _FILTER_RE.match(candidate)
        if not match:
            if negated:
                query.terms.append("-" + candidate)
            else:
                query.terms.append(candidate)
            continue
        query.clauses.append(
            Clause(
                field=match.group("field"),
                operator=match.group("operator"),
                value=match.group("value"),
                negated=negated,
            )
        )
    return query


def _parse_bool(value: str) -> bool:
    normalised = value.lower()
    if normalised in _BOOLEAN_TRUE:
        return True
    if normalised in _BOOLEAN_FALSE:
        return False
    raise SearchError(f"invalid boolean query value: {value!r}")


def _compare(actual, expected, operator: str) -> bool:
    if operator == ":":
        if isinstance(actual, str):
            return str(expected).lower() in actual.lower()
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == ">=":
        return actual >= expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == "<":
        return actual < expected
    raise SearchError(f"unsupported query operator: {operator}")


def _author_text(snippet: Snippet) -> str:
    author = snippet.author
    return " ".join(
        value for value in (getattr(author, "name", ""), getattr(author, "email", "")) if value
    )


def _matches_clause(snippet: Snippet, clause: Clause) -> bool:
    field_name = clause.field
    value = clause.value
    if field_name == "tag":
        result = any(_compare(tag, value, clause.operator) for tag in snippet.all_tags())
    elif field_name in {"archived", "favourite"}:
        result = _compare(bool(getattr(snippet, field_name)), _parse_bool(value), clause.operator)
    elif field_name in {"created", "updated"}:
        expected = parse_iso(value).timestamp()
        actual = snippet.created_at if field_name == "created" else snippet.updated_at
        result = _compare(actual, expected, clause.operator)
    elif field_name == "uses":
        try:
            expected_number = int(value)
        except ValueError as exc:
            raise SearchError(f"invalid usage count: {value!r}") from exc
        result = _compare(snippet.used_count, expected_number, clause.operator)
    elif field_name == "author":
        result = _compare(_author_text(snippet), value, clause.operator)
    else:
        result = _compare(str(getattr(snippet, field_name, "") or ""), value, clause.operator)
    return not result if clause.negated else result


def _matches_terms(snippet: Snippet, terms: Sequence[str]) -> bool:
    positive = [term for term in terms if not term.startswith("-")]
    negative = [term[1:] for term in terms if term.startswith("-") and len(term) > 1]
    haystack = "\n".join(
        [
            snippet.title,
            snippet.body,
            snippet.language,
            snippet.notes,
            snippet.source,
            " ".join(snippet.all_tags()),
            _author_text(snippet),
        ]
    ).lower()
    return all(term.lower() in haystack for term in positive) and not any(
        term.lower() in haystack for term in negative
    )


def matches(snippet: Snippet, query: Query) -> bool:
    if not _matches_terms(snippet, query.terms):
        return False
    grouped: Dict[str, list[Clause]] = {}
    for clause in query.clauses:
        grouped.setdefault(clause.field, []).append(clause)
    for clauses in grouped.values():
        positive = [clause for clause in clauses if not clause.negated]
        negative = [clause for clause in clauses if clause.negated]
        if positive and not any(_matches_clause(snippet, clause) for clause in positive):
            return False
        if any(not _matches_clause(snippet, clause) for clause in negative):
            return False
    return True


def filter_snippets(snippets: Iterable[Snippet], query_or_text: Query | str) -> list[Snippet]:
    query = parse(query_or_text) if isinstance(query_or_text, str) else query_or_text
    return [snippet for snippet in snippets if matches(snippet, query)]


def compile_predicate(query_or_text: Query | str) -> Callable[[Snippet], bool]:
    query = parse(query_or_text) if isinstance(query_or_text, str) else query_or_text
    return lambda snippet: matches(snippet, query)


def explain(snippet: Snippet, query_or_text: Query | str) -> dict:
    query = parse(query_or_text) if isinstance(query_or_text, str) else query_or_text
    clauses = [
        {
            "field": clause.field,
            "operator": clause.operator,
            "value": clause.value,
            "negated": clause.negated,
            "matched": _matches_clause(snippet, clause),
        }
        for clause in query.clauses
    ]
    return {
        "snippet_id": snippet.id,
        "matched": matches(snippet, query),
        "terms_matched": _matches_terms(snippet, query.terms),
        "clauses": clauses,
    }
