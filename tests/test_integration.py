"""End-to-end integration tests.

These exercise multiple modules at once to catch regressions in the
glue between them. They live in their own file because the rest of
the suite is module-by-module and these would feel out of place
elsewhere.
"""

from __future__ import annotations

import json


from snippetbox import (
    backup,
    io_csv,
    io_gist,
    io_html,
    io_json,
    io_markdown,
    io_textmate,
    io_vscode,
    io_zip,
    recipes,
    storage,
)
from snippetbox.collection import Collection
from snippetbox.snippet import Snippet


def test_full_workflow_end_to_end(tmp_path):
    """Initialise -> add a few -> export every format -> import them back."""
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)

    a = Snippet(title="tail file", body="import asyncio\nawait asyncio.sleep(0.1)", language="python", tags=["io"])
    b = Snippet(title="grep todo", body="grep -rni TODO .", language="shell", tags=["search"])
    c = Snippet(title="active users", body="SELECT * FROM users WHERE active = TRUE", language="sql")
    book.add(a)
    book.add(b)
    book.add(c)
    book.save()

    # exercise every codec round-trip
    json_text = io_json.export_snippets(list(book))
    assert len(io_json.import_snippets(json_text)) == 3

    md_text = io_markdown.export_snippets(list(book))
    assert len(io_markdown.import_snippets(md_text)) == 3

    csv_text = io_csv.export_snippets(list(book))
    assert len(io_csv.import_snippets(csv_text)) == 3

    vs_text = io_vscode.export_snippets(list(book))
    assert len(io_vscode.import_snippets(vs_text)) == 3

    tm_text = io_textmate.export_snippets(list(book))
    assert len(io_textmate.import_snippets(tm_text)) == 3

    gist_text = io_gist.export_snippets(list(book))
    assert len(io_gist.import_snippets(gist_text)) == 3

    zip_bytes = io_zip.export_to_bytes(list(book))
    assert len(io_zip.import_from_bytes(zip_bytes)) == 3

    html_text = io_html.render(list(book))
    assert "<html>" in html_text


def test_book_round_trip_through_disk(tmp_path):
    """Save + load preserves snippets exactly."""
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)
    s = Snippet(title="x", body="b", language="python", tags=["t"])
    book.add(s)
    book.save()

    fresh = storage.Book.load(book_path)
    fetched = fresh.get(s.id)
    assert fetched is not None
    assert fetched.title == s.title
    assert fetched.body == s.body
    assert fetched.tags == s.tags


def test_backup_then_modify_then_restore(tmp_path):
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)
    s = Snippet(title="original", body="x", language="python")
    book.add(s)
    book.save()

    bk = backup.make_backup(book_path)

    # mutate
    book.delete(s.id)
    book.save()
    assert len(storage.Book.load(book_path)) == 0

    backup.restore_backup(book_path, bk)
    restored = storage.Book.load(book_path)
    assert len(restored) == 1


def test_recipes_after_import(tmp_path):
    """auto_tag_all + dedup_all + summarise after a fresh import."""
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)
    snippets = [
        Snippet(title="async stuff", body="import asyncio\nawait asyncio.sleep(0.1)", language="python"),
        Snippet(title="async dup", body="import asyncio\nawait asyncio.sleep(0.1)", language="python"),
        Snippet(title="csv reader", body="import csv\nfor row in csv.reader(f): print(row)", language="python"),
    ]
    for s in snippets:
        try:
            book.add(s)
        except Exception:  # noqa: BLE001
            s.slug = s.slug + "-x"
            book.add(s)
    book.save()

    recipes.auto_tag_all(book)
    book.save()

    removed = recipes.dedup_all(book)
    assert removed >= 1

    summary = recipes.summarise(book)
    assert "total" in summary
    assert summary["total"] < len(snippets)


def test_collection_membership_survives_save_load(tmp_path):
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)
    a = Snippet(title="a", body="b", language="python")
    book.add(a)
    book.upsert_collection(Collection(name="favs", snippet_ids=[a.id]))
    book.save()

    fresh = storage.Book.load(book_path)
    coll = fresh.get_collection("favs")
    assert coll is not None
    assert a.id in coll.snippet_ids


def test_export_import_zip_keeps_metadata(tmp_path):
    book_path = tmp_path / "book.json"
    book = storage.Book.init(book_path)
    s = Snippet(title="hello", body="print('hi')", language="python", tags=["greeting"])
    book.add(s)
    target = tmp_path / "out.zip"
    io_zip.export_to_file(list(book), target)

    fresh = io_zip.import_from_file(target)
    assert fresh[0].language == "python"
    assert "greeting" in fresh[0].tags


def test_search_through_books(tmp_path):
    book = storage.Book.init(tmp_path / "book.json")
    # body uses spaces so the fuzzy tokenisation can isolate words
    book.add(Snippet(title="async file tail", body="import asyncio and sleep", language="python", tags=["io"]))
    book.add(Snippet(title="recursive grep", body="grep TODO source", language="shell", tags=["search"]))
    book.save()

    from snippetbox.search import search

    hits = search(list(book), "asyncio", mode="substring")
    assert len(hits) == 1

    hits = search(list(book), "tail file", mode="token")
    assert len(hits) == 1

    hits = search(list(book), "asyncii", mode="fuzzy")
    assert len(hits) == 1


def test_migration_then_use(tmp_path):
    """A v0 book in a file should load + behave like a normal book."""
    book_path = tmp_path / "old.json"
    book_path.write_text(json.dumps([{"title": "old", "body": "x"}]), encoding="utf-8")
    book = storage.Book.load(book_path)
    assert len(book) == 1
    assert book.data["schema_version"] == 3


def test_audit_log_records_hooks(tmp_path):
    from snippetbox.audit_log import AuditLog

    log = AuditLog(tmp_path / "audit.log")
    log.record("add", target="abc")
    log.record("delete", target="abc")
    entries = log.read()
    assert [e.action for e in entries] == ["add", "delete"]


def test_plugin_extension(tmp_path):
    from snippetbox import plugins
    from snippetbox.snippet import Snippet

    plugins.clear()
    plugins.register("post-add", lambda s: s.title.upper())
    s = Snippet(title="hello", body="x")
    out = plugins.call("post-add", s)
    assert out == "HELLO"
    plugins.clear()


def test_lint_after_export_import_round_trip(tmp_path):
    from snippetbox import lint

    book = storage.Book.init(tmp_path / "book.json")
    book.add(Snippet(title="ok", body="x = 1", language="python", tags=["t"]))
    book.save()
    json_text = io_json.export_snippets(list(book))
    out_path = tmp_path / "out.json"
    out_path.write_text('{"snippets":' + json.dumps(json.loads(json_text)["snippets"]) + "}", encoding="utf-8")
    fresh_book = storage.Book.init(tmp_path / "fresh.json")
    for s in io_json.import_from_file(out_path):
        try:
            fresh_book.add(s)
        except Exception:  # noqa: BLE001
            pass
    issues = lint.lint_book(fresh_book.data)
    assert lint.has_errors(issues) is False


def test_dedup_after_search_and_mark(tmp_path):
    book = storage.Book.init(tmp_path / "book.json")
    a = Snippet(title="a", body="duplicate body", language="python", tags=["t"])
    b = Snippet(title="b", body="duplicate body", language="python", tags=["t"])
    book.add(a)
    book.add(b)
    book.save()

    n = recipes.search_and_mark(book, "duplicate", favourite=True)
    assert n >= 1
    book.save()

    removed = recipes.dedup_all(book)
    assert removed >= 1
