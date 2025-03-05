"""Generic input parsing utilities.

These helpers don't know about any particular import format; they
just turn dirty user-supplied strings into typed values. The codec
modules call into here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple


_DATE_FORMATS: tuple = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%d-%b-%Y",
    "%d %b %Y",
)


def parse_date(raw: str) -> Optional[datetime]:
    """Best-effort date parsing.

    Returns ``None`` if nothing matched. We don't try to be clever
    about ambiguous DD/MM vs MM/DD.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # ISO with timezone offsets like "+02:00" - python's fromisoformat
    # handles those on 3.11+; we backstop manually for older ones
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        # FIXME: parse_date treats DD/MM and MM/DD ambiguously when both are valid
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def parse_int(raw, *, default: Optional[int] = None) -> Optional[int]:
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def parse_float(raw, *, default: Optional[float] = None) -> Optional[float]:
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


def parse_bool(raw) -> Optional[bool]:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in {"y", "yes", "t", "true", "1", "on"}:
        return True
    if s in {"n", "no", "f", "false", "0", "off"}:
        return False
    return None


def split_lines(text: str) -> List[str]:
    if not text:
        return []
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def squeeze_whitespace(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_kv(raw: str) -> Optional[Tuple[str, str]]:
    """Parse 'key = value' or 'key: value' into ``(key, value)``."""
    if not raw:
        return None
    s = raw.strip()
    if not s or s.startswith("#"):
        return None
    sep = None
    for candidate in ("=", ":"):
        idx = s.find(candidate)
        if idx > 0:
            sep = idx
            break
    if sep is None:
        return None
    key = s[:sep].strip()
    val = s[sep + 1 :].strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return key, val


def parse_kv_block(text: str) -> dict:
    out: dict = {}
    for line in split_lines(text):
        kv = parse_kv(line)
        if kv:
            out[kv[0]] = kv[1]
    return out


def detect_indent(text: str) -> int:
    """Best-guess indent (number of spaces). Returns 4 if unsure."""
    if not text:
        return 4
    for line in split_lines(text):
        m = re.match(r"^( +)\S", line)
        if m:
            return len(m.group(1))
    return 4


def detect_eol(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def parse_int_list(raw: str) -> List[int]:
    """Parse '1,3-5,8' into [1,3,4,5,8]. Used by '--rows 1-5,7'."""
    if not raw:
        return []
    out: list = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece and not piece.startswith("-"):
            a, _, b = piece.partition("-")
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            if lo <= hi:
                out.extend(range(lo, hi + 1))
        else:
            try:
                out.append(int(piece))
            except ValueError:
                continue
    # dedupe but preserve order
    seen: set = set()
    uniq: list = []
    for n in out:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq


def normalise_newlines(text: str) -> str:
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_size(raw: str) -> Optional[int]:
    """Parse '12kb', '4MB', '900' into a byte count."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    units = {"b": 1, "k": 1024, "kb": 1024, "m": 1024 ** 2, "mb": 1024 ** 2, "g": 1024 ** 3, "gb": 1024 ** 3}
    for suf, mul in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if s.endswith(suf):
            head = s[: -len(suf)].strip()
            try:
                return int(float(head) * mul)
            except ValueError:
                return None
    try:
        return int(float(s))
    except ValueError:
        return None


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def first_nonblank_line(text: str) -> str:
    for line in split_lines(text):
        if line.strip():
            return line.strip()
    return ""


def truncate(text: str, length: int = 80, *, ellipsis: str = "\u2026") -> str:
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[: max(0, length - len(ellipsis))] + ellipsis
