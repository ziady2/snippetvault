"""Import GitHub Gist JSON.

We don't talk to the GitHub API. The user feeds us a JSON file from
``gh gist view <id> --raw`` (or a saved single-gist JSON dump from
the github API). One gist usually has multiple files; each file
becomes a separate snippet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .author import Author
from .errors import IOFormatError
from .snippet import Snippet


CODEC = "gist"


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IOFormatError(CODEC, f"invalid JSON: {exc}") from exc
    if isinstance(data, list):
        out: list = []
        for entry in data:
            out.extend(_import_one(entry))
        return out
    if isinstance(data, dict):
        return _import_one(data)
    raise IOFormatError(CODEC, "unexpected JSON shape")


def _import_one(gist: dict) -> List[Snippet]:
    if not isinstance(gist, dict):
        return []
    files = gist.get("files") or {}
    if not isinstance(files, dict):
        return []
    description = (gist.get("description") or "").strip()
    owner = gist.get("owner") or {}
    author = Author(
        name=str(owner.get("login") or owner.get("name") or ""),
        url=str(owner.get("html_url") or owner.get("url") or ""),
    )
    snippets: list = []
    for filename, payload in files.items():
        if not isinstance(payload, dict):
            continue
        body = str(payload.get("content") or "")
        language = (payload.get("language") or "plain").lower()
        if " " in language:
            language = language.replace(" ", "")
        snippet = Snippet(
            title=str(filename),
            body=body,
            language=language or "plain",
            notes=description,
            source=str(gist.get("html_url") or ""),
            author=author,
        )
        snippets.append(snippet)
    return snippets


def export_snippets(snippets: Iterable[Snippet]) -> str:
    """Build a Gist-shaped JSON object from snippets.

    Useful for round-trip testing; not for posting to GitHub.
    """
    files: dict = {}
    for s in snippets:
        name = s.title or s.slug or (s.id + ".txt")
        files[name] = {
            "filename": name,
            "language": s.language or "plain",
            "content": s.body or "",
        }
    payload: dict = {
        "description": "exported from snippetbox",
        "files": files,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_to_file(snippets: Iterable[Snippet], path: Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(export_snippets(snippets), encoding="utf-8")


def import_from_file(path: Path) -> List[Snippet]:
    p = Path(path)
    if not p.exists():
        raise IOFormatError(CODEC, f"file not found: {path}")
    return import_snippets(p.read_text(encoding="utf-8"))
