from __future__ import annotations

import json
from pathlib import Path

import pytest

from snippetbox.collection import Collection
from snippetbox.manifest import (
    Manifest,
    ManifestEntry,
    build,
    entry_from_file,
    hash_bytes,
    normalise_path,
    verify,
)
from snippetbox.provenance import ProvenanceIndex, SourceRecord, index_for_book, infer, save_index
from snippetbox.quality import QualityProfile, render as render_quality, score_library, score_snippet
from snippetbox.retention import (
    ARCHIVE,
    DELETE,
    KEEP,
    RetentionPolicy,
    apply as apply_retention,
    decide,
    plan as retention_plan,
    policy_from_dict as retention_policy_from_dict,
    policy_to_dict as retention_policy_to_dict,
)
from snippetbox.snapshot import BookSnapshot, compare, create, stored, store
from snippetbox.snippet import Snippet
from snippetbox.stats import (
    cooccurring_tags,
    compute,
    concentration,
    created_by_month,
    distribution,
    freshness,
    growth_rate,
    language_share,
    language_tag_matrix,
    orphan_tags,
    render_summary,
    top_snippets,
)
from snippetbox.workspace import Workspace, WorkspaceRegistry


def make_snippet(identifier: str, **kwargs) -> Snippet:
    values = {
        "id": identifier,
        "title": f"Snippet {identifier}",
        "body": "print('hello')\n",
        "language": "python",
        "tags": ["example"],
        "created_at": 1_700_000_000,
        "updated_at": 1_700_000_000,
    }
    values.update(kwargs)
    return Snippet(**values)


def test_snapshot_create_compare_store_and_round_trip(empty_book):
    empty_book.add(make_snippet("a"))
    empty_book.upsert_collection(Collection("examples", snippet_ids=["a"]))
    before = create(empty_book, label="before", created_at=10)
    assert before.validate() == []
    assert len(before.snippets) == 1
    empty_book.add(make_snippet("b", language="sql"))
    after = create(empty_book, label="after", created_at=20)
    difference = compare(before, after)
    assert difference.changed
    assert difference.snippets_added == ("b",)
    assert difference.summary()["snippets_added"] == 1
    restored = BookSnapshot.from_dict(after.to_dict())
    assert restored.to_dict() == after.to_dict()
    store(empty_book, before)
    store(empty_book, after)
    assert [item.label for item in stored(empty_book)] == ["before", "after"]


def test_snapshot_detects_changed_and_removed_entries(empty_book):
    item = make_snippet("a")
    empty_book.add(item)
    before = create(empty_book, created_at=1)
    item.body = "print('changed')"
    empty_book.replace(item)
    after_change = create(empty_book, created_at=2)
    assert compare(before, after_change).snippets_changed == ("a",)
    empty_book.delete("a")
    after_delete = create(empty_book, created_at=3)
    assert compare(after_change, after_delete).snippets_removed == ("a",)


def test_snapshot_store_enforces_retention(empty_book):
    for index in range(4):
        store(empty_book, create(empty_book, label=str(index), created_at=index), keep=2)
    assert [item.label for item in stored(empty_book)] == ["2", "3"]
    with pytest.raises(ValueError):
        store(empty_book, create(empty_book), keep=0)


@pytest.mark.parametrize("path", ["../secret", "/absolute", "folder/../secret", ""])
def test_manifest_rejects_unsafe_paths(path):
    with pytest.raises(ValueError):
        normalise_path(path)


def test_manifest_build_verify_and_json_round_trip(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    first = root / "one.txt"
    second = root / "nested" / "two.py"
    second.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    second.write_text("print(2)\n", encoding="utf-8")
    manifest = build(root, [second, first], book_checksum="a" * 64, created_at=10)
    assert [entry.path for entry in manifest.entries] == ["nested/two.py", "one.txt"]
    assert manifest.total_size() == first.stat().st_size + second.stat().st_size
    assert manifest.validate() == []
    assert verify(root, manifest) == []
    restored = Manifest.from_json(manifest.to_json())
    assert restored.to_dict() == manifest.to_dict()
    assert restored.digest() == manifest.digest()


def test_manifest_verification_reports_missing_modified_and_extra(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    tracked = root / "tracked.txt"
    tracked.write_text("before", encoding="utf-8")
    manifest = build(root, [tracked])
    tracked.write_text("after", encoding="utf-8")
    (root / "extra.txt").write_text("extra", encoding="utf-8")
    issues = verify(root, manifest, reject_extra=True)
    assert {issue.code for issue in issues} == {"size_mismatch", "extra"}
    tracked.unlink()
    assert any(issue.code == "missing" for issue in verify(root, manifest))


def test_manifest_entry_helpers_and_validation(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    path = root / "data.json"
    path.write_text("{}", encoding="utf-8")
    entry = entry_from_file(path, root=root)
    assert entry.media_type == "application/json"
    assert entry.sha256 == hash_bytes(b"{}")
    assert ManifestEntry.from_dict(entry.to_dict()) == entry
    with pytest.raises(ValueError):
        ManifestEntry("x", 1, "bad")


def test_workspace_registry_crud_filters_and_round_trip(tmp_path):
    existing_book = tmp_path / "book.json"
    existing_book.write_text("{}", encoding="utf-8")
    first = Workspace("work", existing_book, labels=["Code", "code"])
    missing = Workspace("missing", tmp_path / "missing.json", labels=["archive"])
    registry = WorkspaceRegistry([first, missing], active="work")
    assert registry.active_workspace() is first
    assert [item.name for item in registry.list(labels=["code"])] == ["work"]
    assert [item.name for item in registry.list(existing_only=True)] == ["work"]
    assert [item.name for item in registry.missing()] == ["missing"]
    assert registry.rename("work", "primary")
    assert registry.active_workspace().name == "primary"
    restored = WorkspaceRegistry.from_dict(registry.to_dict())
    assert [item.name for item in restored.list()] == ["missing", "primary"]


def test_workspace_registry_file_round_trip(tmp_path):
    path = tmp_path / "workspaces.json"
    registry = WorkspaceRegistry([Workspace("main", Path("books/main.json"))])
    registry.save(path)
    restored = WorkspaceRegistry.load(path)
    assert restored.active_workspace().name == "main"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1
    assert WorkspaceRegistry.load(tmp_path / "missing.json").list() == []


def test_provenance_records_checksums_and_round_trip():
    record = SourceRecord.for_text("print(1)", kind="file", locator="one.py", imported_at=10)
    assert record.matches_text("print(1)")
    assert not record.matches_text("print(2)")
    assert SourceRecord.from_dict(record.to_dict()) == record
    with pytest.raises(ValueError):
        SourceRecord("file", checksum="bad")


def test_provenance_index_deduplicates_finds_stale_and_orphans():
    index = ProvenanceIndex()
    record = SourceRecord.for_text("old", kind="file", locator="one.py")
    assert index.add("one", record)
    assert not index.add("one", record)
    index.add("orphan", SourceRecord("manual"))
    assert index.find_by_locator("one.py") == ["one"]
    assert index.stale([make_snippet("one", body="new")]) == ["one"]
    assert index.orphan_ids(["one"]) == ["orphan"]
    restored = ProvenanceIndex.from_dict(index.to_dict())
    assert restored.latest("one") == record


def test_provenance_book_helpers_and_inference(empty_book):
    item = make_snippet("one", source="https://example.com/snippet")
    index = index_for_book(empty_book)
    record = infer(item)
    assert record.kind == "url"
    index.add(item.id, record)
    save_index(empty_book, index)
    assert index_for_book(empty_book).latest("one").locator.startswith("https://")


def test_distribution_and_library_stats():
    stats = distribution([1, 2, 3, 10])
    assert stats.count == 4
    assert stats.median == 2.5
    assert stats.p90 == 10
    snippets = [
        make_snippet("a", tags=["web", "api"], used_count=4, favourite=True),
        make_snippet("b", language="sql", tags=["data"], used_count=1),
    ]
    library = compute(snippets)
    assert library.snippet_count == 2
    assert library.language_counts == {"python": 1, "sql": 1}
    assert "snippets: 2" in render_summary(library)


def test_statistics_matrices_shares_growth_and_top():
    snippets = [
        make_snippet("a", tags=["web", "api"], used_count=1),
        make_snippet("b", tags=["web", "api"], used_count=5),
        make_snippet("c", language="sql", tags=["data"]),
    ]
    assert created_by_month(snippets) == {"2023-11": 3}
    assert language_tag_matrix(snippets)["python"]["web"] == 2
    assert cooccurring_tags(snippets) == [("api", "web", 2)]
    assert orphan_tags(snippets) == ["data"]
    assert language_share(snippets)["python"] == pytest.approx(2 / 3)
    assert concentration(snippets) == pytest.approx(5 / 9)
    assert top_snippets(snippets, limit=1)[0].id == "b"
    assert growth_rate({"2025-01": 2, "2025-02": 4, "2025-03": 6}) == pytest.approx(0.75)


def test_freshness_validates_half_life():
    item = make_snippet("a", updated_at=100)
    assert freshness([item], now=100) == 1.0
    with pytest.raises(ValueError):
        freshness([item], now=100, half_life_days=0)


def test_quality_scores_explain_dimensions_and_suggestions():
    good = make_snippet("good", notes="why", used_count=3, favourite=True)
    result = score_snippet(good, now=good.updated_at)
    assert result.score > 80
    assert set(result.dimension_scores()) == {
        "completeness",
        "readability",
        "discoverability",
        "freshness",
        "safety",
    }
    assert "good:" in render_quality(result)
    poor = make_snippet("poor", title="", body="", language="", tags=[], updated_at=0)
    poor_result = score_snippet(poor, profile=QualityProfile(), now=1_000_000)
    assert poor_result.grade in {"D", "F"}
    assert poor_result.suggestions()


def test_library_quality_aggregates_and_filters():
    result = score_library(
        [make_snippet("a", notes="context", used_count=1), make_snippet("b", title="", tags=[])],
        now=1_700_000_000,
    )
    assert result.average > 0
    assert sum(result.grade_counts().values()) == 2
    assert len(result.below(101)) == 2
    assert set(result.dimension_averages()) == {
        "completeness",
        "readability",
        "discoverability",
        "freshness",
        "safety",
    }


def test_retention_decisions_respect_protection_and_age():
    policy = RetentionPolicy(archive_after_days=10, delete_archived_after_days=20, minimum_uses_to_keep=2)
    now = 30 * 86400
    assert decide(make_snippet("used", used_count=2, updated_at=0), policy, now=now).action == KEEP
    assert decide(make_snippet("fav", favourite=True, updated_at=0), policy, now=now).action == KEEP
    assert decide(make_snippet("old", updated_at=0), policy, now=now).action == ARCHIVE
    assert decide(make_snippet("gone", archived=True, updated_at=0), policy, now=now).action == DELETE


def test_retention_plan_apply_and_round_trip(empty_book):
    old = make_snippet("old", title="Old", updated_at=0)
    gone = make_snippet("gone", title="Gone", archived=True, updated_at=0)
    empty_book.add(old)
    empty_book.add(gone)
    policy = RetentionPolicy(archive_after_days=1, delete_archived_after_days=2, minimum_uses_to_keep=1)
    restored_policy = retention_policy_from_dict(retention_policy_to_dict(policy))
    result = retention_plan(list(empty_book), restored_policy, now=3 * 86400)
    assert result.counts() == {KEEP: 0, ARCHIVE: 1, DELETE: 1}
    applied = apply_retention(empty_book, result)
    assert applied == {"archived": 1, "deleted": 1}
    assert empty_book.get("old").archived
    assert empty_book.get("gone") is None
