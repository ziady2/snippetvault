import pytest

from snippetbox import migrate
from snippetbox.errors import MigrationError


def test_current_schema_is_three():
    assert migrate.current_schema_version() == 3


def test_needs_migration_for_old_schema():
    assert migrate.needs_migration({"schema_version": 1}) is True


def test_needs_migration_for_current():
    assert migrate.needs_migration({"schema_version": 3}) is False


def test_needs_migration_missing_version():
    assert migrate.needs_migration({}) is True


def test_migrate_v0_list_to_dict(book_dict_v0):
    out = migrate.migrate(book_dict_v0)
    assert out["schema_version"] == 3
    assert isinstance(out["snippets"], list)


def test_migrate_v0_adds_metadata(book_dict_v0):
    out = migrate.migrate(book_dict_v0)
    assert "metadata" in out


def test_migrate_v0_fills_defaults(book_dict_v0):
    out = migrate.migrate(book_dict_v0)
    for s in out["snippets"]:
        assert "language" in s
        assert "tags" in s
        assert "created_at" in s


def test_migrate_v1_adds_collections(book_dict_v1):
    out = migrate.migrate(book_dict_v1)
    assert "collections" in out


def test_migrate_v1_assigns_slug(book_dict_v1):
    out = migrate.migrate(book_dict_v1)
    snippet = out["snippets"][0]
    assert snippet.get("slug")


def test_migrate_v2_to_v3_splits_auto_tags():
    book = {
        "schema_version": 2,
        "snippets": [
            {"id": "1", "title": "x", "body": "b", "tags": ["mine", "auto:python"]},
        ],
        "collections": [],
    }
    out = migrate.migrate(book)
    assert "mine" in out["snippets"][0]["tags"]
    assert "python" in out["snippets"][0]["auto_tags"]


def test_migrate_v2_keeps_existing_auto_tags():
    book = {
        "schema_version": 2,
        "snippets": [
            {"id": "1", "title": "x", "body": "b", "tags": ["m"], "auto_tags": ["already"]},
        ],
        "collections": [],
    }
    out = migrate.migrate(book)
    assert "already" in out["snippets"][0]["auto_tags"]


def test_migrate_v2_coerces_archived_to_bool():
    book = {
        "schema_version": 2,
        "snippets": [{"id": "1", "title": "x", "body": "b", "tags": [], "archived": 1}],
        "collections": [],
    }
    out = migrate.migrate(book)
    assert out["snippets"][0]["archived"] is True


def test_migrate_already_current_unchanged():
    book = {"schema_version": 3, "snippets": [], "collections": [], "metadata": {}}
    out = migrate.migrate(book)
    assert out is book


def test_migrate_rejects_non_dict_input():
    with pytest.raises(MigrationError):
        migrate.migrate("not a dict")  # type: ignore[arg-type]


def test_migrate_unknown_schema_raises():
    with pytest.raises(MigrationError):
        migrate.migrate({"schema_version": 99})


def test_describe_step_known():
    desc = migrate.describe_step(0)
    assert "metadata" in desc.lower() or "initial" in desc.lower()


def test_describe_step_unknown():
    assert "unknown" in migrate.describe_step(999).lower()


def test_history_returns_all_steps():
    history = migrate.history()
    assert len(history) == 3


def test_can_migrate_known_version():
    assert migrate.can_migrate({"schema_version": 1}) is True


def test_can_migrate_current():
    assert migrate.can_migrate({"schema_version": 3}) is True


def test_can_migrate_unknown_version():
    assert migrate.can_migrate({"schema_version": 99}) is False


def test_migrate_v1_dedupes_slugs():
    book = {
        "schema_version": 1,
        "snippets": [
            {"id": "a", "title": "Foo", "body": "x"},
            {"id": "b", "title": "Foo", "body": "y"},
        ],
    }
    out = migrate.migrate(book)
    slugs = [s["slug"] for s in out["snippets"]]
    assert len(set(slugs)) == 2


def test_migrate_v0_preserves_existing_language():
    book = [{"title": "x", "body": "b", "language": "go"}]
    out = migrate.migrate(book)
    assert out["snippets"][0]["language"] == "go"
