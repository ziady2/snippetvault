"""Export the book as a folder-ish .zip.

Each snippet becomes a file inside the zip:

::

    book.zip
    ├── manifest.json
    └── snippets/
        ├── <slug>.<ext>
        ...

The manifest carries metadata; the individual files carry just the
body. Useful for handing snippets to non-Python people.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Iterable, List

from .errors import IOFormatError
from .language import by_name
from .snippet import Snippet
from .validators import is_safe_filename


CODEC = "zip"


def _ext_for(language: str) -> str:
    lang = by_name(language)
    return lang.extensions[0] if lang.extensions else ".txt"


def _safe_filename(slug: str, language: str) -> str:
    base = (slug or "snippet").lower()
    base = "".join(c for c in base if c.isalnum() or c == "-")
    if not base:
        base = "snippet"
    return base + _ext_for(language)


def export_to_bytes(snippets: Iterable[Snippet]) -> bytes:
    snippets = list(snippets)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"snippets": []}
        seen: dict = {}
        for s in snippets:
            name = _safe_filename(s.slug or s.id, s.language)
            n = 2
            while name in seen:
                stem, dot, ext = name.rpartition(".")
                name = (stem or name) + f"-{n}" + ((dot + ext) if dot else "")
                n += 1
            seen[name] = True
            zf.writestr(f"snippets/{name}", s.body or "")
            entry = s.to_dict()
            entry["filename"] = name
            manifest["snippets"].append(entry)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue()


def export_to_file(snippets: Iterable[Snippet], path: Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(export_to_bytes(snippets))


def import_from_bytes(data: bytes) -> List[Snippet]:
    out: list = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IOFormatError(CODEC, f"bad zip: {exc}") from exc
    if "manifest.json" not in zf.namelist():
        # treat every entry as a snippet, body = file contents
        for name in zf.namelist():
            if not is_safe_filename(name) or name.endswith("/"):
                continue
            body = zf.read(name).decode("utf-8", errors="replace")
            out.append(Snippet(title=name, body=body, language="plain"))
        return out
    try:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise IOFormatError(CODEC, f"manifest.json invalid: {exc}") from exc
    for entry in manifest.get("snippets", []):
        body_path = "snippets/" + (entry.get("filename") or "")
        if body_path in zf.namelist():
            entry["body"] = zf.read(body_path).decode("utf-8", errors="replace")
        out.append(Snippet.from_dict(entry))
    return out


def import_from_file(path: Path) -> List[Snippet]:
    p = Path(path)
    if not p.exists():
        raise IOFormatError(CODEC, f"file not found: {path}")
    return import_from_bytes(p.read_bytes())


def list_entries(data: bytes) -> List[str]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IOFormatError(CODEC, f"bad zip: {exc}") from exc
    return zf.namelist()
