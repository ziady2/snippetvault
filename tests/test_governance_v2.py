from __future__ import annotations


import pytest

from snippetbox.author import Author
from snippetbox.batch import BatchOperation, apply_operations, apply_to_book, parse_operations, plan, render_plan
from snippetbox.health import HealthFinding, HealthReport, exit_code, inspect_book, inspect_path, merge_reports
from snippetbox.maintenance import (
    apply as apply_repairs,
    archive_stale,
    compact_metadata,
    remove_empty_collections,
    render as render_repairs,
    repair,
)
from snippetbox.policy import (
    SnippetPolicy,
    combine,
    counts,
    evaluate,
    evaluate_many,
    has_errors,
    policy_from_dict,
    policy_to_dict,
    render,
)
from snippetbox.sharing import (
    SharingProfile,
    profile_from_dict,
    profile_to_dict,
    pseudonym,
    redact,
    redact_many,
    redaction_summary,
    scan,
)
from snippetbox.snippet import Snippet


def make_snippet(identifier: str = "one", **kwargs) -> Snippet:
    values = {
        "id": identifier,
        "title": "API client",
        "body": "token=super-secret\nprint('ready')\n",
        "language": "python",
        "tags": ["web", "private:team"],
        "notes": "internal note",
        "source": "C:/private/api.py",
        "author": Author("Ziad", "z@example.com"),
        "created_at": 100,
        "updated_at": 100,
    }
    values.update(kwargs)
    return Snippet(**values)


def test_sharing_scan_finds_sensitive_fields():
    findings = scan(make_snippet(body="contact dev@example.com\npassword=hunter2"))
    reasons = {finding.reason for finding in findings}
    assert {"personal_email", "source_location", "private_notes", "email_address", "credential", "private_tag"}.issubset(reasons)


def test_default_sharing_profile_redacts_private_data():
    shared = redact(make_snippet())
    assert "super-secret" not in shared.snippet.body
    assert shared.snippet.notes == ""
    assert shared.snippet.source == ""
    assert shared.snippet.author.name == "Ziad"
    assert shared.snippet.author.email == ""
    assert shared.snippet.tags == ["web"]
    assert not shared.safe


def test_custom_sharing_profile_can_include_fields():
    profile = SharingProfile(
        name="trusted",
        include_notes=True,
        include_source=True,
        include_author_email=True,
        include_private_tags=True,
        scan_secrets=False,
    )
    shared = redact(make_snippet(), profile)
    assert shared.snippet.notes == "internal note"
    assert shared.snippet.author.email == "z@example.com"
    assert shared.snippet.tags == ["web", "private:team"]
    assert "super-secret" in shared.snippet.body


def test_sharing_profile_round_trip_and_summary():
    profile = SharingProfile(name="external")
    assert profile_from_dict(profile_to_dict(profile)) == profile
    items = redact_many([make_snippet("a"), make_snippet("b")], profile)
    summary = redaction_summary(items)
    assert summary["notes:profile_excludes_notes"] == 2


def test_pseudonym_is_stable_and_salted():
    assert pseudonym("z@example.com") == pseudonym("z@example.com")
    assert pseudonym("z@example.com", salt="other") != pseudonym("z@example.com")
    with pytest.raises(ValueError):
        pseudonym("x", length=3)


def test_policy_reports_content_and_metadata_issues():
    snippet = make_snippet(title="", body="x", language="rust", tags=["private:a"])
    policy = SnippetPolicy(
        require_tags=True,
        minimum_body_characters=5,
        allowed_languages=("python",),
        forbidden_patterns=("token",),
        stale_after_days=1,
    )
    issues = evaluate(snippet, policy, now=200_000)
    codes = {issue.code for issue in issues}
    assert {"missing_title", "body_too_short", "language_not_allowed", "forbidden_tag", "stale"}.issubset(codes)
    assert has_errors(issues)
    assert "ERROR" in render(issues)


def test_policy_forbidden_pattern_and_invalid_regex():
    policy = SnippetPolicy(forbidden_patterns=("super-secret",))
    assert any(issue.code == "forbidden_content" for issue in evaluate(make_snippet(), policy))
    with pytest.raises(ValueError, match="invalid policy pattern"):
        evaluate(make_snippet(), SnippetPolicy(forbidden_patterns=("[",)))


def test_policy_round_trip_combine_and_counts():
    left = SnippetPolicy(require_tags=False, maximum_tags=10, allowed_languages=("python", "sql"))
    right = SnippetPolicy(require_tags=True, maximum_tags=5, allowed_languages=("python",))
    combined = combine(left, right)
    assert combined.require_tags
    assert combined.maximum_tags == 5
    assert combined.allowed_languages == ("python",)
    assert policy_from_dict(policy_to_dict(combined)) == combined
    assert counts(evaluate_many([make_snippet("a"), make_snippet("b")], combined))["warning"] >= 2


def test_batch_operations_apply_without_mutating_original():
    original = make_snippet(tags=["Web"], auto_tags=["generated"])
    operations = [
        BatchOperation("add_tag", "API"),
        BatchOperation("remove_tag", "generated"),
        BatchOperation("set_language", "SQL"),
        BatchOperation("archive"),
        BatchOperation("clear_notes"),
    ]
    changed = apply_operations(original, operations, touch=False)
    assert original.language == "python"
    assert changed.language == "sql"
    assert changed.tags == ["Web", "api"]
    assert changed.auto_tags == []
    assert changed.archived
    assert changed.notes == ""


def test_batch_parse_plan_render_and_apply(empty_book):
    first = make_snippet("a", body="print(1)", tags=["web"])
    second = make_snippet("b", title="Other", body="print(2)", tags=["other"])
    empty_book.add(first)
    empty_book.add(second)
    operations = parse_operations(["add-tag=reviewed", "favourite"])
    result = plan(list(empty_book), operations, predicate=lambda item: item.has_tag("web"), touch=False)
    assert result.selected_count == 1
    assert result.changed_count == 1
    assert "selected=1 changed=1" in render_plan(result)
    assert apply_to_book(empty_book, result) == 1
    assert empty_book.get("a").favourite
    assert not empty_book.get("b").favourite


def test_batch_validation():
    with pytest.raises(ValueError):
        BatchOperation("unknown")
    with pytest.raises(ValueError):
        BatchOperation("add_tag")


def test_repair_normalises_slugs_tags_and_collection_members():
    raw = {
        "schema_version": 3,
        "snippets": [
            make_snippet("a", slug="Same", tags=[" Web ", "web", ""]).to_dict(),
            make_snippet("b", slug="Same", tags=["API"], auto_tags=["api", "AUTO"]).to_dict(),
        ],
        "collections": [{"name": "mixed", "snippet_ids": ["a", "missing", "a"]}],
        "metadata": {
            "revision_history": {"missing": []},
            "reviews": [{"snippet_id": "missing"}],
        },
    }
    result = repair(raw)
    assert result.changed
    assert result.data["snippets"][0]["slug"] == "same"
    assert result.data["snippets"][1]["slug"] == "same-2"
    assert result.data["snippets"][0]["tags"] == ["web"]
    assert result.data["snippets"][1]["auto_tags"] == ["auto"]
    assert result.data["collections"][0]["snippet_ids"] == ["a"]
    assert "missing" not in result.data["metadata"]["revision_history"]
    assert "actions=" in render_repairs(result)


def test_apply_repair_and_remove_empty_collections(empty_book):
    empty_book.data["collections"] = [{"name": "empty", "snippet_ids": []}]
    result = remove_empty_collections(empty_book.data)
    assert apply_repairs(empty_book, result)
    assert empty_book.data["collections"] == []


def test_compact_metadata_retains_newest_items():
    data = {"metadata": {"usage_log": list(range(5)), "snapshots": list(range(4))}}
    result = compact_metadata(data, keep_usage=2, keep_snapshots=1)
    assert result.data["metadata"]["usage_log"] == [3, 4]
    assert result.data["metadata"]["snapshots"] == [3]


def test_archive_stale_only_changes_old_active_snippets():
    data = {
        "snippets": [
            make_snippet("old", updated_at=10).to_dict(),
            make_snippet("new", updated_at=100).to_dict(),
            make_snippet("archived", updated_at=1, archived=True).to_dict(),
        ]
    }
    result = archive_stale(data, cutoff=50)
    assert [action.entity for action in result.actions] == ["old"]


def test_health_report_for_clean_and_broken_books(tmp_path, empty_book):
    clean = inspect_book(empty_book)
    assert clean.healthy
    assert clean.metrics["snippets"] == 0
    empty_book.data["collections"] = [{"name": "bad", "snippet_ids": ["missing"]}]
    broken = inspect_book(empty_book)
    assert any(finding.code == "dangling_collection_member" for finding in broken.findings)
    assert exit_code(broken) == 0
    assert exit_code(broken, warnings_as_errors=True) == 1
    missing = inspect_path(tmp_path / "missing.json")
    assert not missing.healthy
    assert exit_code(missing) == 2


def test_health_merge_render_and_serialise():
    warning = HealthReport([HealthFinding("warn", "warning", "warning")], {"a": 1})
    error = HealthReport([HealthFinding("bad", "error", "error")], {"b": 2})
    merged = merge_reports(warning, error)
    assert merged.level == "error"
    assert merged.counts() == {"info": 0, "warning": 1, "error": 1}
    assert merged.to_dict()["healthy"] is False
    assert "ERROR" in merged.render_text()
