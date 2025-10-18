import pytest

from snippetbox import merge
from snippetbox.errors import SnippetboxError
from snippetbox.snippet import Snippet


def test_merge_books_adds_new_snippets():
    base = {"snippets": [{"id": "a", "title": "x", "body": "b", "updated_at": 1}]}
    incoming = {"snippets": [{"id": "b", "title": "y", "body": "b", "updated_at": 2}]}
    out, report = merge.merge_books(base, incoming)
    assert report.added == 1
    assert len(out["snippets"]) == 2


def test_merge_books_keep_base_skips_conflict():
    base = {"snippets": [{"id": "a", "title": "x", "body": "old", "updated_at": 1}]}
    incoming = {"snippets": [{"id": "a", "title": "x", "body": "new", "updated_at": 2}]}
    out, report = merge.merge_books(base, incoming, strategy="keep-base")
    assert report.skipped == 1
    assert out["snippets"][0]["body"] == "old"


def test_merge_books_prefer_incoming_replaces():
    base = {"snippets": [{"id": "a", "title": "x", "body": "old", "updated_at": 1}]}
    incoming = {"snippets": [{"id": "a", "title": "x", "body": "new", "updated_at": 2}]}
    out, report = merge.merge_books(base, incoming, strategy="prefer-incoming")
    assert report.replaced == 1
    assert out["snippets"][0]["body"] == "new"


def test_merge_books_newer_wins_keeps_newer():
    base = {"snippets": [{"id": "a", "title": "x", "body": "old", "updated_at": 5}]}
    incoming = {"snippets": [{"id": "a", "title": "x", "body": "new", "updated_at": 1}]}
    out, report = merge.merge_books(base, incoming, strategy="newer-wins")
    assert report.skipped == 1
    assert out["snippets"][0]["body"] == "old"


def test_merge_books_newer_wins_picks_incoming_when_newer():
    base = {"snippets": [{"id": "a", "title": "x", "body": "old", "updated_at": 1}]}
    incoming = {"snippets": [{"id": "a", "title": "x", "body": "new", "updated_at": 5}]}
    out, report = merge.merge_books(base, incoming, strategy="newer-wins")
    assert report.replaced == 1
    assert out["snippets"][0]["body"] == "new"


def test_merge_books_invalid_strategy():
    with pytest.raises(SnippetboxError):
        merge.merge_books({}, {}, strategy="psychic")


def test_merge_books_handles_missing_id():
    incoming = {"snippets": [{"title": "x", "body": "b", "updated_at": 1}]}
    out, report = merge.merge_books({"snippets": []}, incoming)
    assert report.added == 1


def test_diff_book():
    base = {"snippets": [{"id": "a"}, {"id": "b"}]}
    incoming = {"snippets": [{"id": "b"}, {"id": "c"}]}
    out = merge.diff_book(base, incoming)
    assert out["added"] == ["c"]
    assert out["removed"] == ["a"]
    assert out["common"] == ["b"]


def test_conflicts_helper():
    base = {"snippets": [{"id": "a"}, {"id": "b"}]}
    incoming = {"snippets": [{"id": "b"}, {"id": "c"}]}
    out = merge.conflicts(base, incoming)
    assert out == ["b"]


def test_merge_snippet_keep_base():
    a = Snippet(title="x", body="old")
    b = Snippet(title="x", body="new")
    out = merge.merge_snippet(a, b, strategy="keep-base")
    assert out is a


def test_merge_snippet_prefer_incoming():
    a = Snippet(title="x", body="old")
    b = Snippet(title="x", body="new")
    out = merge.merge_snippet(a, b, strategy="prefer-incoming")
    assert out is b


def test_merge_snippet_newer_wins_picks_incoming():
    a = Snippet(title="x", body="old")
    a.updated_at = 1
    b = Snippet(title="x", body="new")
    b.updated_at = 5
    out = merge.merge_snippet(a, b)
    assert out is b


def test_merge_snippet_newer_wins_keeps_base():
    a = Snippet(title="x", body="old")
    a.updated_at = 5
    b = Snippet(title="x", body="new")
    b.updated_at = 1
    out = merge.merge_snippet(a, b)
    assert out is a


def test_can_merge_same_schema():
    assert merge.can_merge({"schema_version": 3}, {"schema_version": 3}) is True


def test_can_merge_different_schema():
    assert merge.can_merge({"schema_version": 2}, {"schema_version": 3}) is False


def test_merge_report_total():
    r = merge.MergeReport(added=2, replaced=1, skipped=3)
    assert r.total() == 6


def test_merge_report_summary():
    r = merge.MergeReport(added=1, replaced=2, skipped=3, conflicts=["a", "b"])
    text = r.summary()
    assert "added=1" in text
    assert "conflicts=2" in text


def test_merge_books_records_conflicts():
    base = {"snippets": [{"id": "a", "title": "x", "body": "1", "updated_at": 1}]}
    incoming = {"snippets": [{"id": "a", "title": "x", "body": "2", "updated_at": 2}]}
    _, report = merge.merge_books(base, incoming)
    assert "a" in report.conflicts
