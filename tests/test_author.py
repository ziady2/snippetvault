from snippetbox.author import Author, equal, unique, from_git_format


def test_default_author_is_blank():
    a = Author()
    assert a.is_blank() is True
    assert bool(a) is False


def test_author_strips_whitespace():
    a = Author(name="  Ziad  ", email="  z@example.com ", url="  https://x ")
    assert a.name == "Ziad"
    assert a.email == "z@example.com"
    assert a.url == "https://x"


def test_display_name_and_email():
    a = Author(name="Z", email="z@x")
    assert a.display() == "Z <z@x>"


def test_display_name_only():
    a = Author(name="Z")
    assert a.display() == "Z"


def test_display_email_only():
    a = Author(email="z@x")
    assert a.display() == "z@x"


def test_display_url_only():
    a = Author(url="https://example.com")
    assert a.display() == "https://example.com"


def test_display_anonymous():
    assert Author().display() == "anonymous"


def test_to_dict_skips_blanks():
    a = Author(name="Z")
    assert a.to_dict() == {"name": "Z"}


def test_to_dict_full():
    a = Author(name="Z", email="z@x", url="u")
    assert a.to_dict() == {"name": "Z", "email": "z@x", "url": "u"}


def test_from_dict_none_returns_blank():
    a = Author.from_dict(None)
    assert a.is_blank() is True


def test_from_dict_partial():
    a = Author.from_dict({"name": "Z"})
    assert a.name == "Z"


def test_from_string_blank():
    assert Author.from_string("").is_blank()


def test_from_string_name_email():
    a = Author.from_string("Z <z@x>")
    assert a.name == "Z"
    assert a.email == "z@x"


def test_from_string_bare_email():
    a = Author.from_string("z@x.io")
    assert a.email == "z@x.io"
    assert a.name == ""


def test_from_string_url():
    a = Author.from_string("https://example.com")
    assert a.url == "https://example.com"


def test_from_string_bare_name():
    a = Author.from_string("Just Me")
    assert a.name == "Just Me"


def test_with_email_returns_new():
    a = Author(name="Z")
    b = a.with_email("z@x")
    assert b is not a
    assert b.email == "z@x"
    assert a.email == ""


def test_with_name_returns_new():
    a = Author(email="z@x")
    b = a.with_name("Z")
    assert b.name == "Z"


def test_equal_case_insensitive():
    a = Author(name="Z", email="z@x")
    b = Author(name="z", email="Z@X")
    assert equal(a, b) is True


def test_equal_different():
    a = Author(name="Z")
    b = Author(name="A")
    assert equal(a, b) is False


def test_unique_drops_duplicates_and_blanks():
    out = unique([Author(name="Z"), Author(), Author(name="z"), Author(name="A")])
    names = [a.name for a in out]
    assert names == ["Z", "A"]


def test_from_git_format_with_email():
    a = from_git_format("Z <z@x> 1234567890 +0000")
    assert a.name == "Z"
    assert a.email == "z@x"


def test_from_git_format_blank():
    assert from_git_format("").is_blank()


def test_from_git_format_no_email_ish():
    a = from_git_format("Just A Name")
    assert a.name == "Just A Name"


def test_from_git_format_no_email_with_brackets():
    a = from_git_format("Foo")
    assert a.name == "Foo"


def test_to_dict_round_trip():
    a = Author(name="Z", email="z@x", url="u")
    b = Author.from_dict(a.to_dict())
    assert b.name == a.name
    assert b.email == a.email
    assert b.url == a.url
