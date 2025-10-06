from snippetbox import language


def test_all_languages_returns_tuple():
    langs = language.all_languages()
    assert isinstance(langs, tuple)
    assert len(langs) >= 20


def test_by_name_python():
    lang = language.by_name("python")
    assert lang.name == "python"


def test_by_name_alias_returns_canonical():
    assert language.by_name("py").name == "python"
    assert language.by_name("js").name == "javascript"
    assert language.by_name("c++").name == "cpp"


def test_by_name_case_insensitive():
    assert language.by_name("PYTHON").name == "python"


def test_by_name_blank_returns_plain():
    assert language.by_name("").name == "plain"
    assert language.by_name(None).name == "plain"


def test_by_name_unknown_returns_plain():
    assert language.by_name("klingon").name == "plain"


def test_by_extension_with_dot():
    assert language.by_extension(".py").name == "python"


def test_by_extension_without_dot():
    assert language.by_extension("py").name == "python"


def test_by_extension_blank_returns_plain():
    assert language.by_extension("").name == "plain"


def test_by_extension_unknown_returns_plain():
    assert language.by_extension(".xyz").name == "plain"


def test_get_plain_returns_last_entry():
    assert language.get_plain().name == "plain"


def test_family_helper():
    assert language.family(language.by_name("python")) == "dynamic"


def test_names_includes_python_and_plain():
    names = language.names()
    assert "python" in names
    assert "plain" in names


def test_is_known_truthy():
    assert language.is_known("python") is True


def test_is_known_unknown_returns_false():
    assert language.is_known("klingon") is False
    assert language.is_known("") is False


def test_comment_token_for_python():
    assert language.comment_token(language.by_name("python")) == "#"


def test_block_tokens_for_javascript():
    assert language.block_tokens(language.by_name("javascript")) == ("/*", "*/")


def test_filter_by_family():
    result = language.filter_by_family("static")
    assert all(language.family == "static" for language in result)
    assert any(language.name == "rust" for language in result)


def test_guess_from_filename_python():
    assert language.guess_from_filename("foo.py").name == "python"


def test_guess_from_filename_no_extension():
    assert language.guess_from_filename("Makefile").name == "plain"


def test_normalise_name_canonical():
    assert language.normalise_name("py") == "python"


def test_normalise_name_unknown_returns_blank():
    assert language.normalise_name("klingon") == ""


def test_normalise_name_explicit_plain():
    assert language.normalise_name("plain") == "plain"


def test_suggest_returns_matches():
    suggestions = language.suggest("py")
    assert "python" in suggestions


def test_suggest_limit_respected():
    suggestions = language.suggest("", limit=3)
    assert len(suggestions) <= 3


def test_families_unique_in_order():
    fams = language.families()
    assert len(fams) == len(set(fams))


def test_from_iterable_drops_unknowns():
    langs = language.from_iterable(["python", "klingon", "go"])
    names = [language.name for language in langs]
    assert names == ["python", "go"]


def test_matches_alias():
    py = language.by_name("python")
    assert py.matches("py") is True
    assert py.matches("python3") is True
    assert py.matches("klingon") is False
