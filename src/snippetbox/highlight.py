"""Tiny syntax-classification helper.

Despite the name, this isn't a renderer. We classify each line as
``code`` / ``comment`` / ``blank`` / ``string`` so other modules can
ignore comments when fingerprinting/searching. Real syntax
highlighting lives in your editor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .language import Language, by_name


@dataclass
class Line:
    raw: str
    kind: str  # 'code' | 'comment' | 'blank' | 'string'

    def is_comment(self) -> bool:
        return self.kind == "comment"

    def is_blank(self) -> bool:
        return self.kind == "blank"


def classify_line(line: str, lang: Language) -> Line:
    if not line.strip():
        return Line(line, "blank")
    stripped = line.lstrip()
    token = lang.line_comment
    if token and stripped.startswith(token):
        return Line(line, "comment")
    open_, _close = (lang.block_comment + ("",))[:2] if lang.block_comment else ("", "")
    if open_ and stripped.startswith(open_):
        return Line(line, "comment")
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return Line(line, "string")
    return Line(line, "code")


def classify(text: str, language: str = "plain") -> List[Line]:
    lang = by_name(language)
    return [classify_line(line, lang) for line in (text or "").splitlines()]


def code_lines(text: str, language: str = "plain") -> List[str]:
    return [line.raw for line in classify(text, language) if line.kind == "code"]


def comment_lines(text: str, language: str = "plain") -> List[str]:
    return [line.raw for line in classify(text, language) if line.kind == "comment"]


def strip_comments(text: str, language: str = "plain") -> str:
    out: list = []
    for line in classify(text, language):
        if line.kind == "comment":
            continue
        out.append(line.raw)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def strip_blank_lines(text: str) -> str:
    out: list = []
    for line in (text or "").splitlines():
        if line.strip():
            out.append(line)
    return "\n".join(out)


def normalise_indent(text: str, *, tab_size: int = 4) -> str:
    """Replace tabs with ``tab_size`` spaces."""
    if not text:
        return ""
    return text.replace("\t", " " * tab_size)


def detect_shebang(text: str) -> Optional[str]:
    if not text:
        return None
    first = text.splitlines()[0] if "\n" in text or text else text
    if first.startswith("#!"):
        return first[2:].strip()
    return None


def is_likely_python(text: str) -> bool:
    sig: tuple = ("def ", "import ", "from ", "class ", "if __name__", "print(")
    head = (text or "")[:1000]
    return any(s in head for s in sig)


def is_likely_javascript(text: str) -> bool:
    sig: tuple = ("function ", "const ", "let ", "var ", "=>", "console.log")
    head = (text or "")[:1000]
    return any(s in head for s in sig)


def is_likely_shell(text: str) -> bool:
    if (text or "").startswith("#!/bin/"):
        return True
    sig: tuple = ("echo ", "if [", "then\n", "fi\n", "for i in")
    return any(s in (text or "") for s in sig)


def guess_language(text: str) -> str:
    """Cheap language guesser used when the user didn't tell us."""
    if not text:
        return "plain"
    if is_likely_python(text):
        return "python"
    if is_likely_javascript(text):
        return "javascript"
    if is_likely_shell(text):
        return "shell"
    if "<html" in (text or "").lower() or "<!doctype" in (text or "").lower():
        return "html"
    if (text or "").lstrip().startswith("{") and (text or "").rstrip().endswith("}"):
        return "json"
    return "plain"


def line_density(text: str, language: str = "plain") -> float:
    """Ratio of code lines to total non-blank lines. Used by ``lint``."""
    lines = classify(text, language)
    nonblank = [line for line in lines if line.kind != "blank"]
    if not nonblank:
        return 0.0
    code = [line for line in nonblank if line.kind == "code"]
    return len(code) / len(nonblank)


def code_token_count(text: str, language: str = "plain") -> int:
    total = 0
    for line in code_lines(text, language):
        total += len([t for t in line.split() if t])
    return total
