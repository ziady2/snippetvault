"""The ``Snippet`` dataclass.

This is the central entity: a piece of code with a title, a
language, optional tags and metadata. The dataclass is intentionally
flat; nesting beyond one level made the JSON ugly to grep.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import List

from .author import Author
from .errors import InvalidSnippetError


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_TITLE = 200


def _now() -> float:
    return time.time()


def _slugify(text: str) -> str:
    if not text:
        return ""
    s = text.lower().strip()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:80] if s else ""


def _short_hash(body: str, length: int = 7) -> str:
    h = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
    return h[:length]


@dataclass
class Snippet:
    """One stored snippet."""

    id: str = ""
    title: str = ""
    body: str = ""
    language: str = "plain"
    tags: List[str] = field(default_factory=list)
    auto_tags: List[str] = field(default_factory=list)
    slug: str = ""
    author: Author = field(default_factory=Author)
    source: str = ""
    notes: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    favourite: bool = False
    archived: bool = False
    used_count: int = 0
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalise required strings without raising; raise only when
        # the snippet is genuinely unusable.
        self.title = (self.title or "").strip()[:_MAX_TITLE]
        self.body = self.body if self.body is not None else ""
        self.language = (self.language or "plain").strip().lower()
        if not self.id:
            self.id = self._build_id()
        if not self.slug:
            self.slug = _slugify(self.title) or _short_hash(self.body)

    def _build_id(self) -> str:
        """A stable-ish id derived from title+body+timestamp."""
        seed = f"{self.title}\u0001{self.body[:512]}\u0001{self.created_at:.6f}"
        return _short_hash(seed, length=12)

    def validate(self) -> None:
        """Raise ``InvalidSnippetError`` if this snippet wouldn't save cleanly."""
        if not self.title and not self.body:
            raise InvalidSnippetError(
                "snippet must have either a title or a body",
                field="title",
            )
        if not self.id:
            raise InvalidSnippetError("snippet missing id", field="id")
        if any(not t for t in self.tags):
            raise InvalidSnippetError("blank tag in tags list", field="tags")
        if "\n" in self.title:
            raise InvalidSnippetError("title contains a newline", field="title")

    def touch(self) -> None:
        self.updated_at = _now()

    def mark_used(self) -> None:
        self.used_count += 1
        self.touch()

    def all_tags(self) -> List[str]:
        seen: set = set()
        out: list = []
        for t in (*self.tags, *self.auto_tags):
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

    def has_tag(self, tag: str) -> bool:
        # case-insensitive across both manual + auto tags
        target = (tag or "").strip().lower()
        if not target:
            return False
        for t in self.all_tags():
            if (t or "").lower() == target:
                return True
        return False

    def line_count(self) -> int:
        if not self.body:
            return 0
        return self.body.count("\n") + (0 if self.body.endswith("\n") else 1)

    def char_count(self) -> int:
        return len(self.body)

    def to_dict(self) -> dict:
        # Keep keys stable: never reorder for code-style reasons.
        d: dict = {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "language": self.language,
            "tags": list(self.tags),
            "auto_tags": list(self.auto_tags),
            "slug": self.slug,
            "source": self.source,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "favourite": self.favourite,
            "archived": self.archived,
            "used_count": self.used_count,
        }
        author = self.author.to_dict()
        if author:
            d["author"] = author
        if self.extra:
            d["extra"] = dict(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Snippet":
        if not isinstance(data, dict):
            raise InvalidSnippetError("snippet entry must be a dict")
        s = cls(
            id=data.get("id", "") or "",
            title=data.get("title", "") or "",
            body=data.get("body", "") or "",
            language=data.get("language", "plain") or "plain",
            tags=list(data.get("tags") or []),
            auto_tags=list(data.get("auto_tags") or []),
            slug=data.get("slug", "") or "",
            author=Author.from_dict(data.get("author")),
            source=data.get("source", "") or "",
            notes=data.get("notes", "") or "",
            created_at=(
                float(data["created_at"])
                if data.get("created_at") is not None
                else _now()
            ),
            updated_at=(
                float(data["updated_at"])
                if data.get("updated_at") is not None
                else _now()
            ),
            favourite=bool(data.get("favourite")),
            archived=bool(data.get("archived")),
            used_count=int(data.get("used_count") or 0),
            extra=dict(data.get("extra") or {}),
        )
        return s

    def short_summary(self, width: int = 80) -> str:
        body_first = (self.body or "").splitlines()[0] if self.body else ""
        if len(body_first) > width:
            body_first = body_first[: width - 1] + "\u2026"
        return body_first or self.title

    def matches_query(self, q: str) -> bool:
        # cheap "any" search; the proper search lives in search.py
        if not q:
            return True
        ql = q.lower()
        for hay in (self.title, self.body, self.language, self.notes):
            if ql in (hay or "").lower():
                return True
        for t in self.all_tags():
            if ql in t:
                return True
        return False

    def fingerprint(self) -> str:
        """Hash of normalised body — used by dedup."""
        norm = "\n".join(line.rstrip() for line in (self.body or "").splitlines()).strip()
        return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()
