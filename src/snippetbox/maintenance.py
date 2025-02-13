"""Safe repair and cleanup operations for loaded books."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List

from .identifiers import unique_slug
from .tag import normalise as normalise_tag


@dataclass(frozen=True)
class RepairAction:
    code: str
    entity: str
    message: str
    changed: bool = True


@dataclass
class RepairResult:
    data: dict
    actions: List[RepairAction] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(action.changed for action in self.actions)

    def counts(self) -> dict:
        result: dict[str, int] = {}
        for action in self.actions:
            result[action.code] = result.get(action.code, 0) + 1
        return dict(sorted(result.items()))


def _dedupe(values: Iterable[str], *, normaliser: Callable[[str], str] = lambda value: value):
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalised = normaliser(value)
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        result.append(normalised)
    return result


def repair(
    book_data: dict,
    *,
    fix_slugs: bool = True,
    fix_tags: bool = True,
    drop_dangling_members: bool = True,
    remove_orphan_workflows: bool = True,
) -> RepairResult:
    data = copy.deepcopy(book_data)
    actions: list[RepairAction] = []
    snippets = data.setdefault("snippets", [])
    known_ids = {str(item.get("id") or "") for item in snippets if item.get("id")}

    if fix_slugs:
        occupied: list[str] = []
        for raw in snippets:
            identifier = str(raw.get("id") or "")
            original = str(raw.get("slug") or "")
            valid = bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", original))
            if not original or not valid or original.lower() in {value.lower() for value in occupied}:
                replacement = unique_slug(
                    original or str(raw.get("title") or ""),
                    occupied,
                    fallback=identifier[:8] or "snippet",
                )
                raw["slug"] = replacement
                actions.append(
                    RepairAction(
                        "repair_slug",
                        identifier,
                        f"changed slug from {original!r} to {replacement!r}",
                    )
                )
            occupied.append(raw.get("slug", ""))

    if fix_tags:
        for raw in snippets:
            identifier = str(raw.get("id") or "")
            manual = _dedupe(raw.get("tags") or [], normaliser=normalise_tag)
            automatic = _dedupe(raw.get("auto_tags") or [], normaliser=normalise_tag)
            automatic = [tag for tag in automatic if tag not in set(manual)]
            if manual != list(raw.get("tags") or []):
                raw["tags"] = manual
                actions.append(RepairAction("normalise_tags", identifier, "normalised manual tags"))
            if automatic != list(raw.get("auto_tags") or []):
                raw["auto_tags"] = automatic
                actions.append(RepairAction("normalise_auto_tags", identifier, "normalised automatic tags"))

    if drop_dangling_members:
        for collection in data.setdefault("collections", []):
            original = list(collection.get("snippet_ids") or [])
            cleaned = [identifier for identifier in dict.fromkeys(original) if identifier in known_ids]
            if cleaned != original:
                collection["snippet_ids"] = cleaned
                actions.append(
                    RepairAction(
                        "drop_dangling_collection_member",
                        str(collection.get("name") or ""),
                        f"removed {len(original) - len(cleaned)} invalid member references",
                    )
                )

    if remove_orphan_workflows:
        metadata = data.setdefault("metadata", {})
        revisions = metadata.get("revision_history")
        if isinstance(revisions, dict):
            for identifier in sorted(set(revisions) - known_ids):
                revisions.pop(identifier, None)
                actions.append(
                    RepairAction("drop_orphan_revisions", identifier, "removed history for missing snippet")
                )
        reviews = metadata.get("reviews")
        if isinstance(reviews, list):
            cleaned_reviews = [item for item in reviews if item.get("snippet_id") in known_ids]
            removed = len(reviews) - len(cleaned_reviews)
            if removed:
                metadata["reviews"] = cleaned_reviews
                actions.append(
                    RepairAction("drop_orphan_reviews", "metadata", f"removed {removed} orphan reviews")
                )
    return RepairResult(data=data, actions=actions)


def apply(book, result: RepairResult, *, save: bool = False) -> bool:
    if not result.changed:
        return False
    book.data = copy.deepcopy(result.data)
    if save:
        book.save()
    return True


def compact_metadata(book_data: dict, *, keep_usage: int = 500, keep_snapshots: int = 25) -> RepairResult:
    if keep_usage < 0 or keep_snapshots < 0:
        raise ValueError("retention limits must not be negative")
    data = copy.deepcopy(book_data)
    actions: list[RepairAction] = []
    metadata = data.setdefault("metadata", {})
    usage = metadata.get("usage_log")
    if isinstance(usage, list) and len(usage) > keep_usage:
        removed = len(usage) - keep_usage
        metadata["usage_log"] = usage[-keep_usage:] if keep_usage else []
        actions.append(RepairAction("trim_usage", "metadata", f"removed {removed} usage events"))
    snapshots = metadata.get("snapshots")
    if isinstance(snapshots, list) and len(snapshots) > keep_snapshots:
        removed = len(snapshots) - keep_snapshots
        metadata["snapshots"] = snapshots[-keep_snapshots:] if keep_snapshots else []
        actions.append(RepairAction("trim_snapshots", "metadata", f"removed {removed} snapshots"))
    return RepairResult(data=data, actions=actions)


def remove_empty_collections(book_data: dict) -> RepairResult:
    data = copy.deepcopy(book_data)
    collections = data.setdefault("collections", [])
    kept = [collection for collection in collections if collection.get("snippet_ids")]
    removed = [collection for collection in collections if not collection.get("snippet_ids")]
    data["collections"] = kept
    actions = [
        RepairAction("remove_empty_collection", str(collection.get("name") or ""), "removed empty collection")
        for collection in removed
    ]
    return RepairResult(data=data, actions=actions)


def archive_stale(book_data: dict, *, cutoff: float) -> RepairResult:
    data = copy.deepcopy(book_data)
    actions: list[RepairAction] = []
    for raw in data.setdefault("snippets", []):
        if not raw.get("archived") and float(raw.get("updated_at") or 0) < cutoff:
            raw["archived"] = True
            actions.append(
                RepairAction("archive_stale", str(raw.get("id") or ""), "archived stale snippet")
            )
    return RepairResult(data=data, actions=actions)


def render(result: RepairResult) -> str:
    if not result.actions:
        return "no repairs needed"
    rows = [f"{action.code:<34} {action.entity:<16} {action.message}" for action in result.actions]
    rows.append(f"actions={len(result.actions)}")
    return "\n".join(rows)
