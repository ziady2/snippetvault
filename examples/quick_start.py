"""Smallest possible example: init a temp book, add one snippet, search.

Run with: ``python examples/quick_start.py``
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from snippetbox import search, storage
from snippetbox.snippet import Snippet


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        book_path = Path(td) / "book.json"
        book = storage.Book.init(book_path)

        body = (
            "import asyncio\n"
            "async def tail(path):\n"
            "    while True:\n"
            "        await asyncio.sleep(0.1)\n"
        )
        snippet = Snippet(
            title="tail a file",
            body=body,
            language="python",
            tags=["io", "async"],
        )
        book.add(snippet)
        book.save()

        hits = search.search(list(book), "asyncio")
        print(f"found {len(hits)} match(es) for 'asyncio'")
        for hit in hits:
            print(f"  - {hit.snippet.title} (score {hit.score:.2f})")


if __name__ == "__main__":
    main()
