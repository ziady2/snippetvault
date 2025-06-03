"""Tag handling.

Tags are lower-case strings, stripped, with internal whitespace
collapsed. There is no Tag class outside of the ``Tag`` dataclass
below; everywhere else we just pass strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


_RESERVED = {"all", "untagged", "trash"}


@dataclass(frozen=True)
class Tag:
    """A normalised tag with optional colour + description.

    Frozen because tags are used in sets a lot. If you want to
    rename a tag, build a new one.
    """

    name: str
    colour: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        # we run normalise here so users can pass weird input
        object.__setattr__(self, "name", normalise(self.name))


def normalise(raw: str) -> str:
    """Strip + lower + collapse whitespace + drop a leading '#'."""
    if raw is None:
        return ""
    t = raw.strip()
    if t.startswith("#"):
        t = t[1:]
    t = " ".join(t.lower().split())
    return t


def is_reserved(name: str) -> bool:
    return normalise(name) in _RESERVED


def is_valid(name: str) -> bool:
    n = normalise(name)
    if not n:
        return False
    if is_reserved(n):
        return False
    if len(n) > 64:
        return False
    if any(c in n for c in ",;\n\t"):
        return False
    return True


def parse(raw: str) -> List[str]:
    """Parse a comma-separated tag string into a clean list."""
    if not raw:
        return []
    out: list = []
    seen: set = set()
    for piece in raw.replace(";", ",").split(","):
        t = normalise(piece)
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def join(tags: Iterable) -> str:
    """Inverse of ``parse``: join a list of tags back into a string."""
    return ", ".join(t for t in tags if t)


def merge(*lists: Iterable) -> List[str]:
    seen: set = set()
    out: list = []
    for lst in lists:
        for t in lst:
            n = normalise(t)
            if not n or n in seen:
                continue
            seen.add(n)
            out.append(n)
    return out


def diff(a: Iterable, b: Iterable):
    """Return (added, removed) when going from a -> b."""
    sa = {normalise(x) for x in a if x}
    sb = {normalise(x) for x in b if x}
    sa.discard("")
    sb.discard("")
    return sorted(sb - sa), sorted(sa - sb)


def common(*lists: Iterable) -> List[str]:
    """Return tags present in every list (intersection)."""
    sets = []
    for lst in lists:
        sets.append({normalise(x) for x in lst if x})
    if not sets:
        return []
    return sorted(set.intersection(*sets))


def sort_alpha(tags: Iterable) -> List[str]:
    return sorted({normalise(t) for t in tags if t})


def sort_by_count(counter: dict) -> List[tuple]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def with_prefix(prefix: str, tags: Iterable) -> List[str]:
    p = normalise(prefix)
    return [t for t in tags if normalise(t).startswith(p)]


def strip_hash(text: str) -> str:
    return text.lstrip("#").strip()


def humanise(tag: str) -> str:
    """Render a tag for a UI: 'web-dev' -> 'Web Dev'."""
    n = normalise(tag)
    if not n:
        return ""
    return " ".join(word.capitalize() for word in n.replace("-", " ").replace("_", " ").split())


def from_csv_cell(cell: str) -> List[str]:
    """A CSV cell may use '|' or ',' as a separator. Be tolerant."""
    if not cell:
        return []
    cleaned = cell.replace("|", ",")
    return parse(cleaned)


def to_csv_cell(tags: Iterable) -> str:
    return "|".join(t for t in tags if t)
