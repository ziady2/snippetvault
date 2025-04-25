"""Search.

We have three search modes:

- substring: dumb ``in`` over title+body+tags. Cheap, exact.
- token: split the query on whitespace and match all tokens (AND).
- fuzzy: token search, but each token allowed up to one typo
  (Levenshtein distance 1).

Ranking: title hits beat body hits beat tag hits. Recently updated
snippets win ties.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .errors import SearchError
from .snippet import Snippet


@dataclass
class Hit:
    snippet: Snippet
    score: float
    matched_in: tuple = ()  # ('title', 'body', ...) for the UI


def _normalise(text: str) -> str:
    return (text or "").lower().strip()


def _tokenise(query: str) -> List[str]:
    return [t for t in _normalise(query).split() if t]


def _within_one(a: str, b: str) -> bool:
    """Levenshtein distance <= 1 (insertion, deletion, substitution)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    # now len(a) <= len(b)
    if len(b) == len(a) + 1:
        # try one deletion
        for i in range(len(b)):
            if a == b[:i] + b[i + 1 :]:
                return True
        return False
    # equal length: at most one substitution
    diff = sum(1 for x, y in zip(a, b) if x != y)
    return diff <= 1


def matches_token(text: str, token: str, *, fuzzy: bool = False) -> bool:
    if not token:
        return True
    haystack = _normalise(text)
    if not fuzzy:
        return token in haystack
    # fuzzy: try the token as-is first, otherwise look at each word
    if token in haystack:
        return True
    for word in haystack.split():
        if _within_one(token, word):
            return True
    return False


def search(
    snippets: Iterable[Snippet],
    query: str,
    *,
    mode: str = "token",
    rank: bool = True,
    languages: Optional[Iterable[str]] = None,
    tags: Optional[Iterable[str]] = None,
    include_archived: bool = False,
    limit: Optional[int] = None,
) -> List[Hit]:
    """Run a search and return ``Hit`` objects."""
    if mode not in {"substring", "token", "fuzzy"}:
        raise SearchError(f"unknown search mode: {mode}")
    tokens = _tokenise(query) if mode != "substring" else [query.strip().lower()] if query.strip() else []
    lang_filter = {language.lower() for language in (languages or []) if language}
    tag_filter = {t.lower() for t in (tags or []) if t}

    hits: list = []
    for s in snippets:
        if s.archived and not include_archived:
            continue
        if lang_filter and s.language.lower() not in lang_filter:
            continue
        if tag_filter and not (set(s.all_tags()) & tag_filter):
            continue
        score, matched = _score(s, tokens, mode=mode)
        if score <= 0 and tokens:
            continue
        hits.append(Hit(snippet=s, score=score, matched_in=tuple(matched)))

    if rank:
        hits.sort(key=lambda h: (-h.score, -h.snippet.updated_at))
    if limit is not None:
        hits = hits[:limit]
    return hits


def _score(s: Snippet, tokens, *, mode: str) -> tuple:
    if not tokens:
        return 1.0, ("any",)
    fuzzy = mode == "fuzzy"
    title = s.title or ""
    body = s.body or ""
    matched: list = []
    score = 0.0
    for tk in tokens:
        if matches_token(title, tk, fuzzy=fuzzy):
            score += 3.0
            if "title" not in matched:
                matched.append("title")
        elif matches_token(body, tk, fuzzy=fuzzy):
            score += 1.0
            if "body" not in matched:
                matched.append("body")
        elif any(matches_token(t, tk, fuzzy=fuzzy) for t in s.all_tags()):
            score += 0.5
            if "tags" not in matched:
                matched.append("tags")
        else:
            return 0.0, ()  # AND: any miss kills the hit
    if s.favourite:
        score *= 1.1
    return score, matched


def filter_by_tag(snippets: Iterable[Snippet], tag: str) -> List[Snippet]:
    target = (tag or "").lower()
    return [s for s in snippets if target in {t.lower() for t in s.all_tags()}]


def filter_by_language(snippets: Iterable[Snippet], language: str) -> List[Snippet]:
    target = (language or "").lower()
    return [s for s in snippets if (s.language or "").lower() == target]


def filter_by_collection(snippets: Iterable[Snippet], collection_ids: Iterable[str]) -> List[Snippet]:
    ids = set(collection_ids)
    return [s for s in snippets if s.id in ids]


def recent(snippets: Iterable[Snippet], n: int = 10) -> List[Snippet]:
    if n <= 0:
        return []
    return sorted(snippets, key=lambda s: -s.updated_at)[:n]


def most_used(snippets: Iterable[Snippet], n: int = 10) -> List[Snippet]:
    return sorted(snippets, key=lambda s: -s.used_count)[:n]


def favourites(snippets: Iterable[Snippet]) -> List[Snippet]:
    return [s for s in snippets if s.favourite]


def archived(snippets: Iterable[Snippet]) -> List[Snippet]:
    return [s for s in snippets if s.archived]


def explain(hit: Hit) -> str:
    """Human readable explanation of a hit's score, used by '--explain'."""
    parts: list = []
    parts.append(f"score={hit.score:.2f}")
    if hit.matched_in:
        parts.append("matched in " + ", ".join(hit.matched_in))
    return "; ".join(parts)
