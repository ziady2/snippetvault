import pytest

from snippetbox import io_markdown
from snippetbox.errors import IOFormatError


def test_export_round_trip_keeps_title(python_snippet):
    text = io_markdown.export_snippets([python_snippet])
    back = io_markdown.import_snippets(text)
    assert any("tail a file" in s.title for s in back)


def test_export_round_trip_keeps_body(python_snippet):
    text = io_markdown.export_snippets([python_snippet])
    back = io_markdown.import_snippets(text)
    assert "asyncio" in back[0].body


def test_export_round_trip_keeps_language(python_snippet):
    text = io_markdown.export_snippets([python_snippet])
    back = io_markdown.import_snippets(text)
    assert back[0].language == "python"


def test_export_round_trip_keeps_tags(python_snippet):
    text = io_markdown.export_snippets([python_snippet])
    back = io_markdown.import_snippets(text)
    assert set(back[0].tags) == set(python_snippet.tags)


def test_import_blank_text():
    assert io_markdown.import_snippets("") == []


def test_import_with_no_fence_skips():
    text = "# Just a heading\n\nsome prose"
    assert io_markdown.import_snippets(text) == []


def test_import_with_extra_meta():
    text = """\
# T

- language: python
- tags: a, b
- source: http://x
- notes: a note

```python
print("hi")
```
"""
    out = io_markdown.import_snippets(text)
    assert out
    assert out[0].source == "http://x"
    assert out[0].notes == "a note"


def test_import_explicit_language_in_fence():
    text = """\
# T

```javascript
console.log(1)
```
"""
    out = io_markdown.import_snippets(text)
    assert out[0].language == "javascript"


def test_import_no_meta_lines():
    text = """\
# T

```python
1+1
```
"""
    out = io_markdown.import_snippets(text)
    assert out[0].body == "1+1"


def test_export_to_file_round_trip(tmp_path, python_snippet):
    target = tmp_path / "out.md"
    io_markdown.export_to_file([python_snippet], target)
    back = io_markdown.import_from_file(target)
    assert len(back) == 1


def test_import_from_missing_file(tmp_path):
    with pytest.raises(IOFormatError):
        io_markdown.import_from_file(tmp_path / "missing.md")


def test_split_codefences_returns_bodies():
    text = "before\n```\na\n```\nbetween\n```python\nb\n```\nafter"
    out = io_markdown.split_codefences(text)
    assert "a" in out
    assert "b" in out


def test_split_codefences_blank():
    assert io_markdown.split_codefences("") == []


def test_import_with_auto_tags_meta():
    text = """\
# T

- language: python
- auto-tags: io, json

```python
1
```
"""
    out = io_markdown.import_snippets(text)
    assert "io" in out[0].auto_tags


def test_split_codefences_unterminated():
    text = "```\na\nb"
    out = io_markdown.split_codefences(text)
    assert "a" in out[0]


def test_import_uses_meta_language_when_fence_blank():
    text = """\
# T

- language: python

```
print("hi")
```
"""
    out = io_markdown.import_snippets(text)
    assert out[0].language == "python"
