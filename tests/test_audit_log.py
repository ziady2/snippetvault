import pytest

from snippetbox import audit_log
from snippetbox.errors import AuditError


def test_record_writes_line(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("add", target="x")
    assert log.path.exists()
    assert log.path.read_text(encoding="utf-8").strip()


def test_record_skipped_when_disabled(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log", enabled=False)
    assert log.record("add") is None
    assert not log.path.exists()


def test_record_blank_action_raises(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    with pytest.raises(AuditError):
        log.record("")


def test_read_returns_entries(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("add", target="x")
    log.record("edit", target="y")
    entries = log.read()
    assert len(entries) == 2
    assert entries[0].action == "add"


def test_read_missing_file(tmp_path):
    log = audit_log.AuditLog(tmp_path / "missing.log")
    assert log.read() == []


def test_read_skips_invalid_lines(tmp_path):
    p = tmp_path / "audit.log"
    p.write_text('{"action":"ok","at":1.0}\nnot-json\n', encoding="utf-8")
    log = audit_log.AuditLog(p)
    out = log.read()
    assert len(out) == 1


def test_actions_returns_list(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("a")
    log.record("b")
    assert log.actions() == ["a", "b"]


def test_truncate_removes_file(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("a")
    log.truncate()
    assert not log.path.exists()


def test_truncate_no_op_when_missing(tmp_path):
    log = audit_log.AuditLog(tmp_path / "missing.log")
    log.truncate()  # does not raise


def test_size_bytes(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    assert log.size_bytes() == 0
    log.record("a")
    assert log.size_bytes() > 0


def test_filter_by_action(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("a")
    log.record("b")
    out = log.filter_by_action("a")
    assert len(out) == 1


def test_filter_since(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("a")
    out = log.filter_since(0)
    assert len(out) == 1


def test_latest(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    for i in range(5):
        log.record(f"a-{i}")
    out = log.latest(2)
    assert len(out) == 2
    assert out[-1].action == "a-4"


def test_count(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    log.record("a")
    log.record("b")
    assert log.count() == 2


def test_default_audit_path(tmp_path):
    out = audit_log.default_audit_path(tmp_path / "book.json")
    assert out.parent == tmp_path
    assert out.name == "audit.log"


def test_is_enabled_default():
    assert audit_log.is_enabled({}) is False


def test_is_enabled_truthy():
    assert audit_log.is_enabled({"metadata": {"audit_enabled": True}}) is True


def test_set_enabled():
    book = {}
    audit_log.set_enabled(book, True)
    assert book["metadata"]["audit_enabled"] is True


def test_replay_summarises():
    entries = [
        audit_log.AuditEntry(action="a"),
        audit_log.AuditEntry(action="a"),
        audit_log.AuditEntry(action="b"),
    ]
    out = audit_log.replay(entries)
    assert out["counts"]["a"] == 2


def test_audit_entry_to_line_includes_target():
    e = audit_log.AuditEntry(action="add", target="x")
    line = e.to_line()
    assert "target" in line


def test_audit_entry_from_line_round_trip():
    e = audit_log.AuditEntry(action="add", target="x", user="me", extra={"k": 1})
    e2 = audit_log.AuditEntry.from_line(e.to_line())
    assert e2.action == e.action
    assert e2.target == e.target
    assert e2.extra == e.extra


def test_audit_entry_from_line_blank_returns_none():
    assert audit_log.AuditEntry.from_line("") is None


def test_audit_entry_from_line_bad_json_returns_none():
    assert audit_log.AuditEntry.from_line("nope") is None


def test_record_with_extra(tmp_path):
    log = audit_log.AuditLog(tmp_path / "audit.log")
    e = log.record("add", id="abc", count=5)
    assert e.extra["id"] == "abc"
