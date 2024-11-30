"""User config.

Read from ``~/.snippetbox/config.toml`` if it exists. Falls back to
sane defaults. The CLI exposes most of these via flags too, but the
config lets you avoid retyping ``--book ...`` every time.

We deliberately use a tiny parser for the subset of TOML represented by the
configuration file. This keeps configuration deterministic and avoids making
the behaviour depend on optional parser packages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import ConfigError


_DEFAULT = {
    "book_path": "~/.snippetbox/book.json",
    "editor": "",
    "default_language": "plain",
    "default_format": "text",
    "audit_enabled": False,
    "server_host": "127.0.0.1",
    "server_port": 8765,
    "auto_tag": True,
}


@dataclass
class Config:
    book_path: str = _DEFAULT["book_path"]  # type: ignore[assignment]
    editor: str = ""
    default_language: str = _DEFAULT["default_language"]  # type: ignore[assignment]
    default_format: str = _DEFAULT["default_format"]  # type: ignore[assignment]
    audit_enabled: bool = False
    server_host: str = _DEFAULT["server_host"]  # type: ignore[assignment]
    server_port: int = int(_DEFAULT["server_port"])  # type: ignore[arg-type]
    auto_tag: bool = True

    def book_resolved(self) -> Path:
        return Path(os.path.expanduser(self.book_path))


def default_config_path() -> Path:
    return Path.home() / ".snippetbox" / "config.toml"


def load(path: Optional[Path] = None) -> Config:
    p = Path(path) if path else default_config_path()
    if not p.exists():
        return _from_environ()
    raw = p.read_text(encoding="utf-8")
    parsed = _parse(raw)
    return _merge(_from_environ(), parsed)


def save(config: Config, path: Optional[Path] = None) -> Path:
    p = Path(path) if path else default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_render(config), encoding="utf-8")
    return p


def _from_environ() -> Config:
    cfg = Config()
    if "SNIPPETBOX_BOOK" in os.environ:
        cfg.book_path = os.environ["SNIPPETBOX_BOOK"]
    if "SNIPPETBOX_EDITOR" in os.environ:
        cfg.editor = os.environ["SNIPPETBOX_EDITOR"]
    elif "EDITOR" in os.environ:
        cfg.editor = os.environ["EDITOR"]
    return cfg


def _merge(base: Config, overrides: dict) -> Config:
    cfg = Config(**base.__dict__)
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            continue
        setattr(cfg, k, v)
    return cfg


def _parse(text: str) -> dict:
    """A very small TOML subset: bare ``key = value`` lines, ``[section]`` headers."""
    out: dict = {}
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            value: object = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            value = val[1:-1]
        elif val.lower() in {"true", "false"}:
            value = val.lower() == "true"
        else:
            try:
                value = int(val)
            except ValueError:
                try:
                    value = float(val)
                except ValueError:
                    value = val
        full = f"{section}.{key}" if section else key
        flat = full.split(".")[-1]
        out[flat] = value
    return out


def _render(cfg: Config) -> str:
    out: list = ["# snippetbox config", ""]
    for k in (
        "book_path",
        "editor",
        "default_language",
        "default_format",
        "audit_enabled",
        "server_host",
        "server_port",
        "auto_tag",
    ):
        v = getattr(cfg, k)
        if isinstance(v, bool):
            out.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{k} = {v}")
        else:
            out.append(f'{k} = "{v}"')
    return "\n".join(out) + "\n"


def validate(cfg: Config) -> list:
    errors: list = []
    if not cfg.book_path:
        errors.append("book_path is empty")
    if cfg.server_port < 1 or cfg.server_port > 65535:
        errors.append(f"server_port out of range: {cfg.server_port}")
    if cfg.default_format not in {"text", "json", "markdown", "html"}:
        errors.append(f"unknown default_format: {cfg.default_format!r}")
    return errors


def reset() -> Config:
    return Config()


def from_dict(data: dict) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("config is not a dict")
    return _merge(Config(), data)
