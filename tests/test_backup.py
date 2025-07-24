import time

import pytest

from snippetbox import backup
from snippetbox.errors import BookNotFoundError
from snippetbox.storage import Book


def _make_book(path):
    Book.init(path)
    return path


def test_make_backup_creates_file(tmp_book_path):
    _make_book(tmp_book_path)
    target = backup.make_backup(tmp_book_path)
    assert target.exists()


def test_make_backup_supports_label(tmp_book_path):
    _make_book(tmp_book_path)
    target = backup.make_backup(tmp_book_path, label="weekly")
    assert target.name.endswith("-weekly")


def test_make_backup_missing_book_raises(tmp_path):
    with pytest.raises(BookNotFoundError):
        backup.make_backup(tmp_path / "missing.json")


def test_list_backups_empty(tmp_book_path):
    _make_book(tmp_book_path)
    assert backup.list_backups(tmp_book_path) == []


def test_list_backups_after_backup(tmp_book_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path)
    assert len(backup.list_backups(tmp_book_path)) == 1


def test_latest_backup_returns_most_recent(tmp_book_path):
    _make_book(tmp_book_path)
    a = backup.make_backup(tmp_book_path)
    time.sleep(1.1)
    b = backup.make_backup(tmp_book_path)
    latest = backup.latest_backup(tmp_book_path)
    assert latest in (a, b)


def test_latest_backup_none_when_empty(tmp_book_path):
    _make_book(tmp_book_path)
    assert backup.latest_backup(tmp_book_path) is None


def test_restore_backup_round_trip(tmp_book_path, tmp_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path)
    target = backup.latest_backup(tmp_book_path)
    out = tmp_path / "restored.json"
    backup.restore_backup(out, target)
    assert out.exists()


def test_restore_missing_backup_raises(tmp_book_path):
    _make_book(tmp_book_path)
    with pytest.raises(BookNotFoundError):
        backup.restore_backup(tmp_book_path, tmp_book_path.parent / "missing.json")


def test_prune_keeps_n(tmp_book_path):
    _make_book(tmp_book_path)
    for _ in range(3):
        backup.make_backup(tmp_book_path)
        time.sleep(1.1)
    removed = backup.prune_backups(tmp_book_path, keep=1)
    assert removed == 2
    assert len(backup.list_backups(tmp_book_path)) == 1


def test_prune_no_op_under_threshold(tmp_book_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path)
    assert backup.prune_backups(tmp_book_path, keep=10) == 0


def test_total_backup_size(tmp_book_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path)
    assert backup.total_backup_size(tmp_book_path) > 0


def test_total_backup_size_no_backups(tmp_book_path):
    _make_book(tmp_book_path)
    assert backup.total_backup_size(tmp_book_path) == 0


def test_parse_backup_timestamp_valid(tmp_book_path):
    _make_book(tmp_book_path)
    target = backup.make_backup(tmp_book_path)
    parsed = backup.parse_backup_timestamp(target)
    assert parsed is not None


def test_parse_backup_timestamp_unrecognised(tmp_path):
    p = tmp_path / "weird.json"
    p.write_text("{}", encoding="utf-8")
    assert backup.parse_backup_timestamp(p) is None


def test_age_seconds_for_unparseable(tmp_path):
    p = tmp_path / "weird.json"
    p.write_text("{}", encoding="utf-8")
    assert backup.age_seconds(p) == float("inf")


def test_age_seconds_real_backup(tmp_book_path):
    _make_book(tmp_book_path)
    target = backup.make_backup(tmp_book_path)
    assert backup.age_seconds(target) < 60


def test_find_by_label_present(tmp_book_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path, label="x")
    assert backup.find_by_label(tmp_book_path, "x") is not None


def test_find_by_label_missing(tmp_book_path):
    _make_book(tmp_book_path)
    assert backup.find_by_label(tmp_book_path, "missing") is None


def test_find_by_label_blank(tmp_book_path):
    _make_book(tmp_book_path)
    assert backup.find_by_label(tmp_book_path, "") is None


def test_backup_dir_resolves_correctly(tmp_book_path):
    bd = backup.backup_dir(tmp_book_path)
    assert bd.name == "backups"


def test_make_backup_creates_directory(tmp_book_path):
    _make_book(tmp_book_path)
    backup.make_backup(tmp_book_path)
    assert backup.backup_dir(tmp_book_path).exists()
