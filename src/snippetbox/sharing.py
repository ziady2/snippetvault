"""Redaction and sharing profiles for exported snippets."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .snippet import Snippet


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_TOKEN_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd)\b\s*[:=]\s*([\"']?)([^\s\"']+)\2"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.DOTALL,
)


@dataclass(frozen=True)
class Redaction:
    field: str
    reason: str
    count: int = 1


@dataclass(frozen=True)
class SharingProfile:
    name: str = "safe"
    include_notes: bool = False
    include_source: bool = False
    include_author_name: bool = True
    include_author_email: bool = False
    include_private_tags: bool = False
    scan_secrets: bool = True
    private_tag_prefix: str = "private:"
    replacement: str = "[redacted]"

    def __post_init__(self) -> None:
        if not (self.name or "").strip():
            raise ValueError("sharing profile name is blank")
        if not self.replacement:
            raise ValueError("redaction replacement is blank")


@dataclass
class SharedSnippet:
    snippet: Snippet
    redactions: List[Redaction] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.redactions


def _redact_text(text: str, profile: SharingProfile) -> tuple[str, list[Redaction]]:
    if not profile.scan_secrets or not text:
        return text, []
    redactions: list[Redaction] = []
    private_keys = len(_PRIVATE_KEY_RE.findall(text))
    if private_keys:
        text = _PRIVATE_KEY_RE.sub(profile.replacement, text)
        redactions.append(Redaction("body", "private_key", private_keys))
    tokens = len(_TOKEN_RE.findall(text))
    if tokens:
        text = _TOKEN_RE.sub(lambda match: f"{match.group(1)}={profile.replacement}", text)
        redactions.append(Redaction("body", "credential", tokens))
    return text, redactions


def redact(snippet: Snippet, profile: Optional[SharingProfile] = None) -> SharedSnippet:
    profile = profile or SharingProfile()
    data = snippet.to_dict()
    redactions: list[Redaction] = []
    body, body_redactions = _redact_text(data.get("body", ""), profile)
    data["body"] = body
    redactions.extend(body_redactions)

    if not profile.include_notes and data.get("notes"):
        data["notes"] = ""
        redactions.append(Redaction("notes", "profile_excludes_notes"))
    if not profile.include_source and data.get("source"):
        data["source"] = ""
        redactions.append(Redaction("source", "profile_excludes_source"))

    author = dict(data.get("author") or {})
    if author:
        if not profile.include_author_name and author.get("name"):
            author["name"] = ""
            redactions.append(Redaction("author.name", "profile_excludes_author_name"))
        if not profile.include_author_email and author.get("email"):
            author["email"] = ""
            redactions.append(Redaction("author.email", "profile_excludes_author_email"))
        data["author"] = author

    prefix = profile.private_tag_prefix.lower()
    if not profile.include_private_tags:
        for key in ("tags", "auto_tags"):
            original = list(data.get(key) or [])
            data[key] = [tag for tag in original if not tag.lower().startswith(prefix)]
            removed = len(original) - len(data[key])
            if removed:
                redactions.append(Redaction(key, "private_tag", removed))
    data["extra"] = {}
    return SharedSnippet(snippet=Snippet.from_dict(data), redactions=redactions)


def redact_many(
    snippets: Iterable[Snippet], profile: Optional[SharingProfile] = None
) -> List[SharedSnippet]:
    return [redact(snippet, profile) for snippet in snippets]


def scan(snippet: Snippet) -> List[Redaction]:
    """Report potentially sensitive fields without changing the snippet."""
    findings: list[Redaction] = []
    if snippet.author.email:
        findings.append(Redaction("author.email", "personal_email"))
    if snippet.source:
        findings.append(Redaction("source", "source_location"))
    if snippet.notes:
        findings.append(Redaction("notes", "private_notes"))
    email_count = len(_EMAIL_RE.findall(snippet.body))
    if email_count:
        findings.append(Redaction("body", "email_address", email_count))
    token_count = len(_TOKEN_RE.findall(snippet.body))
    if token_count:
        findings.append(Redaction("body", "credential", token_count))
    key_count = len(_PRIVATE_KEY_RE.findall(snippet.body))
    if key_count:
        findings.append(Redaction("body", "private_key", key_count))
    private_tags = sum(1 for tag in snippet.all_tags() if tag.lower().startswith("private:"))
    if private_tags:
        findings.append(Redaction("tags", "private_tag", private_tags))
    return findings


def pseudonym(value: str, *, salt: str = "snippetbox", length: int = 12) -> str:
    if not 6 <= length <= 64:
        raise ValueError("pseudonym length must be between 6 and 64")
    digest = hashlib.sha256(f"{salt}\x00{value}".encode("utf-8")).hexdigest()
    return digest[:length]


def profile_to_dict(profile: SharingProfile) -> dict:
    return {name: getattr(profile, name) for name in SharingProfile.__dataclass_fields__}


def profile_from_dict(data: Mapping[str, object]) -> SharingProfile:
    allowed = set(SharingProfile.__dataclass_fields__)
    return SharingProfile(**{key: value for key, value in (data or {}).items() if key in allowed})


def redaction_summary(shared: Iterable[SharedSnippet]) -> Dict[str, int]:
    summary: dict[str, int] = {}
    for item in shared:
        for redaction in item.redactions:
            key = f"{redaction.field}:{redaction.reason}"
            summary[key] = summary.get(key, 0) + redaction.count
    return dict(sorted(summary.items()))
