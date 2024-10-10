"""Interactive-ish demo showing all three search modes side by side."""

from __future__ import annotations

import tempfile
from pathlib import Path

from snippetbox import search, storage
from snippetbox.snippet import Snippet


def _seed(book: storage.Book) -> None:
    rows = [
        ("Tail a file (asyncio)", "import asyncio\nawait asyncio.sleep(0.1)", "python", ["io", "async"]),
        ("Recursive grep", "grep -rni 'TODO' .", "shell", ["search"]),
        ("Active users SQL", "SELECT * FROM users WHERE active = TRUE;", "sql", ["query"]),
        ("HTTP fetch in JS", "const r = await fetch('/api/x');", "javascript", ["http"]),
        ("Prime sieve", "primes = [n for n in range(2, 100) if all(n%i for i in range(2, int(n**0.5)+1))]", "python", ["math"]),
    ]
    for title, body, lang, tags in rows:
        book.add(Snippet(title=title, body=body, language=lang, tags=tags))


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        book_path = Path(td) / "book.json"
        book = storage.Book.init(book_path)
        _seed(book)
        book.save()

        for query, mode in [
            ("asyncio", "substring"),
            ("tail file", "token"),
            ("asyncii", "fuzzy"),
            ("primes", "token"),
            ("nope-not-here", "token"),
        ]:
            hits = search.search(list(book), query, mode=mode)
            print(f"-- {mode!r} query={query!r} -> {len(hits)} hit(s)")
            for h in hits:
                print(f"   {h.snippet.title}  (score {h.score:.2f})")


if __name__ == "__main__":
    main()
