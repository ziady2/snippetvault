from snippetbox import validators


def test_validate_slug_valid():
    assert validators.validate_slug("hello-world") is None


def test_validate_slug_blank():
    assert validators.validate_slug("") is not None


def test_validate_slug_too_long():
    assert validators.validate_slug("a" * 81) is not None


def test_validate_slug_uppercase_invalid():
    assert validators.validate_slug("HELLO") is not None


def test_validate_slug_with_underscores_invalid():
    assert validators.validate_slug("hello_world") is not None


def test_validate_slug_trailing_hyphen_invalid():
    assert validators.validate_slug("hello-") is not None


def test_validate_title_blank_ok():
    assert validators.validate_title("") is None


def test_validate_title_with_newline():
    assert validators.validate_title("a\nb") is not None


def test_validate_title_too_long():
    assert validators.validate_title("x" * 201) is not None


def test_validate_title_normal():
    assert validators.validate_title("Tail a file") is None


def test_validate_language_known():
    assert validators.validate_language("python") is None


def test_validate_language_unknown():
    assert validators.validate_language("klingon") is not None


def test_validate_language_blank():
    assert validators.validate_language("") is not None


def test_validate_tags_ok():
    assert validators.validate_tags(["a", "b"]) is None


def test_validate_tags_invalid_member():
    assert validators.validate_tags(["a", ""]) is not None


def test_validate_tags_duplicate():
    assert validators.validate_tags(["a", "a"]) is not None


def test_validate_tags_none_ok():
    assert validators.validate_tags(None) is None  # type: ignore[arg-type]


def test_validate_email_blank_ok():
    assert validators.validate_email("") is None


def test_validate_email_normal():
    assert validators.validate_email("z@x.io") is None


def test_validate_email_bad():
    assert validators.validate_email("not-an-email") is not None


def test_validate_url_blank_ok():
    assert validators.validate_url("") is None


def test_validate_url_normal():
    assert validators.validate_url("https://example.com") is None


def test_validate_url_bad():
    assert validators.validate_url("not a url") is not None


def test_validate_body_normal():
    assert validators.validate_body("print('hi')") is None


def test_validate_body_too_short():
    assert validators.validate_body("", min_chars=5) is not None


def test_validate_body_too_long():
    assert validators.validate_body("x" * 100, max_chars=50) is not None


def test_validate_body_none():
    assert validators.validate_body(None) is not None  # type: ignore[arg-type]


def test_validate_collection_name_ok():
    assert validators.validate_collection_name("favs") is None


def test_validate_collection_name_blank():
    assert validators.validate_collection_name("") is not None


def test_validate_collection_name_too_long():
    assert validators.validate_collection_name("x" * 65) is not None


def test_validate_collection_name_with_slash():
    assert validators.validate_collection_name("a/b") is not None
    assert validators.validate_collection_name("a\\b") is not None


def test_collect_errors_filters_none():
    out = validators.collect_errors(None, "x", None, "y")
    assert out == ["x", "y"]


def test_validate_snippet_dict_minimal_valid():
    out = validators.validate_snippet_dict({"title": "x", "language": "python", "body": "code"})
    assert out == []


def test_validate_snippet_dict_unknown_language():
    out = validators.validate_snippet_dict({"title": "x", "language": "xxx", "body": "code"})
    assert out


def test_validate_snippet_dict_non_dict():
    assert validators.validate_snippet_dict("nope") == ["entry is not a dict"]  # type: ignore[arg-type]


def test_validate_snippet_dict_with_bad_slug():
    out = validators.validate_snippet_dict({"title": "x", "language": "python", "body": "b", "slug": "BAD"})
    assert out


def test_is_safe_filename_normal():
    assert validators.is_safe_filename("foo.txt") is True


def test_is_safe_filename_absolute():
    assert validators.is_safe_filename("/foo") is False


def test_is_safe_filename_backslash():
    assert validators.is_safe_filename("foo\\bar") is False


def test_is_safe_filename_dotdot():
    assert validators.is_safe_filename("../etc/passwd") is False


def test_is_safe_filename_blank():
    assert validators.is_safe_filename("") is False


def test_validate_book_non_dict():
    assert validators.validate_book("nope") == ["book is not a dict"]  # type: ignore[arg-type]


def test_validate_book_missing_snippets():
    assert "missing key: snippets" in validators.validate_book({})


def test_validate_book_bad_snippets_field():
    out = validators.validate_book({"snippets": "x"})
    assert any("not a list" in e for e in out)


def test_validate_book_with_bad_snippet():
    out = validators.validate_book({"snippets": [{"title": "x", "language": "klingon", "body": "b"}]})
    assert out


def test_validate_book_duplicate_slug():
    out = validators.validate_book(
        {
            "snippets": [
                {"title": "a", "language": "python", "body": "x", "slug": "same"},
                {"title": "b", "language": "python", "body": "y", "slug": "same"},
            ]
        }
    )
    assert any("duplicate slug" in e for e in out)


def test_is_blank():
    assert validators.is_blank("") is True
    assert validators.is_blank("   ") is True
    assert validators.is_blank("x") is False


def test_first_error_returns_first():
    assert validators.first_error(None, "x", "y") == "x"


def test_first_error_none_when_clean():
    assert validators.first_error(None, None) is None
