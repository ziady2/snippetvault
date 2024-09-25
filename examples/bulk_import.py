"""Bulk-import every .py file in a directory as snippets.

Run with: ``python examples/bulk_import.py <folder>``
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from snippetbox import storage
from snippetbox.language import guess_from_filename
from snippetbox.snippet import Snippet


def main(folder: Path) -> int:
    if not folder.exists():
        print(f"no such folder: {folder}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as td:
        book_path = Path(td) / "book.json"
        book = storage.Book.init(book_path)
        added = 0
        for p in folder.rglob("*"):
            if not p.is_file():
                continue
            if p.stat().st_size > 200_000:
                continue
            try:
                body = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            language = guess_from_filename(p.name).name
            snippet = Snippet(
                title=p.stem,
                body=body,
                language=language,
                source=str(p),
            )
            try:
                book.add(snippet)
                added += 1
            except Exception as exc:  # noqa: BLE001
                print(f"skipped {p}: {exc}")
        book.save()
        print(f"imported {added} files into {book_path}")
        print(f"book size: {book_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    raise SystemExit(main(target))
