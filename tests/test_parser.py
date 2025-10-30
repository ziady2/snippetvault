from datetime import datetime

from snippetbox import parser


def test_parse_date_iso():
    out = parser.parse_date("2025-01-15")
    assert out is not None
    assert out.year == 2025


def test_parse_date_iso_with_z():
    out = parser.parse_date("2025-01-15T10:30:00Z")
    assert out is not None


def test_parse_date_slash_format():
    assert parser.parse_date("2025/01/15") is not None


def test_parse_date_blank_returns_none():
    assert parser.parse_date("") is None
    assert parser.parse_date(None) is None


def test_parse_date_unrecognised():
    assert parser.parse_date("not a date") is None


def test_parse_int_valid():
    assert parser.parse_int("42") == 42


def test_parse_int_invalid_uses_default():
    assert parser.parse_int("xx", default=99) == 99


def test_parse_int_none_returns_default():
    assert parser.parse_int(None, default=7) == 7


def test_parse_float_valid():
    assert parser.parse_float("3.14") == 3.14


def test_parse_float_invalid_default():
    assert parser.parse_float("nope", default=0.0) == 0.0


def test_parse_bool_true_values():
    for v in ("y", "yes", "true", "1", "on", "True"):
        assert parser.parse_bool(v) is True


def test_parse_bool_false_values():
    for v in ("n", "no", "false", "0", "off"):
        assert parser.parse_bool(v) is False


def test_parse_bool_actual_bool():
    assert parser.parse_bool(True) is True
    assert parser.parse_bool(False) is False


def test_parse_bool_unknown_returns_none():
    assert parser.parse_bool("maybe") is None


def test_parse_bool_none_returns_none():
    assert parser.parse_bool(None) is None


def test_split_lines_normalises_eol():
    assert parser.split_lines("a\r\nb\rc") == ["a", "b", "c"]


def test_split_lines_blank_input():
    assert parser.split_lines("") == []


def test_squeeze_whitespace():
    assert parser.squeeze_whitespace("  a  b\nc  ") == "a b c"


def test_squeeze_whitespace_blank():
    assert parser.squeeze_whitespace("") == ""


def test_parse_kv_equals():
    assert parser.parse_kv("key = value") == ("key", "value")


def test_parse_kv_colon():
    assert parser.parse_kv("key: value") == ("key", "value")


def test_parse_kv_quoted_value():
    assert parser.parse_kv('key = "with spaces"') == ("key", "with spaces")


def test_parse_kv_blank_returns_none():
    assert parser.parse_kv("") is None
    assert parser.parse_kv("   ") is None


def test_parse_kv_comment_returns_none():
    assert parser.parse_kv("# comment") is None


def test_parse_kv_block():
    text = "a = 1\nb = 2\n# comment\n"
    out = parser.parse_kv_block(text)
    assert out == {"a": "1", "b": "2"}


def test_detect_indent_default():
    assert parser.detect_indent("foo\nbar") == 4


def test_detect_indent_two_spaces():
    assert parser.detect_indent("def f():\n  return 1") == 2


def test_detect_eol_crlf():
    assert parser.detect_eol("a\r\nb") == "\r\n"


def test_detect_eol_lf():
    assert parser.detect_eol("a\nb") == "\n"


def test_parse_int_list_simple():
    assert parser.parse_int_list("1,3,5") == [1, 3, 5]


def test_parse_int_list_range():
    assert parser.parse_int_list("1-3") == [1, 2, 3]


def test_parse_int_list_combined():
    assert parser.parse_int_list("1,3-5,8") == [1, 3, 4, 5, 8]


def test_parse_int_list_empty():
    assert parser.parse_int_list("") == []


def test_parse_int_list_skips_invalid():
    assert parser.parse_int_list("1,xx,3") == [1, 3]


def test_normalise_newlines():
    assert parser.normalise_newlines("a\r\nb") == "a\nb"


def test_normalise_newlines_blank():
    assert parser.normalise_newlines("") == ""


def test_parse_size_bytes():
    assert parser.parse_size("100") == 100


def test_parse_size_kb():
    assert parser.parse_size("2kb") == 2048


def test_parse_size_mb_uppercase():
    assert parser.parse_size("4MB") == 4 * 1024 * 1024


def test_parse_size_gb():
    assert parser.parse_size("1g") == 1024 ** 3


def test_parse_size_invalid_returns_none():
    assert parser.parse_size("not a size") is None


def test_to_iso_naive_datetime():
    out = parser.to_iso(datetime(2024, 1, 1, 0, 0, 0))
    assert "2024" in out
    assert "+" in out or "Z" in out


def test_first_nonblank_line():
    assert parser.first_nonblank_line("\n\nhello\nworld") == "hello"


def test_first_nonblank_line_all_blank():
    assert parser.first_nonblank_line("\n\n\n") == ""


def test_truncate_short_text():
    assert parser.truncate("abc", length=10) == "abc"


def test_truncate_long_text():
    out = parser.truncate("a" * 200, length=10)
    assert len(out) <= 10


def test_truncate_blank():
    assert parser.truncate("", length=10) == ""
