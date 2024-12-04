"""Find duplicate or near-duplicate snippets.

Two snippets count as duplicates when their normalised body (with
trailing whitespace stripped from each line, leading/trailing blank
lines removed, comments optionally stripped) hashes to the same
SHA-256.

For *near* duplicates we use a token-set Jaccard similarity. Cheap
and good enough.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .highlight import strip_comments
from .snippet import Snippet


@dataclass
class Cluster:
    snippets: List[Snippet]

    def size(self) -> int:
        return len(self.snippets)

    def primary(self) -> Snippet:
        # earliest-created wins; fallback to lowest id
        return min(self.snippets, key=lambda s: (s.created_at, s.id))

    def others(self) -> List[Snippet]:
        primary = self.primary()
        return [s for s in self.snippets if s.id != primary.id]


def fingerprint(snippet: Snippet, *, drop_comments: bool = False) -> str:
    body = snippet.body or ""
    if drop_comments:
        body = strip_comments(body, snippet.language)
    norm = "\n".join(line.rstrip() for line in body.splitlines()).strip()
    return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()


def find_duplicates(snippets: Iterable[Snippet], *, drop_comments: bool = False) -> List[Cluster]:
    buckets: dict = {}
    for s in snippets:
        key = fingerprint(s, drop_comments=drop_comments)
        buckets.setdefault(key, []).append(s)
    clusters: list = []
    for ss in buckets.values():
        if len(ss) > 1:
            clusters.append(Cluster(snippets=list(ss)))
    return clusters


def _tokens(body: str) -> set:
    out: set = set()
    for line in (body or "").splitlines():
        for tok in line.split():
            tok = tok.strip(",.;:()[]{}\"'`").lower()
            if tok:
                out.add(tok)
    return out


def jaccard(a: str, b: str) -> float:
    sa, sb = _tokens(a), _tokens(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_near_duplicates(
    snippets: Iterable[Snippet],
    *,
    threshold: float = 0.85,
    same_language: bool = True,
) -> List[Tuple[Snippet, Snippet, float]]:
    snippets = list(snippets)
    out: list = []
    for i in range(len(snippets)):
        for j in range(i + 1, len(snippets)):
            a, b = snippets[i], snippets[j]
            if same_language and a.language != b.language:
                continue
            score = jaccard(a.body, b.body)
            if score >= threshold:
                out.append((a, b, score))
    out.sort(key=lambda t: -t[2])
    return out


def merge_pair(primary: Snippet, secondary: Snippet) -> Snippet:
    """Return ``primary`` with tags + notes pulled in from ``secondary``."""
    tags: list = []
    seen: set = set()
    for t in (*primary.tags, *secondary.tags):
        if t and t not in seen:
            seen.add(t)
            tags.append(t)
    primary.tags = tags
    primary.auto_tags = list(dict.fromkeys((*primary.auto_tags, *secondary.auto_tags)))
    if secondary.notes and secondary.notes not in primary.notes:
        if primary.notes:
            primary.notes = primary.notes + "\n---\n" + secondary.notes
        else:
            primary.notes = secondary.notes
    if secondary.favourite:
        primary.favourite = True
    primary.used_count = max(primary.used_count, secondary.used_count)
    primary.touch()
    return primary


def report(clusters: Iterable[Cluster]) -> str:
    lines: list = []
    for c in clusters:
        head = c.primary()
        lines.append(f"# duplicate cluster ({c.size()} snippets)")
        lines.append(f"  primary: {head.id} {head.title!r}")
        for s in c.others():
            lines.append(f"  also:    {s.id} {s.title!r}")
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def total_duplicates(clusters: Iterable[Cluster]) -> int:
    return sum(c.size() - 1 for c in clusters)
