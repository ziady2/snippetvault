from snippetbox import highlight
from snippetbox.language import by_name


def test_classify_blank_line():
    line = highlight.classify_line("", by_name("python"))
    assert line.kind == "blank"


def test_classify_comment_line():
    line = highlight.classify_line("# this is a comment", by_name("python"))
    assert line.kind == "comment"


def test_classify_block_comment_starts():
    line = highlight.classify_line("/* opener", by_name("javascript"))
    assert line.kind == "comment"


def test_classify_string_line_python_triple():
    line = highlight.classify_line('"""docstring"""', by_name("python"))
    assert line.kind == "string"


def test_classify_code_line():
    line = highlight.classify_line("x = 1", by_name("python"))
    assert line.kind == "code"


def test_classify_full_text():
    text = "# c\n\nx = 1\n"
    out = highlight.classify(text, "python")
    assert [line.kind for line in out] == ["comment", "blank", "code"]


def test_classify_blank_input():
    assert highlight.classify("", "python") == []


def test_code_lines_filters_comments():
    text = "# comment\nx = 1"
    assert highlight.code_lines(text, "python") == ["x = 1"]


def test_comment_lines():
    text = "# a\nx = 1\n# b"
    out = highlight.comment_lines(text, "python")
    assert "# a" in out
    assert "# b" in out
    assert "x = 1" not in out


def test_strip_comments_drops_lines():
    text = "# a\nx = 1\n# b"
    out = highlight.strip_comments(text, "python")
    assert "x = 1" in out
    assert "# a" not in out


def test_strip_blank_lines():
    text = "a\n\n\nb\n"
    assert highlight.strip_blank_lines(text) == "a\nb"


def test_strip_blank_lines_blank_input():
    assert highlight.strip_blank_lines("") == ""


def test_normalise_indent():
    assert highlight.normalise_indent("\tfoo", tab_size=4) == "    foo"


def test_normalise_indent_blank():
    assert highlight.normalise_indent("") == ""


def test_detect_shebang_present():
    assert highlight.detect_shebang("#!/bin/bash\necho hi") == "/bin/bash"


def test_detect_shebang_absent():
    assert highlight.detect_shebang("echo hi") is None


def test_detect_shebang_blank():
    assert highlight.detect_shebang("") is None


def test_is_likely_python_true():
    assert highlight.is_likely_python("def foo():\n    pass") is True


def test_is_likely_python_false():
    assert highlight.is_likely_python("echo hi") is False


def test_is_likely_javascript_true():
    assert highlight.is_likely_javascript("function foo() {}") is True


def test_is_likely_shell_shebang():
    assert highlight.is_likely_shell("#!/bin/bash\necho hi") is True


def test_is_likely_shell_keyword():
    assert highlight.is_likely_shell("for i in 1 2 3; do echo $i; done") is True


def test_guess_language_python():
    assert highlight.guess_language("import os\nprint(1)") == "python"


def test_guess_language_javascript():
    assert highlight.guess_language("function f() { return 1; }") == "javascript"


def test_guess_language_shell():
    assert highlight.guess_language("#!/bin/sh\necho hi") == "shell"


def test_guess_language_html():
    assert highlight.guess_language("<html><body></body></html>") == "html"


def test_guess_language_json():
    assert highlight.guess_language('{"a": 1}') == "json"


def test_guess_language_blank():
    assert highlight.guess_language("") == "plain"


def test_guess_language_plain_fallback():
    assert highlight.guess_language("just some text") == "plain"


def test_line_density_only_code():
    text = "x = 1\ny = 2"
    assert highlight.line_density(text, "python") == 1.0


def test_line_density_mixed():
    text = "# c\nx = 1"
    assert 0 < highlight.line_density(text, "python") < 1.0


def test_line_density_blank():
    assert highlight.line_density("", "python") == 0.0


def test_code_token_count():
    text = "x = 1\ny = 2"
    assert highlight.code_token_count(text, "python") == 6


def test_code_token_count_blank():
    assert highlight.code_token_count("", "python") == 0


def test_line_helpers_on_dataclass():
    line = highlight.classify_line("# c", by_name("python"))
    assert line.is_comment() is True
    assert line.is_blank() is False
