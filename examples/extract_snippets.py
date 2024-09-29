"""Extract every fenced code block from a markdown document into snippets.

Run with: ``python examples/extract_snippets.py <file.md>``
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from snippetbox import storage
from snippetbox.snippet import Snippet


_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def _extract(text: str) -> list:
    out: list = []
    for m in _FENCE_RE.finditer(text):
        lang = (m.group(1) or "plain").lower()
        body = m.group(2).rstrip()
        out.append(Snippet(title=lang + " block", body=body, language=lang))
    return out


def main(path: Path) -> int:
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    snippets = _extract(text)
    if not snippets:
        print("no fenced code blocks found")
        return 0
    with tempfile.TemporaryDirectory() as td:
        book_path = Path(td) / "book.json"
        book = storage.Book.init(book_path)
        for s in snippets:
            try:
                book.add(s)
            except Exception as exc:  # noqa: BLE001
                print(f"skipped: {exc}")
        book.save()
        print(f"extracted {len(snippets)} snippets into {book_path}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("README.md")
    raise SystemExit(main(target))
