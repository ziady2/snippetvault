from snippetbox import errors


def test_base_class_inherits_from_exception():
    assert issubclass(errors.SnippetboxError, Exception)


def test_book_not_found_carries_path():
    e = errors.BookNotFoundError("/tmp/missing.json")
    assert e.path == "/tmp/missing.json"
    assert "missing.json" in str(e)


def test_duplicate_slug_repr():
    e = errors.DuplicateSlugError("abc-def")
    assert "abc-def" in str(e)
    assert e.slug == "abc-def"


def test_invalid_snippet_optional_field():
    e = errors.InvalidSnippetError("bad", field="title")
    assert e.field == "title"
    assert "bad" in str(e)


def test_invalid_snippet_no_field():
    e = errors.InvalidSnippetError("bad")
    assert e.field is None


def test_migration_error_carries_versions():
    e = errors.MigrationError("oops", from_v=1, to_v=2)
    assert e.from_v == 1
    assert e.to_v == 2


def test_plugin_error_carries_name():
    e = errors.PluginError("xyz", "broke")
    assert e.name == "xyz"
    assert "xyz" in str(e)
    assert "broke" in str(e)


def test_io_format_error_carries_codec():
    e = errors.IOFormatError("csv", "missing column")
    assert e.codec == "csv"
    assert "csv" in str(e)


def test_search_error_inherits_base():
    assert issubclass(errors.SearchError, errors.SnippetboxError)


def test_config_error_inherits_base():
    assert issubclass(errors.ConfigError, errors.SnippetboxError)


def test_audit_error_inherits_base():
    assert issubclass(errors.AuditError, errors.SnippetboxError)


def test_wrap_passes_snippetbox_through():
    inner = errors.PluginError("foo", "bar")
    out = errors.wrap(inner)
    assert out is inner


def test_wrap_with_codec():
    out = errors.wrap(ValueError("x"), codec="json")
    assert isinstance(out, errors.IOFormatError)
    assert out.codec == "json"


def test_wrap_no_codec():
    out = errors.wrap(ValueError("x"))
    assert isinstance(out, errors.SnippetboxError)
    assert "x" in str(out)


def test_all_subclasses_are_snippetbox_errors():
    for cls in (
        errors.BookNotFoundError,
        errors.DuplicateSlugError,
        errors.InvalidSnippetError,
        errors.MigrationError,
        errors.PluginError,
        errors.SearchError,
        errors.IOFormatError,
        errors.ConfigError,
        errors.AuditError,
    ):
        assert issubclass(cls, errors.SnippetboxError)
