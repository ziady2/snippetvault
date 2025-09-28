import json

import pytest

from snippetbox import io_vscode
from snippetbox.errors import IOFormatError
from snippetbox.snippet import Snippet


def test_export_returns_json_object(python_snippet):
    out = io_vscode.export_snippets([python_snippet])
    data = json.loads(out)
    assert isinstance(data, dict)


def test_export_uses_title_as_key(python_snippet):
    out = io_vscode.export_snippets([python_snippet])
    data = json.loads(out)
    assert any("tail a file" in k for k in data.keys())


def test_export_handles_dup_titles():
    a = Snippet(title="same", body="x", language="python")
    b = Snippet(title="same", body="y", language="python")
    out = io_vscode.export_snippets([a, b])
    data = json.loads(out)
    assert len(data) == 2


def test_round_trip_via_export(python_snippet):
    out = io_vscode.export_snippets([python_snippet])
    back = io_vscode.import_snippets(out)
    assert len(back) == 1
    assert back[0].body.strip() == python_snippet.body.strip()


def test_import_blank():
    assert io_vscode.import_snippets("") == []


def test_import_invalid_json():
    with pytest.raises(IOFormatError):
        io_vscode.import_snippets("not json")


def test_import_array_top_level_raises():
    with pytest.raises(IOFormatError):
        io_vscode.import_snippets("[1, 2, 3]")


def test_import_skips_non_dict_values():
    payload = '{"foo": 1, "bar": {"prefix": "p", "body": "x"}}'
    out = io_vscode.import_snippets(payload)
    assert len(out) == 1


def test_import_string_body():
    payload = '{"foo": {"prefix": "p", "body": "single line"}}'
    out = io_vscode.import_snippets(payload)
    assert "single line" in out[0].body


def test_import_array_body():
    payload = '{"foo": {"prefix": "p", "body": ["a", "b"]}}'
    out = io_vscode.import_snippets(payload)
    assert "a\nb" in out[0].body


def test_import_uses_first_scope_language():
    payload = '{"foo": {"prefix": "p", "body": "x", "scope": "python,javascript"}}'
    out = io_vscode.import_snippets(payload)
    assert out[0].language == "python"


def test_import_uses_description_as_notes():
    payload = '{"foo": {"prefix": "p", "body": "x", "description": "a note"}}'
    out = io_vscode.import_snippets(payload)
    assert out[0].notes == "a note"


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.json"
    io_vscode.export_to_file([python_snippet], target)
    back = io_vscode.import_from_file(target)
    assert len(back) == 1


def test_import_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_vscode.import_from_file(tmp_path / "missing.json")


def test_export_includes_scope_for_language():
    s = Snippet(title="x", body="y", language="python")
    data = json.loads(io_vscode.export_snippets([s]))
    entry = list(data.values())[0]
    assert entry.get("scope") == "python"
