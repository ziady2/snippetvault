"""Auto-tagger.

I'm not religious about lint -- the basics are enough -- and I'm
just-as-not-religious about ML for tagging. This is a curated
keyword map. If a snippet's body contains a keyword, it gets the
tag. That's it.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List

from .snippet import Snippet


# (tag, [list of regex patterns])
_RULES: tuple = (
    ("io", [r"\bopen\(", r"\bread\(", r"\bwrite\(", r"\bos\.path\b", r"\bpathlib\b"]),
    ("async", [r"\basync\s+def\b", r"\basyncio\b", r"\bawait\b", r"\baiohttp\b"]),
    ("regex", [r"\bre\.compile\b", r"\bre\.search\b", r"\bre\.match\b"]),
    ("subprocess", [r"\bsubprocess\b", r"\bos\.system\b", r"\bpopen\b"]),
    ("threading", [r"\bthreading\b", r"\bThread\(", r"\bRLock\b", r"\bmultiprocessing\b"]),
    ("date", [r"\bdatetime\b", r"\btimedelta\b", r"\btime\.time\b"]),
    ("json", [r"\bjson\.loads\b", r"\bjson\.dumps\b"]),
    ("yaml", [r"\byaml\.load\b", r"\byaml\.safe_load\b"]),
    ("csv", [r"\bcsv\.reader\b", r"\bcsv\.writer\b", r"\bDictReader\b"]),
    ("http", [r"\brequests\b", r"\bhttp\.client\b", r"\burllib\b", r"\bfetch\(\b"]),
    ("sql", [r"\bSELECT\s+\b", r"\bINSERT\s+INTO\b", r"\bUPDATE\s+\b", r"\bsqlite3\b"]),
    ("test", [r"\bpytest\b", r"\bdef\s+test_", r"\bunittest\b", r"\bassert\s+"]),
    ("logging", [r"\blogging\.\w+\(", r"\blogger\.\w+\("]),
    ("itertools", [r"\bitertools\.\w+\b"]),
    ("dataclass", [r"@dataclass\b", r"\bdataclass\("]),
    ("typing", [r"\btyping\.\w+\b", r"\bfrom\s+typing\b", r"\bOptional\[", r"\bList\[", r"\bDict\["]),
    ("django", [r"\bdjango\b", r"\bModels\.\w+\b"]),
    ("flask", [r"\bflask\.\w+\b", r"@app\.route\b"]),
    ("react", [r"\bReact\.\w+\b", r"\buseState\(", r"\buseEffect\("]),
    ("git", [r"\bgit\s+(?:add|commit|push|pull|rebase|cherry-pick|log|status)\b"]),
    ("docker", [r"\bdocker\s+(?:run|build|push|pull|exec)\b", r"\bdockerfile\b"]),
    ("aws", [r"\bboto3\b", r"\baws_\w+\b"]),
)


def _compile_rules() -> list:
    out: list = []
    for tag, patterns in _RULES:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        out.append((tag, compiled))
    return out


_COMPILED = _compile_rules()


def suggest_tags(snippet: Snippet, *, max_tags: int = 6) -> List[str]:
    """Return a list of tags this snippet probably should have."""
    text = " ".join([snippet.title or "", snippet.body or ""])
    counts: Counter = Counter()
    for tag, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                counts[tag] += 1
                break  # one hit per pattern is enough
    out = [tag for tag, _ in counts.most_common(max_tags)]
    return out


def apply_to(snippet: Snippet, *, max_tags: int = 6) -> List[str]:
    """Mutate ``snippet.auto_tags`` in place; return the tag list."""
    suggested = suggest_tags(snippet, max_tags=max_tags)
    snippet.auto_tags = suggested
    snippet.touch()
    return suggested


def apply_to_many(snippets: Iterable[Snippet], *, max_tags: int = 6) -> int:
    """Run ``apply_to`` over every snippet. Return how many changed."""
    changed = 0
    for s in snippets:
        before = list(s.auto_tags)
        apply_to(s, max_tags=max_tags)
        if before != s.auto_tags:
            changed += 1
    return changed


def known_tags() -> List[str]:
    return [t for t, _ in _RULES]


def match_count(text: str) -> int:
    """How many tag rules match this body. Used by ``lint`` & ``report``."""
    text = text or ""
    matches = 0
    for _tag, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                matches += 1
                break
    return matches


def add_custom_rule(tag: str, patterns: Iterable[str]) -> None:
    """Append a user rule. Mutates the global compiled rules."""
    if not tag or not patterns:
        return
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns if p]
    _COMPILED.append((tag, compiled))
