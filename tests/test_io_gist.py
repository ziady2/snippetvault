import json

import pytest

from snippetbox import io_gist
from snippetbox.errors import IOFormatError


def _gist(files=None, **rest):
    payload = {"description": "x", "html_url": "https://gist", "owner": {"login": "ziad"}, "files": files or {}}
    payload.update(rest)
    return payload


def test_import_one_gist_with_files():
    payload = _gist(files={"a.py": {"content": "print(1)", "language": "Python"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert len(out) == 1
    assert out[0].body == "print(1)"


def test_import_one_gist_lowers_language():
    payload = _gist(files={"a.py": {"content": "x", "language": "Python"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].language == "python"


def test_import_one_gist_uses_description_as_notes():
    payload = _gist(files={"a.py": {"content": "x"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].notes == "x"


def test_import_one_gist_records_url():
    payload = _gist(files={"a.py": {"content": "x"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].source == "https://gist"


def test_import_one_gist_records_author():
    payload = _gist(files={"a.py": {"content": "x"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].author.name == "ziad"


def test_import_list_of_gists():
    a = _gist(files={"a.py": {"content": "x"}})
    b = _gist(files={"b.py": {"content": "y"}})
    out = io_gist.import_snippets(json.dumps([a, b]))
    assert len(out) == 2


def test_import_blank():
    assert io_gist.import_snippets("") == []


def test_import_invalid_json():
    with pytest.raises(IOFormatError):
        io_gist.import_snippets("not json")


def test_import_top_level_string_raises():
    with pytest.raises(IOFormatError):
        io_gist.import_snippets('"a string"')


def test_import_files_not_dict():
    payload = {"files": "nope"}
    out = io_gist.import_snippets(json.dumps(payload))
    assert out == []


def test_import_skips_non_dict_files():
    payload = _gist(files={"a.py": "nope"})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out == []


def test_export_returns_files_dict(python_snippet):
    out = io_gist.export_snippets([python_snippet])
    data = json.loads(out)
    assert "files" in data
    assert any("tail a file" in k for k in data["files"])


def test_round_trip(python_snippet):
    out = io_gist.export_snippets([python_snippet])
    back = io_gist.import_snippets(out)
    assert len(back) == 1
    assert back[0].body == python_snippet.body


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.json"
    io_gist.export_to_file([python_snippet], target)
    back = io_gist.import_from_file(target)
    assert len(back) == 1


def test_import_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_gist.import_from_file(tmp_path / "missing.json")


def test_import_one_gist_handles_blank_filename():
    payload = _gist(files={"": {"content": "x"}})
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].title == ""


def test_import_one_gist_drops_blank_owner():
    payload = {"files": {"a.py": {"content": "x"}}}
    out = io_gist.import_snippets(json.dumps(payload))
    assert out[0].author.is_blank()
