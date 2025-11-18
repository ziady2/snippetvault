import pytest

from snippetbox import search
from snippetbox.errors import SearchError
from snippetbox.snippet import Snippet


def test_search_with_blank_query_returns_all(populated_book):
    hits = search.search(list(populated_book), "")
    assert len(hits) == 3


def test_search_substring_mode(populated_book):
    hits = search.search(list(populated_book), "asyncio", mode="substring")
    assert len(hits) == 1


def test_search_token_mode_and(populated_book):
    hits = search.search(list(populated_book), "tail file")
    assert len(hits) == 1


def test_search_token_mode_no_match(populated_book):
    hits = search.search(list(populated_book), "tail nonexistentxyz")
    assert hits == []


def test_search_fuzzy_typo(populated_book):
    hits = search.search(list(populated_book), "asyncii", mode="fuzzy")
    assert len(hits) == 1


def test_search_invalid_mode_raises(populated_book):
    with pytest.raises(SearchError):
        search.search(list(populated_book), "x", mode="psychic")


def test_search_filters_by_language(populated_book):
    hits = search.search(list(populated_book), "", languages=["python"])
    assert all(h.snippet.language == "python" for h in hits)


def test_search_filters_by_tag(populated_book):
    hits = search.search(list(populated_book), "", tags=["search"])
    assert len(hits) == 1


def test_search_excludes_archived_by_default(empty_book, python_snippet):
    python_snippet.archived = True
    empty_book.add(python_snippet)
    assert search.search(list(empty_book), "asyncio") == []


def test_search_includes_archived_when_asked(empty_book, python_snippet):
    python_snippet.archived = True
    empty_book.add(python_snippet)
    hits = search.search(list(empty_book), "asyncio", include_archived=True)
    assert len(hits) == 1


def test_search_with_limit(populated_book):
    hits = search.search(list(populated_book), "", limit=2)
    assert len(hits) <= 2


def test_search_no_rank_unsorted(populated_book):
    hits = search.search(list(populated_book), "", rank=False)
    assert len(hits) == 3


def test_search_title_score_higher():
    a = Snippet(title="async", body="body", language="python")
    b = Snippet(title="other", body="async stuff in body", language="python")
    hits = search.search([a, b], "async")
    assert hits[0].snippet.id == a.id


def test_search_favourite_bonus():
    a = Snippet(title="async", body="x", language="python")
    b = Snippet(title="async", body="x", language="python", favourite=True)
    hits = search.search([a, b], "async")
    assert hits[0].snippet.id == b.id


def test_matches_token_substring():
    assert search.matches_token("hello world", "hell") is True


def test_matches_token_no_match():
    assert search.matches_token("hello", "abc") is False


def test_matches_token_blank_token():
    assert search.matches_token("hello", "") is True


def test_matches_token_fuzzy_off_by_one():
    assert search.matches_token("hello world", "worl", fuzzy=True) is True


def test_matches_token_fuzzy_substitution():
    assert search.matches_token("hello world", "wxrld", fuzzy=True) is True


def test_matches_token_fuzzy_too_far():
    assert search.matches_token("hello", "xxxxxx", fuzzy=True) is False


def test_filter_by_tag_simple(populated_book):
    snips = list(populated_book)
    out = search.filter_by_tag(snips, "io")
    assert len(out) == 1


def test_filter_by_language(populated_book):
    snips = list(populated_book)
    out = search.filter_by_language(snips, "python")
    assert all(s.language == "python" for s in out)


def test_filter_by_collection(populated_book):
    snips = list(populated_book)
    ids = [snips[0].id]
    out = search.filter_by_collection(snips, ids)
    assert len(out) == 1


def test_recent_returns_most_recent_first(populated_book):
    snips = list(populated_book)
    snips[0].updated_at = 1000
    snips[1].updated_at = 2000
    snips[2].updated_at = 3000
    out = search.recent(snips, n=3)
    assert out[0].updated_at == 3000


def test_recent_zero_returns_empty(populated_book):
    assert search.recent(list(populated_book), n=0) == []


def test_most_used(populated_book):
    snips = list(populated_book)
    snips[0].used_count = 5
    snips[1].used_count = 1
    out = search.most_used(snips, n=2)
    assert out[0] is snips[0]


def test_favourites(populated_book):
    snips = list(populated_book)
    snips[0].favourite = True
    out = search.favourites(snips)
    assert len(out) == 1


def test_archived(populated_book):
    snips = list(populated_book)
    snips[0].archived = True
    out = search.archived(snips)
    assert len(out) == 1


def test_explain_includes_score(populated_book):
    hit = search.search(list(populated_book), "asyncio")[0]
    text = search.explain(hit)
    assert "score" in text


def test_explain_includes_match_areas(populated_book):
    hit = search.search(list(populated_book), "asyncio")[0]
    text = search.explain(hit)
    assert "matched" in text


def test_within_one_identical():
    assert search._within_one("a", "a") is True


def test_within_one_too_far():
    assert search._within_one("ab", "xyz") is False


def test_within_one_insertion():
    assert search._within_one("abc", "abxc") is True


def test_within_one_substitution():
    assert search._within_one("abc", "abd") is True


def test_search_substring_blank_token_returns_all(populated_book):
    hits = search.search(list(populated_book), "", mode="substring")
    assert len(hits) == 3
