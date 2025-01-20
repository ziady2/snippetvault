"""Import/export snippets in markdown.

The format is one snippet per ``# heading`` block, with a fenced code
block for the body. Optional metadata lines between heading and code
fence are recognised:

::

    # Tail a file
    - language: python
    - tags: io, async
    ```python
    ...
    ```

Round-tripping is best-effort.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

from .errors import IOFormatError
from .markdown_render import render_many
from .snippet import Snippet
from .tag import parse as parse_tags

CODEC = "markdown"

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$")
_META_RE = re.compile(r"^-\s+([a-z\-]+):\s*(.*)$", re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(\w*)\s*$")


def export_snippets(snippets: Iterable[Snippet]) -> str:
    return render_many(snippets, include_meta=True, include_toc=False)


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    out: list = []
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _HEADING_RE.match(line)
        if not m:
            i += 1
            continue
        title = m.group(1).strip()
        i += 1
        meta: dict = {}
        while i < n and (not lines[i].strip() or _META_RE.match(lines[i])):
            mm = _META_RE.match(lines[i])
            if mm:
                meta[mm.group(1).lower()] = mm.group(2).strip()
            i += 1
        # collect any blank lines before fence
        while i < n and not lines[i].strip():
            i += 1
        if i >= n:
            break
        f = _FENCE_RE.match(lines[i])
        if not f:
            # not a fenced block right after heading; skip this snippet
            continue
        lang = (f.group(1) or "").strip().lower() or meta.get("language", "plain")
        i += 1
        body_lines: list = []
        while i < n and not lines[i].startswith("```"):
            body_lines.append(lines[i])
            i += 1
        if i < n:
            i += 1  # consume closing fence
        body = "\n".join(body_lines)
        snippet = Snippet(title=title, body=body, language=lang)
        if "tags" in meta:
            # strip backticks because the export wraps each tag in `...`
            snippet.tags = parse_tags(meta["tags"].replace("`", ""))
        if "auto-tags" in meta:
            snippet.auto_tags = parse_tags(meta["auto-tags"].replace("`", ""))
        if "source" in meta:
            snippet.source = meta["source"]
        if "notes" in meta:
            snippet.notes = meta["notes"]
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


def split_codefences(text: str) -> List[str]:
    """Return the contents of every ```...``` fence in ``text``."""
    fences: list = []
    in_fence = False
    buf: list = []
    for line in (text or "").splitlines():
        if line.startswith("```"):
            if in_fence:
                fences.append("\n".join(buf))
                buf = []
            in_fence = not in_fence
            continue
        if in_fence:
            buf.append(line)
    if in_fence and buf:
        # unterminated fence; still keep contents
        fences.append("\n".join(buf))
    return fences
