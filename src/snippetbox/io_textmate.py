"""Import/export TextMate-style snippet bundles.

TextMate's bundle format is a folder of plist files. We don't write
plists; instead we use a tiny home-grown XML that several editors
already grok (notably Sublime Text and BBEdit's "snippet" import).

The format is:

::

    <snippets>
      <snippet>
        <name>...</name>
        <scope>source.python</scope>
        <content><![CDATA[...]]></content>
        <tabTrigger>foo</tabTrigger>
      </snippet>
      ...
    </snippets>
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List
from xml.sax.saxutils import escape, unescape

from .errors import IOFormatError
from .snippet import Snippet


CODEC = "textmate"

_SCOPE_PREFIX = "source."

_TAG_RE = re.compile(r"<(name|scope|content|tabTrigger)>(.*?)</\1>", re.DOTALL)


def _scope_for(language: str) -> str:
    if not language or language == "plain":
        return "text.plain"
    return _SCOPE_PREFIX + language


def _language_from_scope(scope: str) -> str:
    if not scope:
        return "plain"
    if scope.startswith(_SCOPE_PREFIX):
        return scope[len(_SCOPE_PREFIX):] or "plain"
    if scope.startswith("text."):
        return "plain"
    return scope


def export_snippets(snippets: Iterable[Snippet]) -> str:
    out: list = ["<snippets>"]
    for s in snippets:
        out.append("  <snippet>")
        out.append(f"    <name>{escape(s.title or s.slug or s.id)}</name>")
        out.append(f"    <scope>{escape(_scope_for(s.language))}</scope>")
        body = s.body or ""
        out.append(f"    <content><![CDATA[{body}]]></content>")
        if s.slug:
            out.append(f"    <tabTrigger>{escape(s.slug)}</tabTrigger>")
        out.append("  </snippet>")
    out.append("</snippets>")
    return "\n".join(out) + "\n"


def import_snippets(text: str) -> List[Snippet]:
    if not text:
        return []
    chunks: list = re.findall(r"<snippet>(.*?)</snippet>", text or "", re.DOTALL)
    out: list = []
    for chunk in chunks:
        fields: dict = {}
        # CDATA-aware extraction for <content>
        m_cdata = re.search(r"<content>\s*<!\[CDATA\[(.*?)\]\]>\s*</content>", chunk, re.DOTALL)
        if m_cdata:
            fields["content"] = m_cdata.group(1)
        for tag, value in _TAG_RE.findall(chunk):
            if tag == "content" and "content" in fields:
                continue
            fields[tag] = unescape(value).strip() if tag != "content" else unescape(value)
        if "content" not in fields:
            continue
        snippet = Snippet(
            title=fields.get("name", "").strip(),
            body=fields.get("content", ""),
            language=_language_from_scope(fields.get("scope", "")),
            slug=fields.get("tabTrigger", "").strip(),
        )
        out.append(snippet)
    if not chunks and "<snippet" in (text or ""):
        # we saw a `<snippet` somewhere but couldn't pair any of them
        # with a closing tag — that's a structurally broken bundle.
        raise IOFormatError(CODEC, "could not parse any <snippet> elements")
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
