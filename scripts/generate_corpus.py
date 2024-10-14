"""Generate import-format corpus fixtures.

We produce many small files in each of the import formats (markdown,
csv, vscode, gist json, textmate xml) so the test suite has a wide
variety of import inputs. The total bytes here are non-trivial.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

from snippetbox import io_csv, io_gist, io_markdown, io_textmate, io_vscode
from snippetbox.snippet import Snippet


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "imports"


SAMPLE_BODIES = (
    "import asyncio\nasync def foo(): await asyncio.sleep(0.1)",
    "function foo() { return Math.random(); }",
    "SELECT * FROM users WHERE active = TRUE;",
    "echo 'hello world'",
    "use std::io::Read;\nfn main() {}",
    "package main\nimport \"fmt\"\nfunc main() { fmt.Println(\"x\") }",
    "const fs = require('fs')",
    "<html><body>x</body></html>",
    "version: '3'\nservices: {}",
    "for i in range(10): print(i)",
)

SAMPLE_TITLES = (
    "tail a file", "merge two lists", "active users", "grep TODO",
    "rust hello", "go hello", "node fs", "html stub",
    "compose", "python loop",
)

SAMPLE_LANGUAGES = (
    "python", "javascript", "sql", "shell", "rust", "go",
    "javascript", "html", "yaml", "python",
)


def _make_snippet(rng: random.Random, idx: int) -> Snippet:
    title = rng.choice(SAMPLE_TITLES) + f" #{idx}"
    body = rng.choice(SAMPLE_BODIES)
    lang = rng.choice(SAMPLE_LANGUAGES)
    return Snippet(title=title, body=body, language=lang)


def _gist_payload(snippets: List[Snippet], idx: int) -> dict:
    files: Dict[str, dict] = {}
    for s in snippets:
        files[s.title] = {
            "filename": s.title,
            "language": s.language.title(),
            "content": s.body,
        }
    return {
        "description": f"corpus gist #{idx}",
        "html_url": f"https://gist.github.com/example/{idx}",
        "owner": {"login": "ziad", "html_url": "https://github.com/ziad"},
        "files": files,
    }


def write_format_corpus(format_name: str, *, count: int) -> int:
    out_dir = FIXTURES / format_name
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for i in range(count):
        rng = random.Random((hash(format_name) + i) & 0xFFFFFFFF)
        n_snips = rng.randint(2, 12)
        snippets = [_make_snippet(rng, j) for j in range(n_snips)]
        if format_name == "markdown":
            text = io_markdown.export_snippets(snippets)
            path = out_dir / f"notes-{i:04d}.md"
        elif format_name == "csv":
            text = io_csv.export_snippets(snippets)
            path = out_dir / f"notes-{i:04d}.csv"
        elif format_name == "vscode":
            text = io_vscode.export_snippets(snippets)
            path = out_dir / f"snippets-{i:04d}.json"
        elif format_name == "textmate":
            text = io_textmate.export_snippets(snippets)
            path = out_dir / f"bundle-{i:04d}.xml"
        elif format_name == "gist":
            payload = _gist_payload(snippets, i)
            text = json.dumps(payload, indent=2, ensure_ascii=False)
            path = out_dir / f"gist-{i:04d}.json"
        else:
            raise ValueError(format_name)
        path.write_text(text, encoding="utf-8")
        total += len(text.encode("utf-8"))
    return total


if __name__ == "__main__":
    formats = (
        ("markdown", 250),
        ("csv", 200),
        ("vscode", 180),
        ("textmate", 180),
        ("gist", 200),
    )
    grand = 0
    for fmt, n in formats:
        bytes_written = write_format_corpus(fmt, count=n)
        grand += bytes_written
        print(f"{fmt}: {n} files, {bytes_written} bytes")
    print(f"total: {grand} bytes")
