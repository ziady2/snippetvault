r"""Parameterised snippet templates.

Templates use ``${name}`` placeholders and support defaults with
``${name:-default}``. A backslash escapes the next character, so
``\${literal}`` is emitted without interpolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .snippet import Snippet


_PLACEHOLDER_RE = re.compile(
    r"(?<!\\)\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}"
)


@dataclass(frozen=True)
class Variable:
    name: str
    default: Optional[str] = None
    occurrences: int = 1

    @property
    def required(self) -> bool:
        return self.default is None


@dataclass
class RenderResult:
    text: str
    values: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    unused: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing

    def require_complete(self) -> str:
        if self.missing:
            raise ValueError("missing template variables: " + ", ".join(self.missing))
        return self.text


def variables(text: str) -> List[Variable]:
    found: dict[str, dict] = {}
    order: list[str] = []
    for match in _PLACEHOLDER_RE.finditer(text or ""):
        name = match.group("name")
        default = match.group("default")
        if name not in found:
            found[name] = {"default": default, "occurrences": 0}
            order.append(name)
        elif found[name]["default"] is None and default is not None:
            found[name]["default"] = default
        found[name]["occurrences"] += 1
    return [
        Variable(name=name, default=found[name]["default"], occurrences=found[name]["occurrences"])
        for name in order
    ]


def render(text: str, values: Mapping[str, object], *, strict: bool = True) -> RenderResult:
    supplied = {str(name): str(value) for name, value in (values or {}).items()}
    used: set[str] = set()
    missing: list[str] = []

    def replace(match: re.Match) -> str:
        name = match.group("name")
        default = match.group("default")
        if name in supplied:
            used.add(name)
            return supplied[name]
        if default is not None:
            return default
        if name not in missing:
            missing.append(name)
        return match.group(0) if strict else ""

    rendered = _PLACEHOLDER_RE.sub(replace, text or "").replace(r"\${", "${")
    result = RenderResult(
        text=rendered,
        values={name: supplied[name] for name in sorted(used)},
        missing=missing,
        unused=sorted(set(supplied) - used),
    )
    return result


def parse_assignments(items: Iterable[str]) -> Dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"template assignment must be NAME=VALUE: {item!r}")
        name, value = item.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"invalid template variable name: {name!r}")
        values[name] = value
    return values


@dataclass
class SnippetTemplate:
    name: str
    body: str
    title: str = ""
    language: str = "plain"
    tags: List[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag and tag.strip()))
        if not self.name:
            raise ValueError("template name is blank")

    def variables(self) -> List[Variable]:
        combined = "\n".join((self.title, self.body))
        return variables(combined)

    def instantiate(
        self,
        values: Mapping[str, object],
        *,
        source: str = "",
        strict: bool = True,
    ) -> Snippet:
        title_result = render(self.title, values, strict=strict)
        body_result = render(self.body, values, strict=strict)
        missing = list(dict.fromkeys(title_result.missing + body_result.missing))
        if strict and missing:
            raise ValueError("missing template variables: " + ", ".join(missing))
        return Snippet(
            title=title_result.text,
            body=body_result.text,
            language=self.language,
            tags=list(self.tags),
            source=source or f"template:{self.name}",
            extra={"template": self.name, "template_values": {k: str(v) for k, v in values.items()}},
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "body": self.body,
            "language": self.language,
            "tags": list(self.tags),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SnippetTemplate":
        return cls(
            name=data.get("name", ""),
            title=data.get("title", ""),
            body=data.get("body", ""),
            language=data.get("language", "plain"),
            tags=list(data.get("tags") or []),
            description=data.get("description", ""),
        )


class TemplateLibrary:
    def __init__(self, templates: Iterable[SnippetTemplate] = ()) -> None:
        self._templates: dict[str, SnippetTemplate] = {}
        for template in templates:
            self.add(template)

    @staticmethod
    def _key(name: str) -> str:
        return (name or "").strip().lower()

    def add(self, template: SnippetTemplate, *, replace: bool = False) -> bool:
        key = self._key(template.name)
        if key in self._templates and not replace:
            return False
        self._templates[key] = template
        return True

    def get(self, name: str) -> Optional[SnippetTemplate]:
        return self._templates.get(self._key(name))

    def remove(self, name: str) -> bool:
        return self._templates.pop(self._key(name), None) is not None

    def names(self) -> list[str]:
        return sorted(template.name for template in self._templates.values())

    def instantiate(self, name: str, values: Mapping[str, object], **kwargs) -> Snippet:
        template = self.get(name)
        if template is None:
            raise KeyError(f"template not found: {name}")
        return template.instantiate(values, **kwargs)

    def to_list(self) -> list[dict]:
        return [self._templates[key].to_dict() for key in sorted(self._templates)]

    @classmethod
    def from_list(cls, data: Iterable[dict]) -> "TemplateLibrary":
        templates: list[SnippetTemplate] = []
        for item in data or []:
            try:
                templates.append(SnippetTemplate.from_dict(item))
            except (TypeError, ValueError):
                continue
        return cls(templates)
