"""CLI smoke tests.

We invoke the dispatcher with constructed argparse Namespaces because
that's faster than ``subprocess.run`` and gives proper coverage.
"""

from __future__ import annotations

import argparse
import io
import sys

import pytest

from snippetbox import cli, storage


def _ns(**kwargs) -> argparse.Namespace:
    base = {
        "book": None,
        "version": False,
        "command": None,
        "title": "",
        "lang": "plain",
        "tags": "",
        "from_file": "",
        "auto_tag": False,
        "limit": 50,
        "tag": "",
        "archived": False,
        "ident": "",
        "format": "text",
        "query": "",
        "mode": "token",
        "no_rank": False,
        "source": "",
        "target": "",
        "what": "overview",
        "label": "",
        "force": False,
        "max_tags": 6,
        "host": "127.0.0.1",
        "port": 8765,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_main_no_args_prints_help(capsys):
    rc = cli.main([])
    assert rc == 1


def test_main_version(capsys):
    rc = cli.main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out


def test_init_creates_book(tmp_path, capsys):
    rc = cli.main(["--book", str(tmp_path / "book.json"), "init"])
    assert rc == 0
    assert (tmp_path / "book.json").exists()


def test_init_reuses_existing(tmp_path):
    storage.Book.init(tmp_path / "book.json")
    rc = cli.main(["--book", str(tmp_path / "book.json"), "init"])
    assert rc == 0


def test_add_command_round_trip(tmp_path, monkeypatch, capsys):
    book_path = tmp_path / "book.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO("print(1)\n"))
    rc = cli.main(["--book", str(book_path), "add", "--title", "hi", "--lang", "python", "--tags", "demo"])
    assert rc == 0
    book = storage.Book.load(book_path)
    assert len(book) == 1


def test_add_from_file(tmp_path, capsys):
    book_path = tmp_path / "book.json"
    body = tmp_path / "body.py"
    body.write_text("x = 1\n", encoding="utf-8")
    rc = cli.main(
        [
            "--book",
            str(book_path),
            "add",
            "--title",
            "hi",
            "--lang",
            "python",
            "--from-file",
            str(body),
        ]
    )
    assert rc == 0


def test_add_with_auto_tag(tmp_path, monkeypatch):
    book_path = tmp_path / "book.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO("import asyncio\nawait asyncio.sleep(0)\n"))
    rc = cli.main(
        [
            "--book",
            str(book_path),
            "add",
            "--title",
            "hi",
            "--lang",
            "python",
            "--auto-tag",
        ]
    )
    assert rc == 0
    book = storage.Book.load(book_path)
    s = list(book)[0]
    assert s.auto_tags


def test_list_command(tmp_path, populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "list"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert captured


def test_list_filters_by_lang(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "list", "--lang", "python"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "python" in out


def test_show_text(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "show", python_snippet.id])
    assert rc == 0


def test_show_missing(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "show", "missing-id"])
    assert rc == 1


def test_show_markdown(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "show", python_snippet.id, "--format", "markdown"])
    assert rc == 0


def test_show_json(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "show", python_snippet.id, "--format", "json"])
    assert rc == 0


def test_show_html(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "show", python_snippet.id, "--format", "html"])
    assert rc == 0


def test_search_returns_results(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "search", "asyncio"])
    assert rc == 0


def test_search_no_results(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "search", "zzzzzzzzzzz"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no matches" in out.lower()


def test_delete_command(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "delete", python_snippet.id])
    assert rc == 0


def test_delete_missing(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "delete", "missing"])
    assert rc == 1


def test_import_export_round_trip(tmp_path, populated_book):
    target = tmp_path / "out.json"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "json"])
    assert rc == 0
    rc = cli.main(["--book", str(tmp_path / "new.json"), "import", str(target), "--format", "json"])
    assert rc == 0


def test_export_csv(tmp_path, populated_book):
    target = tmp_path / "out.csv"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "csv"])
    assert rc == 0


def test_export_html(tmp_path, populated_book):
    target = tmp_path / "out.html"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "html"])
    assert rc == 0


def test_export_zip(tmp_path, populated_book):
    target = tmp_path / "out.zip"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "zip"])
    assert rc == 0


def test_export_markdown(tmp_path, populated_book):
    target = tmp_path / "out.md"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "markdown"])
    assert rc == 0


def test_export_vscode(tmp_path, populated_book):
    target = tmp_path / "out.json"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "vscode"])
    assert rc == 0


def test_export_textmate(tmp_path, populated_book):
    target = tmp_path / "out.xml"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "textmate"])
    assert rc == 0


def test_export_gist(tmp_path, populated_book):
    target = tmp_path / "out.json"
    rc = cli.main(["--book", str(populated_book.path), "export", str(target), "--format", "gist"])
    assert rc == 0


def test_report_overview(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "report", "--what", "overview"])
    assert rc == 0


def test_report_language(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "report", "--what", "language"])
    assert rc == 0


def test_report_unknown(populated_book, capsys):
    args = _ns(
        command="report",
        what="weird",
        book=str(populated_book.path),
        limit=10,
    )
    assert cli._cmd_report(args) == 1


def test_dedup_command(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "dedup"])
    assert rc == 0


def test_lint_command(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "lint"])
    assert rc == 0


def test_backup_and_restore(tmp_path, populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "backup"])
    assert rc == 0
    captured = capsys.readouterr().out.strip()
    target = captured.replace("backed up to ", "")
    rc = cli.main(["--book", str(populated_book.path), "restore", target])
    assert rc == 0


def test_restore_missing(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "restore", "no-such-label"])
    assert rc == 1


def test_auto_tag_command(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "auto-tag"])
    assert rc == 0


def test_info_command(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "info"])
    assert rc == 0


def test_main_handles_snippetbox_error(tmp_path, capsys):
    target = tmp_path / "out.json"
    target.write_text("not json", encoding="utf-8")
    rc = cli.main(["--book", str(target), "list"])
    assert rc == 2


def test_search_with_tag_filter(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "search", "", "--tag", "io"])
    assert rc == 0


def test_search_with_lang_filter(populated_book, capsys):
    rc = cli.main(["--book", str(populated_book.path), "search", "", "--lang", "python"])
    assert rc == 0


def test_show_by_slug(populated_book, capsys, python_snippet):
    rc = cli.main(["--book", str(populated_book.path), "show", python_snippet.slug])
    assert rc == 0


def test_export_unknown_format(populated_book, capsys, tmp_path):
    args = _ns(
        command="export",
        target=str(tmp_path / "x"),
        book=str(populated_book.path),
        format="weird",
    )
    with pytest.raises(Exception):
        cli._cmd_export(args)


def test_import_unknown_format(populated_book, tmp_path):
    args = _ns(
        command="import",
        source=str(tmp_path / "x"),
        book=str(populated_book.path),
        format="weird",
    )
    with pytest.raises(Exception):
        cli._cmd_import(args)
