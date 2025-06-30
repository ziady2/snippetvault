"""Light-weight validators.

These return either ``None`` (valid) or a string error message. We
deliberately don't raise; the caller decides whether to bail or to
keep going with a warning.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from .language import is_known as language_is_known
from .tag import is_valid as tag_is_valid


_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


def validate_slug(slug: str) -> Optional[str]:
    if not slug:
        return "slug is empty"
    if len(slug) > 80:
        return "slug too long"
    if not _SLUG_RE.match(slug):
        return "slug must be lowercase a-z0-9-, no leading/trailing hyphens"
    return None


def validate_title(title: str) -> Optional[str]:
    if not title:
        return None  # title may be blank if body is non-empty
    if "\n" in title:
        return "title contains newline"
    if len(title) > 200:
        return "title longer than 200 chars"
    return None


def validate_language(name: str) -> Optional[str]:
    if not name:
        return "language is required"
    if not language_is_known(name):
        return f"unknown language: {name!r}"
    return None


def validate_tags(tags: Iterable[str]) -> Optional[str]:
    if tags is None:
        return None
    seen = set()
    for t in tags:
        if not tag_is_valid(t):
            return f"invalid tag: {t!r}"
        if t in seen:
            return f"duplicate tag: {t!r}"
        seen.add(t)
    return None


def validate_email(email: str) -> Optional[str]:
    if not email:
        return None  # email is optional
    if not _EMAIL_RE.match(email):
        return f"bad email: {email!r}"
    return None


def validate_url(url: str) -> Optional[str]:
    if not url:
        return None
    if not _URL_RE.match(url):
        return f"bad url: {url!r}"
    return None


def validate_body(body: str, *, min_chars: int = 0, max_chars: int = 200_000) -> Optional[str]:
    if body is None:
        return "body is None"
    if len(body) < min_chars:
        return f"body shorter than {min_chars} chars"
    if len(body) > max_chars:
        return f"body longer than {max_chars} chars"
    return None


def validate_collection_name(name: str) -> Optional[str]:
    if not name:
        return "collection name empty"
    if len(name) > 64:
        return "collection name too long"
    if any(ch in name for ch in "/\\"):
        return "collection name contains a slash"
    return None


def collect_errors(*results: Optional[str]) -> list:
    return [r for r in results if r]


def validate_snippet_dict(d: dict) -> list:
    errors: list = []
    if not isinstance(d, dict):
        return ["entry is not a dict"]
    errors.append(validate_title(d.get("title", "")))
    errors.append(validate_language(d.get("language", "")))
    errors.append(validate_tags(d.get("tags") or []))
    errors.append(validate_body(d.get("body", "")))
    if d.get("slug"):
        errors.append(validate_slug(d["slug"]))
    return collect_errors(*errors)


def is_safe_filename(name: str) -> bool:
    """Used by the io_zip codec when sanitising entries."""
    if not name:
        return False
    if name.startswith("/") or "\\" in name:
        return False
    if ".." in name.split("/"):
        return False
    return True


def validate_book(book: dict) -> list:
    out: list = []
    if not isinstance(book, dict):
        return ["book is not a dict"]
    if "snippets" not in book:
        out.append("missing key: snippets")
    else:
        if not isinstance(book["snippets"], list):
            out.append("snippets is not a list")
        else:
            slugs: dict = {}
            for i, s in enumerate(book["snippets"]):
                for err in validate_snippet_dict(s):
                    out.append(f"snippets[{i}]: {err}")
                slug = s.get("slug")
                if slug:
                    if slug in slugs:
                        out.append(f"snippets[{i}]: duplicate slug {slug!r}")
                    slugs[slug] = True
    return out


def is_blank(text: str) -> bool:
    return not (text or "").strip()


def first_error(*results: Optional[str]) -> Optional[str]:
    for r in results:
        if r:
            return r
    return None
