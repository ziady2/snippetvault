"""Import/export VSCode user-snippets.

VSCode's format is a JSON object keyed by snippet name. Each value
has ``prefix``, ``body`` (a list of lines OR a string), ``description``,
and optionally ``scope`` (a comma-separated language list).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .errors import IOFormatError
from .snippet import Snippet


CODEC = "vscode"


def export_snippets(snippets: Iterable[Snippet]) -> str:
    payload: dict = {}
    used: set = set()
    for s in snippets:
        name = s.title or s.slug or s.id
        base = name
        n = 2
        while name in used:
            name = f"{base} ({n})"
            n += 1
        used.add(name)
        body = (s.body or "").splitlines()
        entry: dict = {
            "prefix": s.slug or s.id[:8],
            "body": body if len(body) > 1 else (body[0] if body else ""),
            "description": s.notes or s.title or "",
        }
        if s.language:
            entry["scope"] = s.language
        payload[name] = entry
    return json.dumps(payload, indent=2, ensure_ascii=False)


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IOFormatError(CODEC, f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise IOFormatError(CODEC, "expected an object")
    out: list = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        body = entry.get("body")
        if isinstance(body, list):
            body_text = "\n".join(str(b) for b in body)
        else:
            body_text = str(body or "")
        scope = entry.get("scope") or ""
        primary_lang = scope.split(",", 1)[0].strip() if scope else "plain"
        snippet = Snippet(
            title=str(name),
            body=body_text,
            language=primary_lang or "plain",
            notes=str(entry.get("description") or ""),
        )
        out.append(snippet)
    return out


def export_to_file(snippets: Iterable[Snippet], path: Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(export_snippets(snippets), encoding="utf-8")


def import_from_file(path: Path) -> List[Snippet]:
    p = Path(path)
    if not p.exists():
        raise IOFormatError(CODEC, f"file not found: {path}")
    return import_snippets(p.read_text(encoding="utf-8"))
