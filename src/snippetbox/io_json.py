"""JSON import/export.

The "native" format. Used by ``snippetbox export`` to dump the whole
book and by ``snippetbox import`` when given another book file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .errors import IOFormatError
from .snippet import Snippet


CODEC = "json"


def export_snippets(snippets: Iterable[Snippet], *, indent: int = 2) -> str:
    payload = {"snippets": [s.to_dict() for s in snippets]}
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IOFormatError(CODEC, f"invalid JSON: {exc}") from exc
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("snippets") or []
    else:
        raise IOFormatError(CODEC, "unexpected JSON shape")
    out: list = []
    for row in rows:
        if isinstance(row, dict):
            out.append(Snippet.from_dict(row))
    return out


def export_to_file(snippets: Iterable[Snippet], path: Path, *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(export_snippets(snippets, indent=indent), encoding="utf-8")


def import_from_file(path: Path) -> List[Snippet]:
    p = Path(path)
    if not p.exists():
        raise IOFormatError(CODEC, f"file not found: {path}")
    return import_snippets(p.read_text(encoding="utf-8"))


def round_trip(snippets: Iterable[Snippet]) -> List[Snippet]:
    """Encode + decode; mostly used by tests."""
    return import_snippets(export_snippets(snippets))


def write_pretty(snippets: Iterable[Snippet], path: Path) -> None:
    export_to_file(snippets, path, indent=4)


def write_compact(snippets: Iterable[Snippet], path: Path) -> None:
    export_to_file(snippets, path, indent=0)
