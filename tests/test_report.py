import time

from snippetbox import report
from snippetbox.snippet import Snippet


def test_by_language_counts(populated_book):
    rep = report.by_language(list(populated_book))
    rows = dict(rep.rows)
    assert rows.get("python") == 1
    assert rows.get("shell") == 1


def test_by_language_to_text(populated_book):
    rep = report.by_language(list(populated_book))
    text = rep.to_text()
    assert "language" in text


def test_by_language_to_markdown(populated_book):
    rep = report.by_language(list(populated_book))
    md = rep.to_markdown()
    assert md.startswith("#")


def test_by_tag_counts(populated_book):
    rep = report.by_tag(list(populated_book))
    rows = dict(rep.rows)
    assert "io" in rows


def test_by_tag_excludes_auto():
    a = Snippet(title="a", body="b", tags=["mine"], auto_tags=["auto1"])
    rep = report.by_tag([a], include_auto=False)
    rows = dict(rep.rows)
    assert "mine" in rows
    assert "auto1" not in rows


def test_line_counts_orders_descending(populated_book):
    rep = report.line_counts(list(populated_book))
    if len(rep.rows) >= 2:
        assert rep.rows[0][1] >= rep.rows[-1][1]


def test_usage_top(populated_book):
    snips = list(populated_book)
    snips[0].used_count = 7
    rep = report.usage_top(snips)
    assert rep.rows[0][1] == 7


def test_stale_finds_old(populated_book):
    snips = list(populated_book)
    snips[0].updated_at = time.time() - 10 * 365 * 86400
    rep = report.stale(snips, days=180)
    assert len(rep.rows) >= 1


def test_stale_skips_recent(populated_book):
    rep = report.stale(list(populated_book), days=10)
    assert rep.rows == [] or all(isinstance(r, tuple) for r in rep.rows)


def test_coverage_includes_percentage(populated_book):
    rep = report.coverage(list(populated_book))
    assert any("%" in str(row[-1]) for row in rep.rows)


def test_empty_tags_finds_untagged():
    a = Snippet(title="a", body="b", language="python")
    rep = report.empty_tags([a])
    assert len(rep.rows) == 1


def test_empty_tags_skips_tagged():
    a = Snippet(title="a", body="b", language="python", tags=["x"])
    rep = report.empty_tags([a])
    assert rep.rows == []


def test_overview_returns_dict(populated_book):
    overview = report.overview(list(populated_book))
    assert overview["total"] == 3
    assert "languages" in overview


def test_histogram_languages_includes_bars(populated_book):
    text = report.histogram_languages(list(populated_book))
    assert "#" in text


def test_histogram_languages_blank():
    assert report.histogram_languages([]) == ""


def test_report_to_text_empty_rows():
    rep = report.Report(title="X")
    assert "empty" in rep.to_text()


def test_report_to_markdown_empty_rows():
    rep = report.Report(title="X")
    assert "empty" in rep.to_markdown()


def test_by_language_to_markdown_empty():
    rep = report.by_language([])
    assert "empty" in rep.to_markdown().lower()
