import pytest

from snippetbox import io_textmate
from snippetbox.errors import IOFormatError
from snippetbox.snippet import Snippet


def test_export_includes_root_tag(python_snippet):
    out = io_textmate.export_snippets([python_snippet])
    assert "<snippets>" in out
    assert "</snippets>" in out


def test_export_includes_name(python_snippet):
    out = io_textmate.export_snippets([python_snippet])
    assert "tail a file" in out


def test_export_includes_scope(python_snippet):
    out = io_textmate.export_snippets([python_snippet])
    assert "source.python" in out


def test_export_uses_text_plain_for_plain():
    s = Snippet(title="x", body="y", language="plain")
    out = io_textmate.export_snippets([s])
    assert "text.plain" in out


def test_export_includes_tab_trigger():
    s = Snippet(title="x", body="y", slug="my-trig", language="python")
    out = io_textmate.export_snippets([s])
    assert "my-trig" in out


def test_round_trip(python_snippet):
    out = io_textmate.export_snippets([python_snippet])
    back = io_textmate.import_snippets(out)
    assert len(back) == 1
    assert back[0].title == python_snippet.title
    assert back[0].body == python_snippet.body
    assert back[0].language == python_snippet.language


def test_import_blank():
    assert io_textmate.import_snippets("") == []


def test_import_no_snippets_in_text():
    assert io_textmate.import_snippets("<other></other>") == []


def test_import_partial_snippet_raises():
    text = "<snippet>broken"
    with pytest.raises(IOFormatError):
        io_textmate.import_snippets(text)


def test_import_handles_text_plain_scope():
    text = (
        "<snippet>\n"
        "  <name>n</name>\n"
        "  <scope>text.plain</scope>\n"
        "  <content><![CDATA[x]]></content>\n"
        "</snippet>"
    )
    out = io_textmate.import_snippets(text)
    assert out[0].language == "plain"


def test_import_unknown_scope_returns_raw():
    text = (
        "<snippet>\n"
        "  <name>n</name>\n"
        "  <scope>weird.xyz</scope>\n"
        "  <content><![CDATA[x]]></content>\n"
        "</snippet>"
    )
    out = io_textmate.import_snippets(text)
    assert out[0].language == "weird.xyz"


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.xml"
    io_textmate.export_to_file([python_snippet], target)
    back = io_textmate.import_from_file(target)
    assert len(back) == 1


def test_import_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_textmate.import_from_file(tmp_path / "missing.xml")


def test_import_skips_snippets_without_content():
    text = """\
<snippets>
  <snippet>
    <name>n</name>
    <scope>source.python</scope>
  </snippet>
</snippets>
"""
    out = io_textmate.import_snippets(text)
    assert out == []
