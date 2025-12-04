from snippetbox import tag


def test_normalise_strips_and_lowers():
    assert tag.normalise("  Hello  World  ") == "hello world"


def test_normalise_drops_leading_hash():
    assert tag.normalise("#python") == "python"


def test_normalise_handles_none():
    assert tag.normalise(None) == ""


def test_is_reserved_handles_synonyms():
    assert tag.is_reserved("all") is True
    assert tag.is_reserved("Trash") is True


def test_is_reserved_for_normal_tag():
    assert tag.is_reserved("python") is False


def test_is_valid_basic():
    assert tag.is_valid("python") is True


def test_is_valid_blank_invalid():
    assert tag.is_valid("") is False
    assert tag.is_valid("    ") is False


def test_is_valid_reserved_invalid():
    assert tag.is_valid("all") is False


def test_is_valid_too_long():
    assert tag.is_valid("x" * 65) is False


def test_is_valid_with_separators():
    assert tag.is_valid("a,b") is False
    assert tag.is_valid("a;b") is False


def test_is_valid_collapses_internal_whitespace():
    assert tag.is_valid("a\nb") is True
    assert tag.normalise("a\nb") == "a b"


def test_parse_returns_clean_list():
    result = tag.parse("python, io, async")
    assert result == ["python", "io", "async"]


def test_parse_dedupes():
    assert tag.parse("python,python,io") == ["python", "io"]


def test_parse_handles_blank():
    assert tag.parse("") == []
    assert tag.parse(None) == []


def test_parse_supports_semicolons():
    assert tag.parse("a;b;c") == ["a", "b", "c"]


def test_parse_skips_blanks():
    assert tag.parse("a, , b,") == ["a", "b"]


def test_join_round_trip():
    result = tag.join(tag.parse("python, io"))
    assert "python" in result
    assert "io" in result


def test_join_drops_blanks():
    assert tag.join(["", "x"]) == "x"


def test_merge_keeps_order_and_dedupes():
    out = tag.merge(["a", "b"], ["b", "c"], ["d"])
    assert out == ["a", "b", "c", "d"]


def test_diff_added_removed():
    added, removed = tag.diff(["a", "b"], ["b", "c"])
    assert added == ["c"]
    assert removed == ["a"]


def test_diff_no_changes():
    added, removed = tag.diff(["a"], ["a"])
    assert added == []
    assert removed == []


def test_common_intersection():
    out = tag.common(["a", "b", "c"], ["b", "c"], ["c", "d"])
    assert out == ["c"]


def test_common_empty_inputs():
    assert tag.common() == []


def test_sort_alpha_dedupes_and_sorts():
    assert tag.sort_alpha(["b", "a", "a", "c"]) == ["a", "b", "c"]


def test_sort_by_count_orders_high_to_low():
    out = tag.sort_by_count({"a": 1, "b": 5, "c": 3})
    assert out == [("b", 5), ("c", 3), ("a", 1)]


def test_with_prefix():
    out = tag.with_prefix("py", ["python", "javascript", "pytorch"])
    assert "python" in out
    assert "pytorch" in out
    assert "javascript" not in out


def test_strip_hash():
    assert tag.strip_hash("#python") == "python"
    assert tag.strip_hash("python") == "python"


def test_humanise_simple():
    assert tag.humanise("web-dev") == "Web Dev"


def test_humanise_blank():
    assert tag.humanise("") == ""


def test_from_csv_cell_pipe_or_comma():
    assert tag.from_csv_cell("a|b|c") == ["a", "b", "c"]
    assert tag.from_csv_cell("a,b") == ["a", "b"]


def test_to_csv_cell_uses_pipe():
    assert tag.to_csv_cell(["a", "b"]) == "a|b"


def test_tag_dataclass_normalises_name():
    t = tag.Tag(name="  Python ")
    assert t.name == "python"


def test_tag_dataclass_default_fields():
    t = tag.Tag(name="x")
    assert t.colour == ""
    assert t.description == ""
