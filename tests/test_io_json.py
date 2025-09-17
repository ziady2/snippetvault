import pytest

from snippetbox import io_json
from snippetbox.errors import IOFormatError


def test_export_snippets_returns_json_string(python_snippet):
    out = io_json.export_snippets([python_snippet])
    assert "snippets" in out
    assert "tail a file" in out


def test_export_snippets_pretty_indent(python_snippet):
    out = io_json.export_snippets([python_snippet], indent=4)
    assert "    " in out


def test_import_snippets_round_trip(python_snippet):
    out = io_json.export_snippets([python_snippet])
    back = io_json.import_snippets(out)
    assert len(back) == 1
    assert back[0].body == python_snippet.body


def test_import_snippets_empty_text():
    assert io_json.import_snippets("") == []


def test_import_snippets_top_level_list():
    out = io_json.import_snippets('[{"title":"x","body":"b"}]')
    assert len(out) == 1


def test_import_snippets_invalid_json():
    with pytest.raises(IOFormatError):
        io_json.import_snippets("not json")


def test_import_snippets_unexpected_shape():
    with pytest.raises(IOFormatError):
        io_json.import_snippets('"a string at the top level"')


def test_import_snippets_skips_non_dict_entries():
    text = '{"snippets": ["x", {"title": "ok", "body": "b"}]}'
    out = io_json.import_snippets(text)
    assert len(out) == 1


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.json"
    io_json.export_to_file([python_snippet], target)
    back = io_json.import_from_file(target)
    assert len(back) == 1


def test_import_from_file_missing(tmp_path):
    with pytest.raises(IOFormatError):
        io_json.import_from_file(tmp_path / "missing.json")


def test_round_trip_helper(python_snippet):
    out = io_json.round_trip([python_snippet])
    assert out[0].body == python_snippet.body


def test_write_pretty(tmp_path, python_snippet):
    target = tmp_path / "p.json"
    io_json.write_pretty([python_snippet], target)
    assert "    " in target.read_text(encoding="utf-8")


def test_write_compact(tmp_path, python_snippet):
    target = tmp_path / "c.json"
    io_json.write_compact([python_snippet], target)
    text = target.read_text(encoding="utf-8")
    assert text


def test_import_handles_extra_fields():
    text = '{"snippets": [{"title": "x", "body": "b", "extra": {"k": "v"}}]}'
    out = io_json.import_snippets(text)
    assert out[0].extra == {"k": "v"}


def test_export_snippets_empty():
    assert "snippets" in io_json.export_snippets([])
