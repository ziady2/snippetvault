"""Portable manifests for snippet exports and attachment directories."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Mapping, Optional


MANIFEST_VERSION = 1


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalise_path(value: str) -> str:
    """Return a safe relative POSIX path or raise ``ValueError``."""
    path = PurePosixPath((value or "").replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"manifest path must be safe and relative: {value!r}")
    return str(path)


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str
    media_type: str = "application/octet-stream"
    role: str = "attachment"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalise_path(self.path))
        if self.size < 0:
            raise ValueError("manifest size must not be negative")
        if len(self.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.sha256.lower()):
            raise ValueError("manifest sha256 is invalid")

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256.lower(),
            "media_type": self.media_type,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ManifestEntry":
        return cls(
            path=str(data.get("path") or ""),
            size=int(data.get("size") or 0),
            sha256=str(data.get("sha256") or ""),
            media_type=str(data.get("media_type") or "application/octet-stream"),
            role=str(data.get("role") or "attachment"),
        )


@dataclass
class Manifest:
    entries: List[ManifestEntry] = field(default_factory=list)
    book_checksum: str = ""
    created_at: float = 0.0
    generator: str = "snippetbox"
    version: int = MANIFEST_VERSION

    def __post_init__(self) -> None:
        self.entries = list(self.entries)
        self.created_at = float(self.created_at)
        self.book_checksum = (self.book_checksum or "").lower()
        self.generator = str(self.generator or "snippetbox")

    def validate(self) -> List[str]:
        errors: list[str] = []
        if self.version != MANIFEST_VERSION:
            errors.append(f"unsupported manifest version {self.version}")
        seen: set[str] = set()
        for entry in self.entries:
            if entry.path in seen:
                errors.append(f"duplicate manifest path: {entry.path}")
            seen.add(entry.path)
        if self.book_checksum and len(self.book_checksum) != 64:
            errors.append("book checksum is invalid")
        return errors

    def digest(self) -> str:
        payload = self.to_dict()
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hash_bytes(encoded.encode("utf-8"))

    def total_size(self) -> int:
        return sum(entry.size for entry in self.entries)

    def by_role(self, role: str) -> List[ManifestEntry]:
        return [entry for entry in self.entries if entry.role == role]

    def get(self, path: str) -> Optional[ManifestEntry]:
        target = normalise_path(path)
        return next((entry for entry in self.entries if entry.path == target), None)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "generator": self.generator,
            "book_checksum": self.book_checksum,
            "entries": [entry.to_dict() for entry in sorted(self.entries, key=lambda item: item.path)],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Manifest":
        return cls(
            version=int(data.get("version") or MANIFEST_VERSION),
            created_at=float(data.get("created_at") or 0),
            generator=str(data.get("generator") or "snippetbox"),
            book_checksum=str(data.get("book_checksum") or ""),
            entries=[ManifestEntry.from_dict(item) for item in data.get("entries") or []],
        )

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("manifest root must be an object")
        return cls.from_dict(data)


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    path: str
    message: str


def entry_from_file(path: Path, *, root: Path, role: str = "attachment") -> ManifestEntry:
    path = Path(path)
    root = Path(root).resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"file is outside manifest root: {path}") from exc
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return ManifestEntry(
        path=relative.as_posix(),
        size=path.stat().st_size,
        sha256=hash_file(path),
        media_type=media_type,
        role=role,
    )


def build(root: Path, files: Iterable[Path], *, book_checksum: str = "", created_at: float = 0) -> Manifest:
    root = Path(root).resolve()
    entries = [entry_from_file(path, root=root) for path in files]
    entries.sort(key=lambda entry: entry.path)
    return Manifest(entries=entries, book_checksum=book_checksum, created_at=created_at)


def verify(root: Path, manifest: Manifest, *, reject_extra: bool = False) -> List[VerificationIssue]:
    root = Path(root).resolve()
    issues: list[VerificationIssue] = []
    expected_paths = {entry.path for entry in manifest.entries}
    for error in manifest.validate():
        issues.append(VerificationIssue("invalid_manifest", "", error))
    for entry in manifest.entries:
        path = (root / Path(entry.path)).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            issues.append(VerificationIssue("unsafe_path", entry.path, "entry escapes manifest root"))
            continue
        if not path.is_file():
            issues.append(VerificationIssue("missing", entry.path, "file is missing"))
            continue
        actual_size = path.stat().st_size
        if actual_size != entry.size:
            issues.append(
                VerificationIssue("size_mismatch", entry.path, f"expected {entry.size}, got {actual_size}")
            )
            continue
        actual_hash = hash_file(path)
        if actual_hash != entry.sha256:
            issues.append(VerificationIssue("checksum_mismatch", entry.path, "sha256 differs"))
    if reject_extra:
        for path in root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                if relative not in expected_paths:
                    issues.append(VerificationIssue("extra", relative, "file is not listed in manifest"))
    return sorted(issues, key=lambda issue: (issue.path, issue.code))
