"""Render the book to a single self-contained HTML page.

We don't import any markdown library; the HTML is built by hand. The
resulting file is browse-able offline (it's how I email myself
snippets when I'm on a train).
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Iterable

from .snippet import Snippet


CODEC = "html"


_CSS = """\
body{font-family:-apple-system,system-ui,Segoe UI,Helvetica,Arial,sans-serif;
  margin:24px;max-width:860px;color:#222;line-height:1.45}
h1,h2{margin-top:1.6em}
h1{border-bottom:2px solid #ccc;padding-bottom:6px}
h2{border-bottom:1px solid #ddd;padding-bottom:4px}
pre{background:#f4f4f4;padding:12px;border-radius:6px;overflow:auto;
  font-family:Consolas,Menlo,monospace;font-size:13px;line-height:1.4}
code{font-family:Consolas,Menlo,monospace}
.tag{display:inline-block;background:#eef;color:#225;padding:1px 8px;
  border-radius:11px;font-size:12px;margin-right:4px}
.meta{color:#666;font-size:13px;margin-bottom:8px}
.toc a{display:block;padding:2px 0}
"""


def render(snippets: Iterable[Snippet], *, title: str = "snippetbox") -> str:
    snippets = list(snippets)
    parts: list = ["<!doctype html>", "<html>", "<head>"]
    parts.append("<meta charset=\"utf-8\">")
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(f"<style>{_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"<h1>{escape(title)}</h1>")
    if snippets:
        parts.append("<nav class=\"toc\">")
        for s in snippets:
            anchor = _anchor(s.slug or s.id)
            parts.append(
                f'<a href="#{anchor}">{escape(s.title or "(untitled)")}</a>'
            )
        parts.append("</nav>")
    for s in snippets:
        parts.append(_render_one(s))
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def _render_one(s: Snippet) -> str:
    out: list = []
    anchor = _anchor(s.slug or s.id)
    out.append(f'<section id="{anchor}">')
    out.append(f"<h2>{escape(s.title or '(untitled)')}</h2>")
    meta_parts: list = []
    if s.language and s.language != "plain":
        meta_parts.append(f"language: <code>{escape(s.language)}</code>")
    if s.author and s.author.display() not in {"", "anonymous"}:
        meta_parts.append("author: " + escape(s.author.display()))
    if meta_parts:
        out.append('<p class="meta">' + " &middot; ".join(meta_parts) + "</p>")
    if s.tags or s.auto_tags:
        out.append("<p>")
        for t in s.tags:
            out.append(f'<span class="tag">{escape(t)}</span>')
        for t in s.auto_tags:
            out.append(f'<span class="tag" style="background:#eee;color:#444">{escape(t)}</span>')
        out.append("</p>")
    out.append(
        "<pre><code>"
        + escape(s.body or "").rstrip()
        + "</code></pre>"
    )
    if s.notes:
        out.append(f'<p class="meta">notes: {escape(s.notes)}</p>')
    out.append("</section>")
    return "\n".join(out)


def _anchor(text: str) -> str:
    out: list = []
    for ch in (text or "").lower():
        if ch.isalnum() or ch == "-":
            out.append(ch)
        elif ch == " ":
            out.append("-")
    s = "".join(out).strip("-")
    return s or "snippet"


def export_to_file(snippets: Iterable[Snippet], path: Path, *, title: str = "snippetbox") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(snippets, title=title), encoding="utf-8")


def render_minimal(snippet: Snippet) -> str:
    return _render_one(snippet)


def render_index(snippets: Iterable[Snippet]) -> str:
    snippets = list(snippets)
    if not snippets:
        return "<p>(no snippets)</p>"
    items: list = []
    for s in snippets:
        anchor = _anchor(s.slug or s.id)
        items.append(f'<li><a href="#{anchor}">{escape(s.title or "(untitled)")}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"
