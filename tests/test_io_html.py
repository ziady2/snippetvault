from snippetbox import io_html
from snippetbox.snippet import Snippet


def test_render_includes_title(python_snippet):
    out = io_html.render([python_snippet], title="My Box")
    assert "<title>My Box</title>" in out


def test_render_escapes_body():
    s = Snippet(title="x", body="<script>alert(1)</script>", language="html")
    out = io_html.render([s])
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_includes_toc_links(python_snippet):
    out = io_html.render([python_snippet])
    assert "<nav" in out
    assert "<a href=" in out


def test_render_minimal_returns_section(python_snippet):
    out = io_html.render_minimal(python_snippet)
    assert out.startswith("<section")


def test_render_index_with_snippets(python_snippet):
    out = io_html.render_index([python_snippet])
    assert "<ul>" in out
    assert "<li>" in out


def test_render_index_empty():
    assert "no snippets" in io_html.render_index([]).lower()


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.html"
    io_html.export_to_file([python_snippet], target)
    text = target.read_text(encoding="utf-8")
    assert "<html>" in text


def test_render_uses_anchor_for_slug():
    s = Snippet(title="Hello world", body="x", language="python", slug="hello-world")
    out = io_html.render([s])
    assert "id=\"hello-world\"" in out


def test_render_meta_includes_language():
    s = Snippet(title="t", body="x", language="python")
    out = io_html.render([s])
    assert "language" in out


def test_render_includes_author_when_present(sql_snippet):
    out = io_html.render([sql_snippet])
    assert "author" in out


def test_render_skips_author_when_blank(python_snippet):
    out = io_html.render([python_snippet])
    assert "author" not in out


def test_render_includes_tags(python_snippet):
    out = io_html.render([python_snippet])
    assert "tag" in out
    assert "io" in out


def test_render_includes_notes_when_present():
    s = Snippet(title="t", body="x", language="python", notes="a note")
    out = io_html.render([s])
    assert "a note" in out


def test_render_skips_notes_when_blank(python_snippet):
    out = io_html.render([python_snippet])
    assert "notes:" not in out


def test_anchor_stable_for_simple_text():
    out = io_html._anchor("Hello World")
    assert out == "hello-world"


def test_anchor_for_blank():
    assert io_html._anchor("") == "snippet"


def test_render_handles_empty_list():
    out = io_html.render([])
    assert "<html>" in out
