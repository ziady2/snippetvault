from snippetbox import lint
from snippetbox.snippet import Snippet


def test_lint_snippet_clean(python_snippet):
    issues = lint.lint_snippet(python_snippet)
    assert all(i.severity != "error" for i in issues)


def test_lint_snippet_empty_body():
    s = Snippet(title="x", body="")
    s.body = ""
    issues = lint.lint_snippet(s)
    assert any(i.code == "EMPTY_BODY" for i in issues)


def test_lint_snippet_no_title():
    s = Snippet(title="", body="x = 1", language="python")
    issues = lint.lint_snippet(s)
    assert any(i.code == "NO_TITLE" for i in issues)


def test_lint_snippet_punctuation_only_title():
    s = Snippet(title="!!!", body="x", language="python")
    issues = lint.lint_snippet(s)
    assert any(i.code == "BAD_TITLE" for i in issues)


def test_lint_snippet_maybe_lang():
    s = Snippet(title="hi", body="def foo(): return 1", language="plain")
    issues = lint.lint_snippet(s)
    assert any(i.code == "MAYBE_LANG" for i in issues)


def test_lint_snippet_only_comments():
    s = Snippet(title="x", body="# only\n# comments", language="python")
    issues = lint.lint_snippet(s)
    assert any(i.code == "ONLY_COMMENTS" for i in issues)


def test_lint_snippet_long_line():
    s = Snippet(title="x", body="x = " + "1" * 500, language="python")
    issues = lint.lint_snippet(s)
    assert any(i.code == "LONG_LINE" for i in issues)


def test_lint_snippet_many_tags():
    s = Snippet(title="x", body="x = 1", language="python", tags=[f"t{i}" for i in range(15)])
    issues = lint.lint_snippet(s)
    assert any(i.code == "MANY_TAGS" for i in issues)


def test_lint_book_returns_issues_per_snippet(populated_book):
    issues = lint.lint_book(populated_book.data)
    assert isinstance(issues, list)


def test_lint_book_dup_slug_error():
    book = {
        "snippets": [
            {"id": "a", "title": "Foo", "body": "x", "language": "python", "slug": "same"},
            {"id": "b", "title": "Bar", "body": "y", "language": "python", "slug": "same"},
        ]
    }
    issues = lint.lint_book(book)
    assert any(i.code == "DUP_SLUG" and i.severity == "error" for i in issues)


def test_has_errors_true():
    issues = [lint.Issue("a", "DUP_SLUG", "x", severity="error")]
    assert lint.has_errors(issues) is True


def test_has_errors_false():
    issues = [lint.Issue("a", "X", "y", severity="warn")]
    assert lint.has_errors(issues) is False


def test_count_by_code():
    issues = [
        lint.Issue("a", "X", "x"),
        lint.Issue("b", "X", "y"),
        lint.Issue("c", "Y", "z"),
    ]
    counts = lint.count_by_code(issues)
    assert counts == {"X": 2, "Y": 1}


def test_filter_by_severity():
    issues = [
        lint.Issue("a", "X", "x", severity="info"),
        lint.Issue("b", "Y", "y", severity="error"),
    ]
    out = lint.filter_by_severity(issues, "info")
    assert len(out) == 1


def test_render_issues():
    issues = [lint.Issue("a", "X", "y", severity="warn")]
    out = lint.render_issues(issues)
    assert "warn" in out
    assert "X" in out


def test_is_clean_no_issues():
    assert lint.is_clean([]) is True


def test_is_clean_has_issues():
    assert lint.is_clean([lint.Issue("a", "X", "y")]) is False


def test_severity_rank_ordering():
    assert lint.severity_rank("info") < lint.severity_rank("warn") < lint.severity_rank("error")


def test_worst_returns_highest():
    issues = [
        lint.Issue("a", "X", "y", severity="info"),
        lint.Issue("b", "Y", "z", severity="error"),
    ]
    assert lint.worst(issues) == "error"


def test_worst_default_info():
    assert lint.worst([]) == "info"


def test_lint_book_handles_bad_snippet():
    # an entry that's not a dict at all is a hard error.
    book = {"snippets": ["nope, not a dict"]}
    issues = lint.lint_book(book)
    assert any(i.severity == "error" for i in issues)


def test_lint_snippet_long_body_normal_line():
    s = Snippet(title="t", body="x = 1\n" * 100, language="python")
    issues = lint.lint_snippet(s)
    assert all(i.code != "LONG_LINE" for i in issues)


def test_issue_format_contains_severity():
    issue = lint.Issue("a", "CODE", "msg", severity="warn")
    assert "warn" in issue.format()
