"""Named workspace registry for users who keep multiple snippet books."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional


@dataclass
class Workspace:
    name: str
    book_path: Path
    description: str = ""
    created_at: float = field(default_factory=time.time)
    last_opened_at: float = 0.0
    labels: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValueError("workspace name is blank")
        self.book_path = Path(self.book_path).expanduser()
        self.description = (self.description or "").strip()
        self.labels = list(dict.fromkeys(label.strip().lower() for label in self.labels if label.strip()))

    def resolved_path(self, *, base: Optional[Path] = None) -> Path:
        path = self.book_path
        if not path.is_absolute() and base is not None:
            path = Path(base) / path
        return path.resolve()

    def exists(self, *, base: Optional[Path] = None) -> bool:
        return self.resolved_path(base=base).is_file()

    def touch(self, *, at: Optional[float] = None) -> None:
        self.last_opened_at = time.time() if at is None else float(at)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "book_path": str(self.book_path),
            "description": self.description,
            "created_at": self.created_at,
            "last_opened_at": self.last_opened_at,
            "labels": list(self.labels),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Workspace":
        return cls(
            name=str(data.get("name") or ""),
            book_path=Path(str(data.get("book_path") or "")),
            description=str(data.get("description") or ""),
            created_at=float(data.get("created_at") or time.time()),
            last_opened_at=float(data.get("last_opened_at") or 0),
            labels=list(data.get("labels") or []),
        )


class WorkspaceRegistry:
    def __init__(self, workspaces: Iterable[Workspace] = (), *, active: str = "") -> None:
        self._workspaces: Dict[str, Workspace] = {}
        self.active = ""
        for workspace in workspaces:
            self.add(workspace)
        if active:
            self.set_active(active)

    @staticmethod
    def _key(name: str) -> str:
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("workspace name is blank")
        return key

    def add(self, workspace: Workspace, *, replace: bool = False) -> bool:
        key = self._key(workspace.name)
        if key in self._workspaces and not replace:
            return False
        self._workspaces[key] = workspace
        if not self.active:
            self.active = key
        return True

    def get(self, name: str) -> Optional[Workspace]:
        return self._workspaces.get(self._key(name))

    def remove(self, name: str) -> bool:
        key = self._key(name)
        removed = self._workspaces.pop(key, None)
        if removed is None:
            return False
        if self.active == key:
            self.active = sorted(self._workspaces)[0] if self._workspaces else ""
        return True

    def rename(self, old_name: str, new_name: str) -> bool:
        old_key = self._key(old_name)
        workspace = self._workspaces.get(old_key)
        if workspace is None:
            return False
        new_key = self._key(new_name)
        if new_key != old_key and new_key in self._workspaces:
            raise ValueError(f"workspace already exists: {new_name}")
        del self._workspaces[old_key]
        workspace.name = new_name.strip()
        self._workspaces[new_key] = workspace
        if self.active == old_key:
            self.active = new_key
        return True

    def set_active(self, name: str) -> Workspace:
        key = self._key(name)
        workspace = self._workspaces.get(key)
        if workspace is None:
            raise KeyError(f"workspace not found: {name}")
        self.active = key
        return workspace

    def active_workspace(self) -> Optional[Workspace]:
        return self._workspaces.get(self.active)

    def list(self, *, labels: Iterable[str] = (), existing_only: bool = False, base: Optional[Path] = None):
        wanted = {label.lower() for label in labels}
        result: list[Workspace] = []
        for workspace in self._workspaces.values():
            if wanted and not wanted.issubset(set(workspace.labels)):
                continue
            if existing_only and not workspace.exists(base=base):
                continue
            result.append(workspace)
        return sorted(result, key=lambda item: item.name.lower())

    def missing(self, *, base: Optional[Path] = None) -> List[Workspace]:
        return [workspace for workspace in self.list(base=base) if not workspace.exists(base=base)]

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "active": self.active,
            "workspaces": [workspace.to_dict() for workspace in self.list()],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "WorkspaceRegistry":
        workspaces: list[Workspace] = []
        for item in data.get("workspaces") or []:
            try:
                workspaces.append(Workspace.from_dict(item))
            except (TypeError, ValueError):
                continue
        active = str(data.get("active") or "")
        try:
            return cls(workspaces, active=active)
        except KeyError:
            return cls(workspaces)

    @classmethod
    def load(cls, path: Path) -> "WorkspaceRegistry":
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"workspace registry is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("workspace registry root must be an object")
        return cls.from_dict(data)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
