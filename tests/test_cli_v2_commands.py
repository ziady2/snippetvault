from __future__ import annotations

import json

from snippetbox import cli
from snippetbox.snippet import Snippet
from snippetbox.storage import Book


def seed(path):
    book = Book.init(path)
    book.add(
        Snippet(
            id="python-one",
            title="HTTP client",
            body="print('hello')\n",
            language="python",
            tags=["web"],
            created_at=100,
            updated_at=100,
        )
    )
    book.add(
        Snippet(
            id="sql-one",
            title="Recent users",
            body="SELECT * FROM users;\n",
            language="sql",
            tags=["data"],
            created_at=100,
            updated_at=100,
        )
    )
    book.save()
    return book


def test_query_command_filters_structured_fields(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(["--book", str(path), "query", "lang:python tag:web"])
    assert rc == 0
    output = capsys.readouterr().out
    assert "python-one" in output
    assert "sql-one" not in output


def test_query_command_reports_invalid_field(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(["--book", str(path), "query", "planet:mars"])
    assert rc == 2
    assert "unknown query field" in capsys.readouterr().err


def test_doctor_command_text_and_json(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    assert cli.main(["--book", str(path), "doctor"]) == 0
    assert "health:" in capsys.readouterr().out
    assert cli.main(["--book", str(path), "doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["metrics"]["snippets"] == 2


def test_quality_command_text_and_json(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    assert cli.main(["--book", str(path), "quality", "--threshold", "101"]) == 0
    assert "average:" in capsys.readouterr().out
    assert cli.main(["--book", str(path), "quality", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["scores"]) == 2


def test_snapshot_command_can_store_metadata(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(["--book", str(path), "snapshot", "--label", "release", "--store"])
    assert rc == 0
    assert "stored: yes" in capsys.readouterr().out
    book = Book.load(path)
    assert book.data["metadata"]["snapshots"][0]["label"] == "release"


def test_snapshot_command_json(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    assert cli.main(["--book", str(path), "snapshot", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["snippets"]) == 2


def test_batch_command_is_dry_run_by_default(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(
        [
            "--book",
            str(path),
            "batch",
            "--query",
            "lang:python",
            "--operation",
            "add-tag=reviewed",
        ]
    )
    assert rc == 0
    assert "dry run" in capsys.readouterr().out
    assert not Book.load(path).get("python-one").has_tag("reviewed")


def test_batch_command_applies_selected_changes(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(
        [
            "--book",
            str(path),
            "batch",
            "--query",
            "lang:python",
            "--operation",
            "add-tag=reviewed",
            "--operation",
            "favourite",
            "--apply",
        ]
    )
    assert rc == 0
    output = capsys.readouterr().out
    assert "applied changes to 1 snippets" in output
    book = Book.load(path)
    assert book.get("python-one").has_tag("reviewed")
    assert book.get("python-one").favourite
    assert not book.get("sql-one").favourite


def test_batch_command_requires_operation(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    assert cli.main(["--book", str(path), "batch"]) == 1
    assert "at least one" in capsys.readouterr().err


def test_batch_command_validates_operation(tmp_path, capsys):
    path = tmp_path / "book.json"
    seed(path)
    rc = cli.main(["--book", str(path), "batch", "--operation", "not-real"])
    assert rc == 1
    assert "invalid batch request" in capsys.readouterr().err
