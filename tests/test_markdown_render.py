from snippetbox import markdown_render
from snippetbox.snippet import Snippet


def test_render_one_includes_title(python_snippet):
    out = markdown_render.render_one(python_snippet)
    assert "tail a file" in out


def test_render_one_has_code_fence(python_snippet):
    out = markdown_render.render_one(python_snippet)
    assert "```python" in out


def test_render_one_includes_tags(python_snippet):
    out = markdown_render.render_one(python_snippet)
    assert "io" in out
    assert "async" in out


def test_render_one_without_meta(python_snippet):
    out = markdown_render.render_one(python_snippet, include_meta=False)
    assert "language" not in out


def test_render_one_untitled():
    s = Snippet(title="", body="x", language="python")
    out = markdown_render.render_one(s)
    assert "untitled" in out


def test_render_many_with_toc(populated_book):
    out = markdown_render.render_many(populated_book, include_toc=True)
    assert "Contents" in out


def test_render_many_without_toc(populated_book):
    out = markdown_render.render_many(populated_book, include_toc=False)
    assert "Contents" not in out


def test_render_many_uses_title():
    s = Snippet(title="x", body="b", language="python")
    out = markdown_render.render_many([s], title="My Snippets")
    assert "# My Snippets" in out


def test_code_fence_with_language():
    assert markdown_render.code_fence("python", "x") == "```python\nx\n```"


def test_code_fence_no_language():
    assert markdown_render.code_fence("plain", "x") == "```\nx\n```"


def test_inline_code_simple():
    assert markdown_render.inline_code("x") == "`x`"


def test_inline_code_with_backtick():
    assert "``" in markdown_render.inline_code("a`b")


def test_render_minimal_just_fence(python_snippet):
    out = markdown_render.render_minimal(python_snippet)
    assert out.startswith("```python")


def test_link_basic():
    assert markdown_render.link("text", "http://x") == "[text](http://x)"


def test_link_escapes_brackets():
    out = markdown_render.link("[a]", "http://x")
    assert "\\[a\\]" in out


def test_render_table_with_headers():
    out = markdown_render.render_table([("a", 1), ("b", 2)], headers=["k", "v"])
    assert "| k | v |" in out


def test_render_table_no_headers():
    out = markdown_render.render_table([("a", 1)])
    assert "| a | 1 |" in out


def test_bulleted():
    out = markdown_render.bulleted(["a", "b", "c"])
    assert out.split("\n") == ["- a", "- b", "- c"]


def test_heading_levels():
    assert markdown_render.heading("h", 1) == "# h"
    assert markdown_render.heading("h", 3) == "### h"


def test_heading_clamped():
    assert markdown_render.heading("h", 0) == "# h"
    assert markdown_render.heading("h", 99) == "###### h"


def test_render_for_static_site_has_frontmatter(python_snippet):
    out = markdown_render.render_for_static_site(python_snippet)
    assert out.startswith("---")
    assert "title:" in out


def test_render_one_meta_with_source():
    s = Snippet(title="x", body="b", language="python", source="https://x", notes="n")
    out = markdown_render.render_one(s)
    assert "https://x" in out
    assert "n" in out
