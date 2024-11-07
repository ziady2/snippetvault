"""Authors.

A snippet may credit its author (e.g. when imported from a Gist).
This is mostly informational; nothing in snippetbox does anything
behavioural with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Author:
    name: str = ""
    email: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        self.email = (self.email or "").strip()
        self.url = (self.url or "").strip()

    def display(self) -> str:
        """Single-line presentation. Email in <> if present."""
        if self.name and self.email:
            return f"{self.name} <{self.email}>"
        if self.name:
            return self.name
        if self.email:
            return self.email
        return self.url or "anonymous"

    def to_dict(self) -> dict:
        d = {}
        if self.name:
            d["name"] = self.name
        if self.email:
            d["email"] = self.email
        if self.url:
            d["url"] = self.url
        return d

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Author":
        if not data:
            return cls()
        return cls(
            name=data.get("name", ""),
            email=data.get("email", ""),
            url=data.get("url", ""),
        )

    @classmethod
    def from_string(cls, raw: str) -> "Author":
        """Parse 'Name <email>' / plain email / plain name."""
        if not raw:
            return cls()
        s = raw.strip()
        # Name <email>
        if "<" in s and s.rstrip().endswith(">"):
            name, _, rest = s.partition("<")
            email = rest.rstrip(">").strip()
            return cls(name=name.strip(), email=email)
        # bare email
        if "@" in s and " " not in s:
            return cls(email=s)
        # bare URL
        if s.startswith(("http://", "https://")):
            return cls(url=s)
        return cls(name=s)

    def is_blank(self) -> bool:
        return not (self.name or self.email or self.url)

    def with_email(self, email: str) -> "Author":
        return Author(name=self.name, email=email, url=self.url)

    def with_name(self, name: str) -> "Author":
        return Author(name=name, email=self.email, url=self.url)

    def __bool__(self) -> bool:
        return not self.is_blank()


def equal(a: "Author", b: "Author") -> bool:
    """Authors are equal if their visible representation matches.

    We don't use ``__eq__`` because it'd interfere with Python's hashing.
    """
    return a.display().lower() == b.display().lower()


def unique(authors) -> list:
    seen = set()
    out = []
    for a in authors:
        if a.is_blank():
            continue
        key = a.display().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def from_git_format(line: str) -> Author:
    """Parse a git-style 'Name <email> 1234567890 +0000' line.

    Used by the Gist import path because GitHub's commit-author
    metadata occasionally surfaces in snippets-from-gists.
    """
    if not line:
        return Author()
    s = line.strip()
    if "<" not in s:
        return Author.from_string(s)
    if " " not in s:
        return Author.from_string(s)
    head, _, _ = s.partition(">")
    return Author.from_string(head + ">")
