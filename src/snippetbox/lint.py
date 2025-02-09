"""Lint a book or individual snippets.

The lint rules here are very mild. They flag things I personally got
wrong often enough to bother detecting:

- empty body
- body of only comments
- missing language (or language='plain' on something obviously not plain)
- ridiculously long single line
- title that's just punctuation
- duplicate slugs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .highlight import code_lines, comment_lines, guess_language
from .snippet import Snippet


@dataclass
class Issue:
    snippet_id: str
    code: str
    message: str
    severity: str = "warn"  # 'info' | 'warn' | 'error'

    def format(self) -> str:
        return f"[{self.severity}] {self.code} {self.snippet_id}: {self.message}"


def lint_snippet(snippet: Snippet) -> List[Issue]:
    out: list = []
    body = snippet.body or ""
    if not body.strip():
        out.append(Issue(snippet.id, "EMPTY_BODY", "snippet has no body", severity="warn"))
        return out
    if not snippet.title:
        out.append(Issue(snippet.id, "NO_TITLE", "snippet has no title", severity="info"))
    elif snippet.title and not any(c.isalnum() for c in snippet.title):
        out.append(Issue(snippet.id, "BAD_TITLE", "title has no alphanumerics", severity="warn"))
    if snippet.language in ("", "plain"):
        guessed = guess_language(body)
        if guessed not in ("plain", "", snippet.language):
            out.append(
                Issue(
                    snippet.id,
                    "MAYBE_LANG",
                    f"language is {snippet.language!r} but body looks like {guessed!r}",
                    severity="info",
                )
            )
    code = code_lines(body, snippet.language)
    comments = comment_lines(body, snippet.language)
    if not code and comments:
        out.append(Issue(snippet.id, "ONLY_COMMENTS", "snippet body is only comments", severity="warn"))
    longest = max((len(line) for line in body.splitlines()), default=0)
    if longest > 400:
        out.append(
            Issue(
                snippet.id,
                "LONG_LINE",
                f"line of {longest} chars; might be a paste accident",
                severity="info",
            )
        )
    if len(snippet.tags) > 12:
        out.append(Issue(snippet.id, "MANY_TAGS", "snippet has more than 12 manual tags", severity="info"))
    return out


def lint_book(book_data: dict) -> List[Issue]:
    out: list = []
    snippets_raw = book_data.get("snippets") or []
    slugs: dict = {}
    for raw in snippets_raw:
        try:
            s = Snippet.from_dict(raw)
        except Exception as exc:  # noqa: BLE001
            ident = raw.get("id", "?") if isinstance(raw, dict) else "?"
            out.append(Issue(ident, "BAD_SNIPPET", str(exc), severity="error"))
            continue
        out.extend(lint_snippet(s))
        slug = s.slug or ""
        if slug:
            if slug in slugs:
                out.append(
                    Issue(
                        s.id,
                        "DUP_SLUG",
                        f"slug {slug!r} also used by {slugs[slug]}",
                        severity="error",
                    )
                )
            slugs[slug] = s.id
    return out


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(i.severity == "error" for i in issues)


def count_by_code(issues: Iterable[Issue]) -> dict:
    out: dict = {}
    for i in issues:
        out[i.code] = out.get(i.code, 0) + 1
    return out


def filter_by_severity(issues: Iterable[Issue], severity: str) -> List[Issue]:
    return [i for i in issues if i.severity == severity]


def render_issues(issues: Iterable[Issue]) -> str:
    return "\n".join(i.format() for i in issues)


def is_clean(issues: Iterable[Issue]) -> bool:
    return not list(issues)


def severity_rank(severity: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(severity, 0)


def worst(issues: Iterable[Issue]) -> str:
    s = "info"
    for i in issues:
        if severity_rank(i.severity) > severity_rank(s):
            s = i.severity
    return s
