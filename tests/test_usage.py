import time

from snippetbox import usage
from snippetbox.snippet import Snippet


def test_record_use_creates_event():
    book = {"metadata": {}}
    event = usage.record_use(book, "snippet-1")
    assert event.snippet_id == "snippet-1"
    assert book["metadata"]["usage_log"]


def test_record_use_creates_metadata():
    book = {}
    usage.record_use(book, "x")
    assert "metadata" in book


def test_record_use_caps_log_size():
    book = {"metadata": {"usage_log": []}}
    for i in range(usage.MAX_EVENTS + 50):
        usage.record_use(book, f"id-{i}")
    assert len(book["metadata"]["usage_log"]) == usage.MAX_EVENTS


def test_record_use_with_note():
    book = {"metadata": {}}
    event = usage.record_use(book, "x", note="hello")
    assert event.note == "hello"


def test_usage_log_returns_objects():
    book = {"metadata": {"usage_log": [{"id": "x", "at": 1.0}]}}
    log = usage.usage_log(book)
    assert log[0].snippet_id == "x"
    assert log[0].at == 1.0


def test_usage_log_blank_book():
    assert usage.usage_log({}) == []


def test_usage_counts():
    events = [usage.UsageEvent("a"), usage.UsageEvent("a"), usage.UsageEvent("b")]
    counts = usage.usage_counts(events)
    assert counts["a"] == 2
    assert counts["b"] == 1


def test_top_used_returns_pairs():
    events = [usage.UsageEvent("a"), usage.UsageEvent("a"), usage.UsageEvent("b")]
    top = usage.top_used(events, n=2)
    assert top[0] == ("a", 2)


def test_usage_for_returns_count():
    events = [usage.UsageEvent("a"), usage.UsageEvent("a")]
    assert usage.usage_for(events, "a") == 2


def test_usage_for_missing():
    events = [usage.UsageEvent("a")]
    assert usage.usage_for(events, "z") == 0


def test_latest_use_present():
    events = [usage.UsageEvent("a", at=10.0), usage.UsageEvent("a", at=20.0)]
    assert usage.latest_use(events, "a") == 20.0


def test_latest_use_missing():
    assert usage.latest_use([], "a") is None


def test_first_use_present():
    events = [usage.UsageEvent("a", at=10.0), usage.UsageEvent("a", at=20.0)]
    assert usage.first_use(events, "a") == 10.0


def test_first_use_missing():
    assert usage.first_use([], "a") is None


def test_trim_log_no_op_under_threshold():
    book = {"metadata": {"usage_log": [{"id": "x", "at": 1.0}]}}
    assert usage.trim_log(book, keep=10) == 0


def test_trim_log_trims():
    log = [{"id": "x", "at": float(i)} for i in range(20)]
    book = {"metadata": {"usage_log": log}}
    removed = usage.trim_log(book, keep=5)
    assert removed == 15
    assert len(book["metadata"]["usage_log"]) == 5


def test_reset_clears_log():
    book = {"metadata": {"usage_log": [{"id": "x", "at": 1.0}]}}
    usage.reset(book)
    assert book["metadata"]["usage_log"] == []


def test_reset_no_op_without_metadata():
    book = {}
    usage.reset(book)
    assert book == {}


def test_stale_snippets_finds_old_ones():
    snip = Snippet(title="x", body="b", language="python")
    snip.updated_at = time.time() - 365 * 86400
    out = usage.stale_snippets([snip], [], days=180)
    assert len(out) == 1


def test_stale_snippets_skips_recent():
    snip = Snippet(title="x", body="b", language="python")
    out = usage.stale_snippets([snip], [], days=180)
    assert out == []


def test_stale_snippets_uses_log_when_more_recent():
    snip = Snippet(title="x", body="b", language="python")
    snip.updated_at = time.time() - 365 * 86400
    events = [usage.UsageEvent(snip.id, at=time.time())]
    out = usage.stale_snippets([snip], events, days=180)
    assert out == []


def test_export_log_csv_round_trip():
    events = [usage.UsageEvent("a", at=1.5, note="hi")]
    out = usage.export_log_csv(events)
    back = usage.import_log_csv(out)
    assert back[0].snippet_id == "a"


def test_import_log_csv_blank():
    assert usage.import_log_csv("") == []


def test_import_log_csv_no_header_returns_empty():
    text = "weird\nstuff"
    out = usage.import_log_csv(text)
    assert out == []


def test_import_log_csv_skips_bad_rows():
    text = "id,at,note\nx,nope,n\ny,2.0,m"
    out = usage.import_log_csv(text)
    assert len(out) == 1
    assert out[0].snippet_id == "y"


def test_event_to_dict_includes_optional():
    e = usage.UsageEvent("a", note="hi")
    d = e.to_dict()
    assert d["id"] == "a"
    assert d["note"] == "hi"


def test_event_from_dict_handles_missing():
    e = usage.UsageEvent.from_dict({})
    assert e.snippet_id == ""


def test_event_to_dict_no_note():
    e = usage.UsageEvent("a")
    d = e.to_dict()
    assert "note" not in d
