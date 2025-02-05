"""Language metadata for snippets.

I keep this dead simple on purpose: a curated list of languages I
actually use, plus a few aliases. If you write Forth, sorry, open a
PR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Language:
    """A programming language entry."""

    name: str
    extensions: tuple = ()
    line_comment: str = "#"
    block_comment: tuple = ()  # (open, close)
    aliases: tuple = ()
    family: str = "other"

    def matches(self, text: str) -> bool:
        # case-insensitive match against name + aliases
        t = text.lower().strip()
        if t == self.name.lower():
            return True
        return t in {a.lower() for a in self.aliases}


# the canonical table. Order matters because we use the first match
# when guessing language from extension.
_LANGUAGES: tuple = (
    Language("python",     extensions=(".py", ".pyi"),       line_comment="#",    aliases=("py", "python3"),    family="dynamic"),
    Language("javascript", extensions=(".js", ".mjs", ".cjs"),line_comment="//",  block_comment=("/*", "*/"),  aliases=("js", "node"),       family="dynamic"),
    Language("typescript", extensions=(".ts",),               line_comment="//",  block_comment=("/*", "*/"),  aliases=("ts",),              family="dynamic"),
    Language("ruby",       extensions=(".rb",),               line_comment="#",   aliases=("rb",),              family="dynamic"),
    Language("go",         extensions=(".go",),               line_comment="//",  block_comment=("/*", "*/"),  family="static"),
    Language("rust",       extensions=(".rs",),               line_comment="//",  block_comment=("/*", "*/"),  aliases=("rs",),              family="static"),
    Language("java",       extensions=(".java",),             line_comment="//",  block_comment=("/*", "*/"),  family="static"),
    Language("kotlin",     extensions=(".kt", ".kts"),        line_comment="//",  block_comment=("/*", "*/"),  aliases=("kt",),              family="static"),
    Language("c",          extensions=(".c", ".h"),           line_comment="//",  block_comment=("/*", "*/"),  family="static"),
    Language("cpp",        extensions=(".cpp", ".hpp", ".cc"),line_comment="//",  block_comment=("/*", "*/"),  aliases=("c++", "cxx"),       family="static"),
    Language("csharp",     extensions=(".cs",),               line_comment="//",  block_comment=("/*", "*/"),  aliases=("c#",),              family="static"),
    Language("shell",      extensions=(".sh", ".bash"),       line_comment="#",   aliases=("bash", "sh"),       family="shell"),
    Language("powershell", extensions=(".ps1", ".psm1"),      line_comment="#",   aliases=("ps1", "pwsh"),      family="shell"),
    Language("sql",        extensions=(".sql",),              line_comment="--",  block_comment=("/*", "*/"),  family="data"),
    Language("html",       extensions=(".html", ".htm"),      line_comment="",    block_comment=("<!--", "-->"), family="markup"),
    Language("css",        extensions=(".css",),              line_comment="",    block_comment=("/*", "*/"),  family="markup"),
    Language("yaml",       extensions=(".yaml", ".yml"),      line_comment="#",   aliases=("yml",),             family="data"),
    Language("toml",       extensions=(".toml",),             line_comment="#",   family="data"),
    Language("json",       extensions=(".json",),             line_comment="",    family="data"),
    Language("markdown",   extensions=(".md", ".markdown"),   line_comment="",    aliases=("md",),              family="markup"),
    Language("dockerfile", extensions=(".dockerfile",),       line_comment="#",   aliases=("docker",),          family="config"),
    Language("makefile",   extensions=(".mk",),               line_comment="#",   aliases=("make",),            family="config"),
    Language("nix",        extensions=(".nix",),              line_comment="#",   family="config"),
    Language("regex",      extensions=(),                     line_comment="",    aliases=("re", "regexp"),     family="other"),
    Language("plain",      extensions=(".txt",),              line_comment="",    aliases=("text",),            family="other"),
)


def all_languages() -> tuple:
    """Return the static table of supported languages."""
    return _LANGUAGES


def by_name(name: str) -> Language:
    """Look up a language by name or alias. Falls back to ``plain``."""
    if not name:
        return get_plain()
    for lang in _LANGUAGES:
        if lang.matches(name):
            return lang
    return get_plain()


def by_extension(ext: str) -> Language:
    """Map a file extension (.py) to a Language. Falls back to ``plain``."""
    if not ext:
        return get_plain()
    e = ext.lower()
    if not e.startswith("."):
        e = "." + e
    for lang in _LANGUAGES:
        if e in lang.extensions:
            return lang
    return get_plain()


def get_plain() -> Language:
    return _LANGUAGES[-1]


def family(lang: Language) -> str:
    return lang.family


def names() -> list:
    return [language.name for language in _LANGUAGES]


def is_known(name: str) -> bool:
    if not name:
        return False
    for lang in _LANGUAGES:
        if lang.matches(name):
            return True
    return False


def comment_token(lang: Language) -> str:
    """Best line-comment token for a language. Empty string when none exists."""
    return lang.line_comment


def block_tokens(lang: Language):
    return tuple(lang.block_comment)


def filter_by_family(fam: str) -> list:
    return [language for language in _LANGUAGES if language.family == fam]


def guess_from_filename(name: str) -> Language:
    """Pick a language by the *last* extension in a filename."""
    if "." not in name:
        return get_plain()
    ext = "." + name.rsplit(".", 1)[1]
    return by_extension(ext)


def normalise_name(name: str) -> str:
    """Return the canonical name for a language alias (or '' if unknown)."""
    lang = by_name(name)
    if lang is get_plain() and (name or "").lower() != "plain":
        return ""
    return lang.name


def suggest(prefix: str, *, limit: int = 5) -> list:
    # Used by the CLI tab-completion helper.
    p = prefix.lower()
    out = []
    for lang in _LANGUAGES:
        if lang.name.lower().startswith(p):
            out.append(lang.name)
        else:
            for a in lang.aliases:
                if a.lower().startswith(p):
                    out.append(lang.name)
                    break
        if len(out) >= limit:
            break
    return out


def families() -> list:
    seen = []
    for language in _LANGUAGES:
        if language.family not in seen:
            seen.append(language.family)
    return seen


def from_iterable(values: Iterable) -> list:
    """Resolve an iterable of names to Language objects, dropping unknowns."""
    out = []
    for v in values:
        lang = by_name(v)
        if lang.name == "plain" and (v or "").lower() != "plain":
            continue
        out.append(lang)
    return out
