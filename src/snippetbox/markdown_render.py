"""Render snippets to markdown.

Used by ``snippetbox show --format markdown`` and by the static-site
exporter in ``io_html``. Hand-rolled; no jinja, no markdown library.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .snippet import Snippet


def render_one(snippet: Snippet, *, include_meta: bool = True) -> str:
    parts: list = []
    title = snippet.title or "(untitled)"
    parts.append(f"# {title}\n")
    if include_meta:
        meta_lines: list = []
        if snippet.language and snippet.language != "plain":
            meta_lines.append(f"- language: `{snippet.language}`")
        if snippet.tags:
            meta_lines.append("- tags: " + ", ".join(f"`{t}`" for t in snippet.tags))
        if snippet.auto_tags:
            meta_lines.append("- auto-tags: " + ", ".join(f"`{t}`" for t in snippet.auto_tags))
        if snippet.author and snippet.author.display() not in {"", "anonymous"}:
            meta_lines.append(f"- author: {snippet.author.display()}")
        if snippet.source:
            meta_lines.append(f"- source: {snippet.source}")
        if snippet.notes:
            meta_lines.append(f"- notes: {snippet.notes}")
        if meta_lines:
            parts.append("\n".join(meta_lines))
            parts.append("")
    fence_lang = snippet.language if snippet.language and snippet.language != "plain" else ""
    parts.append(f"```{fence_lang}".rstrip())
    parts.append(snippet.body or "")
    parts.append("```")
    return "\n".join(parts).rstrip() + "\n"


def render_many(
    snippets: Iterable,
    *,
    include_meta: bool = True,
    include_toc: bool = False,
    title: str = "Snippets",
) -> str:
    snippets = list(snippets)
    out: list = [f"# {title}\n"]
    if include_toc and snippets:
        out.append("## Contents\n")
        for s in snippets:
            anchor = _anchor(s.title or s.slug or s.id)
            out.append(f"- [{s.title or '(untitled)'}](#{anchor})")
        out.append("")
    for s in snippets:
        out.append(render_one(s, include_meta=include_meta).rstrip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _anchor(text: str) -> str:
    if not text:
        return ""
    out: list = []
    for ch in text.lower():
        if ch.isalnum() or ch == "-":
            out.append(ch)
        elif ch == " ":
            out.append("-")
        # else drop
    return "".join(out).strip("-")


def code_fence(language: str, body: str) -> str:
    lang = language if language and language != "plain" else ""
    return f"```{lang}\n{body or ''}\n```"


def inline_code(text: str) -> str:
    if "`" in text:
        return f"`` {text} ``"
    return f"`{text}`"


def render_minimal(snippet: Snippet) -> str:
    """Bare-bones render: just the code fence. No title, no metadata."""
    return code_fence(snippet.language, snippet.body or "")


def link(text: str, url: str) -> str:
    safe = text.replace("[", "\\[").replace("]", "\\]")
    return f"[{safe}]({url})"


def render_table(rows: Iterable[Iterable], headers: Optional[Iterable] = None) -> str:
    rows = [[str(c) for c in r] for r in rows]
    headers = list(headers or [])
    if headers and not rows:
        rows = []
    out: list = []
    if headers:
        out.append("| " + " | ".join(headers) + " |")
        out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def bulleted(items: Iterable) -> str:
    return "\n".join(f"- {item}" for item in items)


def heading(text: str, level: int = 1) -> str:
    if level < 1:
        level = 1
    if level > 6:
        level = 6
    return ("#" * level) + " " + text


def render_for_static_site(snippet: Snippet) -> str:
    """Like ``render_one`` but with a stable front-matter block.

    Used by ``io_html`` to feed static-site generators if anyone
    wants that.
    """
    fm: list = ["---"]
    fm.append(f"title: {snippet.title or '(untitled)'}")
    fm.append(f"slug: {snippet.slug}")
    fm.append(f"language: {snippet.language}")
    if snippet.tags:
        fm.append("tags: [" + ", ".join(f'"{t}"' for t in snippet.tags) + "]")
    fm.append("---\n")
    body = render_one(snippet, include_meta=False)
    return "\n".join(fm) + body
