import json

import pytest

from snippetbox import storage
from snippetbox.errors import BookNotFoundError, DuplicateSlugError, InvalidSnippetError
from snippetbox.snippet import Snippet


def test_default_book_path_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SNIPPETBOX_BOOK", str(tmp_path / "x.json"))
    assert storage.default_book_path() == tmp_path / "x.json"


def test_default_book_path_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("SNIPPETBOX_BOOK", raising=False)
    p = storage.default_book_path()
    assert p.name == "book.json"


def test_empty_book_has_metadata():
    book = storage.empty_book()
    assert "metadata" in book
    assert book["snippets"] == []


def test_init_creates_file(tmp_book_path):
    storage.Book.init(tmp_book_path)
    assert tmp_book_path.exists()


def test_init_returns_existing_when_present(tmp_book_path):
    storage.Book.init(tmp_book_path)
    book = storage.Book.init(tmp_book_path)
    assert tmp_book_path.exists()
    assert isinstance(book, storage.Book)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(BookNotFoundError):
        storage.Book.load(tmp_path / "missing.json")


def test_load_invalid_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(InvalidSnippetError):
        storage.Book.load(p)


def test_add_and_get_snippet(empty_book, python_snippet):
    empty_book.add(python_snippet)
    fetched = empty_book.get(python_snippet.id)
    assert fetched is not None
    assert fetched.id == python_snippet.id


def test_get_missing_returns_none(empty_book):
    assert empty_book.get("nope") is None


def test_get_by_slug(populated_book, python_snippet):
    fetched = populated_book.get_by_slug(python_snippet.slug)
    assert fetched is not None
    assert fetched.id == python_snippet.id


def test_add_with_duplicate_slug_raises(empty_book):
    a = Snippet(title="hello", body="x", language="python")
    b = Snippet(title="hello", body="y", language="python")
    empty_book.add(a)
    with pytest.raises(DuplicateSlugError):
        empty_book.add(b)


def test_replace_overwrites(empty_book, python_snippet):
    empty_book.add(python_snippet)
    python_snippet.body = "new body"
    assert empty_book.replace(python_snippet) is True
    assert empty_book.get(python_snippet.id).body == "new body"


def test_replace_missing_returns_false(empty_book, python_snippet):
    assert empty_book.replace(python_snippet) is False


def test_delete_existing(populated_book, python_snippet):
    assert populated_book.delete(python_snippet.id) is True
    assert populated_book.get(python_snippet.id) is None


def test_delete_missing(empty_book):
    assert empty_book.delete("nope") is False


def test_delete_drops_from_collections(empty_book, python_snippet):
    from snippetbox.collection import Collection

    empty_book.add(python_snippet)
    coll = Collection(name="favs", snippet_ids=[python_snippet.id])
    empty_book.upsert_collection(coll)
    empty_book.delete(python_snippet.id)
    fresh = empty_book.get_collection("favs")
    assert python_snippet.id not in fresh.snippet_ids


def test_iter_yields_snippets(populated_book):
    items = list(populated_book)
    assert len(items) == 3


def test_len_returns_count(populated_book):
    assert len(populated_book) == 3


def test_collections_round_trip(empty_book):
    from snippetbox.collection import Collection

    empty_book.upsert_collection(Collection(name="x"))
    assert any(c.name == "x" for c in empty_book.collections())


def test_upsert_overwrites_collection(empty_book):
    from snippetbox.collection import Collection

    empty_book.upsert_collection(Collection(name="x"))
    empty_book.upsert_collection(Collection(name="X", description="updated"))
    assert empty_book.get_collection("x").description == "updated"


def test_remove_collection(empty_book):
    from snippetbox.collection import Collection

    empty_book.upsert_collection(Collection(name="x"))
    assert empty_book.remove_collection("x") is True
    assert empty_book.remove_collection("x") is False


def test_metadata_get_set(empty_book):
    empty_book.set_metadata("foo", "bar")
    assert empty_book.metadata()["foo"] == "bar"


def test_stats_includes_counts(populated_book):
    stats = populated_book.stats()
    assert stats["snippet_count"] == 3
    assert "python" in stats["languages"]


def test_save_writes_atomically(tmp_book_path, python_snippet):
    book = storage.Book.init(tmp_book_path)
    book.add(python_snippet)
    book.save()
    raw = json.loads(tmp_book_path.read_text(encoding="utf-8"))
    assert raw["snippets"]


def test_atomic_write_recovers_from_failure(tmp_path):
    target = tmp_path / "out.json"
    storage.atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}


def test_copy_book(tmp_book_path, tmp_path):
    storage.Book.init(tmp_book_path)
    dest = tmp_path / "copy.json"
    storage.copy_book(tmp_book_path, dest)
    assert dest.exists()


def test_copy_missing_raises(tmp_path):
    with pytest.raises(BookNotFoundError):
        storage.copy_book(tmp_path / "missing.json", tmp_path / "out.json")


def test_book_size_existing(tmp_book_path):
    storage.Book.init(tmp_book_path)
    assert storage.book_size(tmp_book_path) > 0


def test_book_size_missing(tmp_path):
    assert storage.book_size(tmp_path / "missing.json") == 0


def test_book_exists_truthy(tmp_book_path):
    storage.Book.init(tmp_book_path)
    assert storage.book_exists(tmp_book_path) is True


def test_book_exists_missing(tmp_path):
    assert storage.book_exists(tmp_path / "missing.json") is False


def test_merge_into_appends_new(empty_book, python_snippet, sql_snippet):
    n = storage.merge_into(empty_book, [python_snippet, sql_snippet])
    assert n == 2
    assert len(empty_book) == 2


def test_merge_into_skips_known(empty_book, python_snippet):
    empty_book.add(python_snippet)
    n = storage.merge_into(empty_book, [python_snippet])
    assert n == 0


def test_merge_into_handles_slug_collision(empty_book):
    a = Snippet(title="dup", body="aaa", language="python")
    b = Snippet(title="dup", body="bbb", language="python")
    empty_book.add(a)
    n = storage.merge_into(empty_book, [b])
    assert n == 1
