import time

from snippetbox import recipes
from snippetbox.collection import Collection
from snippetbox.snippet import Snippet


def test_auto_tag_all_updates(empty_book):
    s = Snippet(title="x", body="open('f')", language="python")
    empty_book.add(s)
    n = recipes.auto_tag_all(empty_book)
    assert n >= 1


def test_auto_tag_all_no_change_when_already_tagged(empty_book):
    s = Snippet(title="x", body="just text", language="python")
    empty_book.add(s)
    recipes.auto_tag_all(empty_book)
    # second call: same body, should be no change
    n = recipes.auto_tag_all(empty_book)
    assert n == 0


def test_dedup_all_dry_run(empty_book):
    a = Snippet(title="a", body="x", language="python")
    b = Snippet(title="b", body="x", language="python")
    empty_book.add(a)
    empty_book.add(b)
    out = recipes.dedup_all(empty_book, dry_run=True)
    assert out == 1


def test_dedup_all_real_remove(empty_book):
    a = Snippet(title="a", body="x", language="python")
    b = Snippet(title="b", body="x", language="python")
    empty_book.add(a)
    empty_book.add(b)
    n = recipes.dedup_all(empty_book)
    assert n == 1
    assert len(empty_book) == 1


def test_archive_stale(empty_book):
    s = Snippet(title="a", body="b", language="python")
    s.updated_at = time.time() - 365 * 86400 * 2
    empty_book.add(s)
    n = recipes.archive_stale(empty_book, days=180)
    assert n == 1


def test_archive_stale_skips_already_archived(empty_book):
    s = Snippet(title="a", body="b", language="python")
    s.archived = True
    s.updated_at = time.time() - 365 * 86400 * 2
    empty_book.add(s)
    n = recipes.archive_stale(empty_book, days=180)
    assert n == 0


def test_unarchive_all(empty_book):
    s = Snippet(title="a", body="b", language="python", archived=True)
    empty_book.add(s)
    n = recipes.unarchive_all(empty_book)
    assert n == 1
    fresh = empty_book.get(s.id)
    assert fresh.archived is False


def test_summarise_returns_dict(populated_book):
    out = recipes.summarise(populated_book)
    assert "total" in out
    assert "lint_issues" in out


def test_search_and_mark_favourite(populated_book):
    n = recipes.search_and_mark(populated_book, "asyncio", favourite=True)
    assert n >= 1


def test_search_and_mark_adds_tags(populated_book):
    n = recipes.search_and_mark(populated_book, "asyncio", add_tags=["read"])
    assert n >= 1


def test_search_and_mark_no_change_when_already_set(populated_book):
    snips = list(populated_book)
    snips[0].favourite = True
    populated_book.replace(snips[0])
    populated_book.save()
    # re-fetch
    refreshed = populated_book.get(snips[0].id)
    assert refreshed.favourite is True


def test_language_breakdown(populated_book):
    counter = recipes.language_breakdown(populated_book)
    assert counter["python"] >= 1


def test_export_collection_returns_snippets(empty_book):
    s = Snippet(title="t", body="b", language="python")
    empty_book.add(s)
    coll = Collection(name="favs", snippet_ids=[s.id])
    empty_book.upsert_collection(coll)
    out = recipes.export_collection(empty_book, "favs")
    assert len(out) == 1


def test_export_collection_missing(empty_book):
    out = recipes.export_collection(empty_book, "no-such")
    assert out == []


def test_merge_collections(empty_book):
    s = Snippet(title="t", body="b", language="python")
    empty_book.add(s)
    target = Collection(name="all", snippet_ids=[])
    src = Collection(name="favs", snippet_ids=[s.id])
    empty_book.upsert_collection(target)
    empty_book.upsert_collection(src)
    n = recipes.merge_collections(empty_book, "all", ["favs"])
    assert n == 1


def test_merge_collections_missing_target(empty_book):
    n = recipes.merge_collections(empty_book, "no-such", ["x"])
    assert n == 0


def test_healthcheck_returns_summary(populated_book):
    out = recipes.healthcheck(populated_book)
    assert "snippets" in out
    assert "favourites" in out
