import pytest

from snippetbox import io_csv
from snippetbox.errors import IOFormatError


def test_export_includes_header(python_snippet):
    out = io_csv.export_snippets([python_snippet])
    assert "title,language" in out


def test_round_trip(python_snippet):
    out = io_csv.export_snippets([python_snippet])
    back = io_csv.import_snippets(out)
    assert len(back) == 1
    assert back[0].body.replace("\r\n", "\n") == python_snippet.body


def test_export_handles_multiline_body(python_snippet):
    out = io_csv.export_snippets([python_snippet])
    back = io_csv.import_snippets(out)
    assert "asyncio" in back[0].body


def test_import_blank():
    assert io_csv.import_snippets("") == []


def test_import_no_header_raises():
    with pytest.raises(IOFormatError):
        io_csv.import_snippets("\n")


def test_import_missing_required_columns():
    text = "id,language\n1,python\n"
    with pytest.raises(IOFormatError):
        io_csv.import_snippets(text)


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.csv"
    io_csv.export_to_file([python_snippet], target)
    back = io_csv.import_from_file(target)
    assert len(back) == 1


def test_import_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_csv.import_from_file(tmp_path / "missing.csv")


def test_export_handles_tags(python_snippet):
    out = io_csv.export_snippets([python_snippet])
    back = io_csv.import_snippets(out)
    assert set(back[0].tags) == set(python_snippet.tags)


def test_export_handles_notes_with_newline():
    from snippetbox.snippet import Snippet

    s = Snippet(title="t", body="b", language="python", notes="line1\nline2")
    out = io_csv.export_snippets([s])
    back = io_csv.import_snippets(out)
    assert "line1" in back[0].notes
    assert "line2" in back[0].notes


def test_detect_dialect_comma():
    assert io_csv.detect_dialect("a,b,c\n1,2,3") == "comma"


def test_detect_dialect_tab():
    assert io_csv.detect_dialect("a\tb\tc") == "tab"


def test_detect_dialect_semicolon():
    assert io_csv.detect_dialect("a;b;c") == "semicolon"


def test_detect_dialect_blank():
    assert io_csv.detect_dialect("") == "comma"


def test_export_includes_id_and_slug(python_snippet):
    out = io_csv.export_snippets([python_snippet])
    assert python_snippet.id in out
