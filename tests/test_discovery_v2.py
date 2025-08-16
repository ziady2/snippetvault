from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from snippetbox.catalog import Catalog
from snippetbox.collection import Collection
from snippetbox.errors import SearchError
from snippetbox.identifiers import (
    AliasRegistry,
    Reference,
    compact_reference,
    content_id,
    slugify,
    unique_slug,
)
from snippetbox.query import compile_predicate, explain, filter_snippets, parse
from snippetbox.ranking import RankingProfile, diversify, normalise_scores, rank, score
from snippetbox.snippet import Snippet
from snippetbox.timestamps import (
    TimeWindow,
    age_seconds,
    bucket_day,
    bucket_month,
    format_duration,
    format_iso,
    parse_duration,
    parse_iso,
)


def make_snippet(identifier: str, title: str, **kwargs) -> Snippet:
    defaults = {
        "id": identifier,
        "title": title,
        "body": "print('hello')",
        "language": "python",
        "created_at": 100.0,
        "updated_at": 200.0,
    }
    defaults.update(kwargs)
    return Snippet(**defaults)


def test_slugify_folds_unicode_and_punctuation():
    assert slugify("  Déjà Vu / HTTP  ") == "deja-vu-http"


def test_slugify_uses_fallback():
    assert slugify("!!!", fallback="Snippet 42") == "snippet-42"


def test_slugify_rejects_invalid_length():
    with pytest.raises(ValueError):
        slugify("hello", max_length=0)


def test_content_id_is_stable_and_namespaced():
    assert content_id("a", 1) == content_id("a", 1)
    assert content_id("a", 1, namespace="x") != content_id("a", 1, namespace="y")


def test_content_id_validates_length():
    with pytest.raises(ValueError):
        content_id("x", length=7)


def test_reference_round_trip_and_compact():
    ref = Reference.parse("collection:web")
    assert str(ref) == "collection:web"
    assert compact_reference(Reference.parse("snippet:abc")) == "abc"


@pytest.mark.parametrize("value", ["", "a b", "name:", "two:colons:here"])
def test_reference_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        Reference.parse(value)


def test_alias_registry_is_case_insensitive_and_serialisable():
    registry = AliasRegistry()
    assert registry.add("My API", Reference("abc"))
    assert not registry.add("my-api", Reference("def"))
    assert registry.resolve("MY API") == Reference("abc")
    restored = AliasRegistry.from_dict(registry.to_dict())
    assert restored.aliases_for(Reference("abc")) == ["my-api"]


def test_unique_slug_adds_first_available_suffix():
    assert unique_slug("HTTP client", ["http-client", "http-client-2"]) == "http-client-3"


def test_iso_round_trip_and_naive_values_become_utc():
    parsed = parse_iso("2025-04-03T10:20:30Z")
    assert parsed.tzinfo == timezone.utc
    assert format_iso(parsed) == "2025-04-03T10:20:30Z"
    assert format_iso(parse_iso("2025-04-03")) == "2025-04-03T00:00:00Z"


@pytest.mark.parametrize(
    ("raw", "seconds", "rendered"),
    [("30s", 30, "30s"), ("15m", 900, "15m"), ("2h", 7200, "2h"), ("7d", 604800, "1w")],
)
def test_duration_helpers(raw, seconds, rendered):
    duration = parse_duration(raw)
    assert duration.total_seconds() == seconds
    assert format_duration(duration) == rendered


def test_invalid_duration_rejected():
    with pytest.raises(ValueError):
        parse_duration("1 month")


def test_time_window_boundaries_and_intersection():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    window = TimeWindow(start, start + timedelta(days=2))
    assert window.contains(start)
    assert not window.contains(window.end)
    other = TimeWindow(start + timedelta(days=1), start + timedelta(days=3))
    assert window.overlaps(other)
    assert window.intersection(other).duration() == timedelta(days=1)


def test_timestamp_buckets_and_age():
    value = datetime(2025, 7, 14, 12, tzinfo=timezone.utc).timestamp()
    assert bucket_day(value) == "2025-07-14"
    assert bucket_month(value) == "2025-07"
    assert age_seconds(value, now=datetime(2025, 7, 15, 12, tzinfo=timezone.utc)) == 86400


def test_structured_query_parses_terms_and_fields():
    result = parse('lang:python tag:web "http client" -archived:true uses>=2')
    assert result.terms == ["http client"]
    assert result.fields() == {"language", "tag", "archived", "uses"}
    assert result.values("lang") == ["python"]


def test_structured_query_rejects_unknown_field():
    with pytest.raises(SearchError):
        parse("planet:mars")


def test_structured_query_filters_terms_booleans_and_numbers():
    matching = make_snippet(
        "one",
        "HTTP client",
        tags=["web"],
        favourite=True,
        used_count=3,
    )
    wrong_language = make_snippet("two", "HTTP client", language="javascript", tags=["web"])
    wrong_usage = make_snippet("three", "HTTP client", tags=["web"], used_count=1)
    result = filter_snippets(
        [matching, wrong_language, wrong_usage],
        "http lang:python tag:web favourite:true uses>=2",
    )
    assert [snippet.id for snippet in result] == ["one"]


def test_repeated_query_fields_use_or_semantics():
    py = make_snippet("py", "one", language="python")
    js = make_snippet("js", "two", language="javascript")
    sql = make_snippet("sql", "three", language="sql")
    result = filter_snippets([py, js, sql], "lang:python lang:javascript")
    assert {snippet.id for snippet in result} == {"py", "js"}


def test_negative_query_clause_excludes_matches():
    active = make_snippet("active", "one")
    archived = make_snippet("old", "two", archived=True)
    assert [item.id for item in filter_snippets([active, archived], "-archived:true")] == ["active"]


def test_query_date_comparison_and_explanation():
    snippet = make_snippet(
        "dated",
        "dated",
        updated_at=datetime(2025, 6, 1, tzinfo=timezone.utc).timestamp(),
    )
    predicate = compile_predicate("updated>=2025-01-01")
    assert predicate(snippet)
    detail = explain(snippet, "updated>=2025-01-01")
    assert detail["matched"] is True
    assert detail["clauses"][0]["matched"] is True


def test_catalog_indexes_and_related_snippets():
    first = make_snippet("a", "alpha", tags=["web", "http"])
    second = make_snippet("b", "beta", tags=["web"])
    third = make_snippet("c", "gamma", language="sql")
    collection = Collection("network", snippet_ids=["a", "c"])
    catalog = Catalog([first, second, third], [collection])
    assert catalog.get(first.slug).id == "a"
    assert [item.id for item in catalog.by_tag("WEB")] == ["a", "b"]
    assert [item.id for item in catalog.in_collection("NETWORK")] == ["a", "c"]
    assert [item.id for item in catalog.related(first)] == ["b", "c"]


def test_catalog_reports_duplicates_and_dangling_members():
    first = make_snippet("same", "one", slug="duplicate")
    second = make_snippet("same", "two", slug="duplicate")
    catalog = Catalog([first, second], [Collection("bad", snippet_ids=["missing"])])
    assert {issue.code for issue in catalog.issues()} == {
        "duplicate_id",
        "duplicate_slug",
        "dangling_collection_member",
    }


def test_ranking_uses_text_favourite_usage_and_recency():
    now = 1_000_000.0
    best = make_snippet("best", "HTTP client", favourite=True, used_count=10, updated_at=now)
    other = make_snippet("other", "misc", body="an http client", updated_at=now - 86400)
    ranked = rank([other, best], "http client", now=now)
    assert [item.snippet.id for item in ranked] == ["best", "other"]
    assert "title=" in ranked[0].explanation()


def test_ranking_profiles_validate_and_round_trip_scores():
    with pytest.raises(ValueError):
        RankingProfile(recency_half_life_days=0)
    item = score(make_snippet("x", "hello"), "hello", now=200)
    normalised = normalise_scores([item])
    assert normalised[0].score == 1.0


def test_diversify_limits_each_language():
    snippets = [make_snippet(str(i), f"item {i}", language="python") for i in range(4)]
    snippets.append(make_snippet("sql", "sql", language="sql"))
    ranked = rank(snippets, "", now=200)
    result = diversify(ranked, per_language=2)
    assert [item.snippet.language for item in result].count("python") == 2
    assert any(item.snippet.language == "sql" for item in result)
