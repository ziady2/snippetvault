"""Shared fixtures.

Most tests need a fresh ``Book`` to scribble in, plus a couple of
canned ``Snippet`` instances. This conftest defines those once.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from snippetbox import storage
from snippetbox.author import Author
from snippetbox.snippet import Snippet


@pytest.fixture
def tmp_book_path(tmp_path: Path) -> Path:
    return tmp_path / "book.json"


@pytest.fixture
def empty_book(tmp_book_path) -> storage.Book:
    return storage.Book.init(tmp_book_path)


@pytest.fixture
def python_snippet() -> Snippet:
    body = (
        "import asyncio\n"
        "async def tail(path):\n"
        "    while True:\n"
        "        await asyncio.sleep(0.1)\n"
    )
    return Snippet(
        title="tail a file",
        body=body,
        language="python",
        tags=["io", "async"],
    )


@pytest.fixture
def shell_snippet() -> Snippet:
    return Snippet(
        title="grep recursive",
        body="grep -rni 'TODO' .",
        language="shell",
        tags=["search"],
    )


@pytest.fixture
def sql_snippet() -> Snippet:
    body = "SELECT id, name FROM users WHERE active = TRUE\nORDER BY created_at DESC\nLIMIT 100;"
    return Snippet(
        title="recent active users",
        body=body,
        language="sql",
        tags=["query"],
        author=Author(name="A. User", email="a@example.com"),
    )


@pytest.fixture
def populated_book(tmp_book_path, python_snippet, shell_snippet, sql_snippet) -> storage.Book:
    book = storage.Book.init(tmp_book_path)
    book.add(python_snippet)
    book.add(shell_snippet)
    book.add(sql_snippet)
    book.save()
    return book


@pytest.fixture
def python_snippet_with_comments() -> Snippet:
    body = (
        "# tail a file by polling - not great but portable\n"
        "import time\n"
        "def tail(path):\n"
        "    with open(path) as f:\n"
        "        f.seek(0, 2)\n"
        "        while True:\n"
        "            line = f.readline()\n"
        "            if line:\n"
        "                yield line\n"
        "            else:\n"
        "                time.sleep(0.1)\n"
    )
    return Snippet(title="tail a file (sync)", body=body, language="python", tags=["io"])


@pytest.fixture
def js_snippet() -> Snippet:
    body = (
        "const tail = async (path) => {\n"
        "  // simple poll, no real fs.watch\n"
        "  while (true) await new Promise(r => setTimeout(r, 100));\n"
        "};\n"
    )
    return Snippet(title="poll a file (js)", body=body, language="javascript", tags=["io"])


@pytest.fixture
def book_dict_v0() -> dict:
    """A pre-1.0 book — bare list of snippets."""
    return [
        {"title": "x", "body": "print('hi')"},
        {"title": "y", "body": "echo hi", "language": "shell"},
    ]


@pytest.fixture
def book_dict_v1() -> dict:
    return {
        "schema_version": 1,
        "snippets": [
            {
                "id": "abc123",
                "title": "v1 sample",
                "body": "print(1)",
                "language": "python",
                "tags": ["sample", "auto:python"],
                "created_at": 0,
                "updated_at": 0,
            }
        ],
    }


@pytest.fixture
def write_book(tmp_path: Path):
    """Helper that writes a book dict to disk and returns the path."""

    def _write(data: dict, name: str = "book.json") -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    return _write
