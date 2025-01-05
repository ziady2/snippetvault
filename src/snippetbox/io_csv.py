"""CSV import/export.

Notion and Obsidian both export markdown notes with columns of
metadata. The CSV codec lets you ingest those.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Iterable, List

from .errors import IOFormatError
from .snippet import Snippet
from .tag import from_csv_cell, to_csv_cell


CODEC = "csv"

_FIELDS = ("id", "title", "language", "tags", "auto_tags", "slug", "source", "notes", "body")


def export_snippets(snippets: Iterable[Snippet]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_FIELDS)
    for s in snippets:
        writer.writerow(
            [
                s.id,
                s.title,
                s.language,
                to_csv_cell(s.tags),
                to_csv_cell(s.auto_tags),
                s.slug,
                s.source,
                (s.notes or "").replace("\n", "\\n"),
                (s.body or "").replace("\r\n", "\n"),
            ]
        )
    return buf.getvalue()


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    out: list = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise IOFormatError(CODEC, "no header row")
    expected = {"title", "body"}
    if not expected.issubset({f.lower() for f in reader.fieldnames}):
        raise IOFormatError(CODEC, "missing required columns: title, body")
    for row in reader:
        title = row.get("title") or ""
        body = (row.get("body") or "").replace("\r\n", "\n")
        snippet = Snippet(
            id=row.get("id") or "",
            title=title,
            body=body,
            language=row.get("language") or "plain",
            slug=row.get("slug") or "",
            source=row.get("source") or "",
            notes=(row.get("notes") or "").replace("\\n", "\n"),
            tags=from_csv_cell(row.get("tags") or ""),
            auto_tags=from_csv_cell(row.get("auto_tags") or ""),
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


def detect_dialect(text: str) -> str:
    """Best-guess CSV dialect: 'comma', 'semicolon', or 'tab'."""
    head = (text or "").splitlines()[0] if text else ""
    if "\t" in head:
        return "tab"
    if head.count(";") > head.count(","):
        return "semicolon"
    return "comma"
