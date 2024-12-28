"""Stable identifiers and user-facing references.

Snippetbox stores opaque ids in the book, but commands and exports often need
references that are pleasant to type and safe to move between books.  This
module centralises the normalisation rules so importers, the query language and
future integrations do not each invent a slightly different spelling.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, Optional


_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")
_REFERENCE_RE = re.compile(r"^(?:(?P<namespace>[a-z][a-z0-9_-]*):)?(?P<value>[^\s:]+)$")


def ascii_fold(value: str) -> str:
    """Return a lowercase ASCII approximation suitable for identifiers."""
    normalised = unicodedata.normalize("NFKD", value or "")
    return normalised.encode("ascii", "ignore").decode("ascii").lower()


def slugify(value: str, *, max_length: int = 80, fallback: str = "") -> str:
    """Convert free text to a deterministic URL-safe slug."""
    if max_length < 1:
        raise ValueError("max_length must be positive")
    slug = _SEPARATOR_RE.sub("-", ascii_fold(value).strip()).strip("-")
    if not slug:
        slug = _SEPARATOR_RE.sub("-", ascii_fold(fallback).strip()).strip("-")
    return slug[:max_length].rstrip("-")


def content_id(*parts: object, length: int = 16, namespace: str = "") -> str:
    """Build a short stable id from a sequence of values.

    Lengths between 8 and 64 are accepted.  A namespace can be supplied to
    keep ids generated for different entity types from sharing a hash domain.
    """
    if not 8 <= length <= 64:
        raise ValueError("length must be between 8 and 64")
    digest = hashlib.sha256()
    digest.update((namespace or "").encode("utf-8"))
    for part in parts:
        digest.update(b"\x00")
        digest.update(str(part).encode("utf-8", errors="replace"))
    return digest.hexdigest()[:length]


@dataclass(frozen=True)
class Reference:
    """A parsed ``namespace:value`` reference."""

    value: str
    namespace: str = "snippet"

    def __post_init__(self) -> None:
        namespace = slugify(self.namespace, max_length=32)
        value = (self.value or "").strip()
        if not namespace:
            raise ValueError("reference namespace is blank")
        if not value or any(ch.isspace() for ch in value) or ":" in value:
            raise ValueError("reference value must be non-blank and contain no spaces or colons")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return f"{self.namespace}:{self.value}"

    @classmethod
    def parse(cls, text: str, *, default_namespace: str = "snippet") -> "Reference":
        match = _REFERENCE_RE.fullmatch((text or "").strip())
        if not match:
            raise ValueError(f"invalid reference: {text!r}")
        return cls(
            value=match.group("value"),
            namespace=match.group("namespace") or default_namespace,
        )


@dataclass
class AliasRegistry:
    """Case-insensitive aliases that resolve to canonical references."""

    _aliases: Dict[str, Reference] = field(default_factory=dict)

    @staticmethod
    def _key(alias: str) -> str:
        key = slugify(alias, max_length=80)
        if not key:
            raise ValueError("alias is blank")
        return key

    def add(self, alias: str, reference: Reference, *, replace: bool = False) -> bool:
        key = self._key(alias)
        if key in self._aliases and not replace:
            return False
        self._aliases[key] = reference
        return True

    def remove(self, alias: str) -> bool:
        return self._aliases.pop(self._key(alias), None) is not None

    def resolve(self, alias_or_reference: str) -> Optional[Reference]:
        text = (alias_or_reference or "").strip()
        if not text:
            return None
        alias = slugify(text, max_length=80)
        if alias in self._aliases:
            return self._aliases[alias]
        try:
            return Reference.parse(text)
        except ValueError:
            return None

    def aliases_for(self, reference: Reference) -> list[str]:
        return sorted(alias for alias, target in self._aliases.items() if target == reference)

    def items(self) -> Iterator[tuple[str, Reference]]:
        for alias in sorted(self._aliases):
            yield alias, self._aliases[alias]

    def to_dict(self) -> dict:
        return {alias: str(reference) for alias, reference in self.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "AliasRegistry":
        registry = cls()
        for alias, raw in (data or {}).items():
            try:
                registry.add(str(alias), Reference.parse(str(raw)), replace=True)
            except ValueError:
                continue
        return registry


def unique_slug(title: str, occupied: Iterable[str], *, fallback: str = "snippet") -> str:
    """Return a slug not already present in ``occupied``."""
    used = {str(value).lower() for value in occupied if value}
    base = slugify(title, fallback=fallback) or fallback
    if base.lower() not in used:
        return base
    number = 2
    while f"{base}-{number}".lower() in used:
        number += 1
    return f"{base}-{number}"


def compact_reference(reference: Reference, *, default_namespace: str = "snippet") -> str:
    """Hide the namespace when it is the caller's default."""
    if reference.namespace == slugify(default_namespace, max_length=32):
        return reference.value
    return str(reference)
