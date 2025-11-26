import pytest

from snippetbox.errors import InvalidSnippetError
from snippetbox.snippet import Snippet


def test_default_snippet_has_id():
    s = Snippet(title="hi", body="x")
    assert s.id


def test_snippet_normalises_language():
    s = Snippet(title="hi", body="x", language="  PYTHON  ")
    assert s.language == "python"


def test_blank_language_defaults_to_plain():
    s = Snippet(body="x")
    assert s.language == "plain"


def test_title_truncation():
    long_title = "x" * 300
    s = Snippet(title=long_title, body="b")
    assert len(s.title) <= 200


def test_slug_built_from_title():
    s = Snippet(title="Hello World!", body="x")
    assert s.slug.startswith("hello-world")


def test_slug_falls_back_to_body_hash():
    s = Snippet(title="!!!", body="content")
    assert s.slug


def test_validate_passes_for_normal_snippet(python_snippet):
    python_snippet.validate()  # does not raise


def test_validate_rejects_blank_title_and_body():
    s = Snippet(title="", body="")
    with pytest.raises(InvalidSnippetError):
        s.validate()


def test_validate_rejects_blank_tags():
    s = Snippet(title="x", body="b", tags=["x", ""])
    with pytest.raises(InvalidSnippetError):
        s.validate()


def test_validate_rejects_newline_in_title():
    s = Snippet(title="x", body="b")
    s.title = "with\nnewline"
    with pytest.raises(InvalidSnippetError):
        s.validate()


def test_touch_updates_timestamp(python_snippet):
    before = python_snippet.updated_at
    python_snippet.created_at = before - 100
    python_snippet.touch()
    assert python_snippet.updated_at >= before


def test_mark_used_increments_count(python_snippet):
    python_snippet.mark_used()
    assert python_snippet.used_count == 1
    python_snippet.mark_used()
    assert python_snippet.used_count == 2


def test_all_tags_dedupes(python_snippet):
    python_snippet.tags = ["a", "b"]
    python_snippet.auto_tags = ["b", "c"]
    assert python_snippet.all_tags() == ["a", "b", "c"]


def test_has_tag_case_insensitive(python_snippet):
    python_snippet.tags = ["Python"]
    assert python_snippet.has_tag("python") is True


def test_has_tag_blank_returns_false(python_snippet):
    assert python_snippet.has_tag("") is False


def test_line_count_for_multi_line(python_snippet):
    assert python_snippet.line_count() >= 1


def test_line_count_blank_body():
    assert Snippet(title="x").line_count() == 0


def test_char_count(python_snippet):
    assert python_snippet.char_count() == len(python_snippet.body)


def test_to_dict_round_trip(python_snippet):
    d = python_snippet.to_dict()
    s = Snippet.from_dict(d)
    assert s.id == python_snippet.id
    assert s.body == python_snippet.body
    assert s.tags == python_snippet.tags


def test_from_dict_rejects_non_dict():
    with pytest.raises(InvalidSnippetError):
        Snippet.from_dict("not a dict")  # type: ignore[arg-type]


def test_from_dict_with_minimal_fields():
    s = Snippet.from_dict({"title": "hi", "body": "x"})
    assert s.title == "hi"


def test_from_dict_handles_extra_field():
    s = Snippet.from_dict({"title": "hi", "body": "x", "extra": {"k": "v"}})
    assert s.extra == {"k": "v"}


def test_short_summary_returns_first_line(python_snippet):
    summary = python_snippet.short_summary()
    assert summary
    assert "\n" not in summary


def test_short_summary_truncates_long_line():
    s = Snippet(title="x", body="a" * 200)
    summary = s.short_summary(width=20)
    assert len(summary) <= 21


def test_matches_query_substring(python_snippet):
    assert python_snippet.matches_query("asyncio") is True


def test_matches_query_blank_returns_true(python_snippet):
    assert python_snippet.matches_query("") is True


def test_matches_query_no_match(python_snippet):
    assert python_snippet.matches_query("nope-not-in-body") is False


def test_matches_query_finds_in_tags(python_snippet):
    assert python_snippet.matches_query("io") is True


def test_fingerprint_stable():
    s1 = Snippet(title="a", body="x \n  ")
    s2 = Snippet(title="b", body="x")
    assert s1.fingerprint() == s2.fingerprint()


def test_fingerprint_differs_for_different_bodies():
    s1 = Snippet(title="a", body="one")
    s2 = Snippet(title="a", body="two")
    assert s1.fingerprint() != s2.fingerprint()


def test_to_dict_includes_author_when_present(sql_snippet):
    d = sql_snippet.to_dict()
    assert "author" in d


def test_to_dict_skips_author_when_blank(python_snippet):
    d = python_snippet.to_dict()
    assert "author" not in d


def test_validate_missing_id_raises():
    s = Snippet(title="x", body="b")
    s.id = ""
    with pytest.raises(InvalidSnippetError):
        s.validate()
