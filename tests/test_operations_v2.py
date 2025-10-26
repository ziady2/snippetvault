from __future__ import annotations


import pytest

from snippetbox.batch import BatchOperation
from snippetbox.import_plan import (
    ADD,
    CONFLICT,
    RENAME,
    REPLACE,
    SKIP,
    apply as apply_import,
    plan as plan_import,
)
from snippetbox.selection import SavedSelection, SelectionLibrary, library_for_book, save_library
from snippetbox.service import SnippetService
from snippetbox.snippet import Snippet
from snippetbox.sync import (
    ADD_LOCAL,
    ADD_REMOTE,
    CONFLICT as SYNC_CONFLICT,
    DELETE_LOCAL,
    DELETE_REMOTE,
    TAKE_LOCAL,
    changed_ids,
    merged,
    plan as plan_sync,
)
from snippetbox.template import SnippetTemplate
from snippetbox.transform import (
    Transform,
    apply,
    apply_one,
    apply_to_snippet,
    default_cleanup,
    parse,
    render,
)


def make_snippet(identifier: str, body: str = "print(1)\n", **kwargs) -> Snippet:
    values = {
        "id": identifier,
        "title": kwargs.pop("title", identifier.title()),
        "body": body,
        "language": "python",
        "created_at": 100,
        "updated_at": 100,
    }
    values.update(kwargs)
    return Snippet(**values)


def test_transform_default_cleanup_and_preview():
    result = apply("\r\n    one  \r\n    two\t\r\n", default_cleanup())
    assert result.text == "    one\n    two\n"
    assert result.changed
    assert result.changed_steps
    assert result.summary()["steps"] == 4
    assert "changed: yes" in render(result, include_diff=True)


def test_transform_dedent_tabs_and_replace():
    result = apply(
        "\t    hello NAME\n\t    bye name",
        [
            Transform("tabs_to_spaces", options={"width": 4}),
            Transform("dedent"),
            Transform("replace", "NAME", "world"),
            Transform("regex_replace", "name", "world", {"ignore_case": True}),
        ],
    )
    assert result.text == "hello world\nbye world"


def test_transform_parse_and_apply_to_snippet():
    transforms = parse(["replace=old=>new", "ensure-final-newline"])
    original = make_snippet("one", "old")
    changed, result = apply_to_snippet(original, transforms, touch=False)
    assert original.body == "old"
    assert changed.body == "new\n"
    assert result.changed


def test_transform_validation_and_bad_regex():
    with pytest.raises(ValueError):
        Transform("missing")
    with pytest.raises(ValueError):
        Transform("tabs_to_spaces", options={"width": 0})
    with pytest.raises(ValueError, match="invalid transform regex"):
        apply_one("x", Transform("regex_replace", "[", ""))
    with pytest.raises(ValueError):
        parse(["replace=missing-separator"])


def test_import_plan_add_skip_and_rename():
    existing = [make_snippet("existing", "same", title="Existing", slug="same")]
    incoming = [
        make_snippet("duplicate-content", "same", title="Copy", slug="copy"),
        make_snippet("slug-collision", "different", title="Same", slug="same"),
        make_snippet("new", "new", title="New", slug="new"),
    ]
    result = plan_import(existing, incoming)
    assert [item.action for item in result.items] == [SKIP, RENAME, ADD]
    assert result.items[1].incoming.slug == "same-2"
    assert result.ready


def test_import_plan_id_conflict_and_resolution():
    existing = [make_snippet("one", "before")]
    incoming = [make_snippet("one", "after")]
    result = plan_import(existing, incoming)
    assert result.items[0].action == CONFLICT
    assert not result.ready
    assert result.resolve_all(SKIP) == 1
    assert result.ready


def test_import_plan_replace_and_apply(empty_book):
    original = make_snippet("one", "before")
    empty_book.add(original)
    incoming = make_snippet("one", "after", slug=original.slug)
    result = plan_import(list(empty_book), [incoming], id_strategy=REPLACE)
    assert result.items[0].action == REPLACE
    counts = apply_import(empty_book, result)
    assert counts[REPLACE] == 1
    assert empty_book.get("one").body == "after"


def test_import_apply_rejects_unresolved_conflicts(empty_book):
    original = make_snippet("one", "before")
    empty_book.add(original)
    result = plan_import(list(empty_book), [make_snippet("one", "after")])
    with pytest.raises(ValueError, match="unresolved"):
        apply_import(empty_book, result)


def test_sync_plan_detects_one_sided_additions_and_changes():
    base = [make_snippet("base", "v1")]
    local = [make_snippet("base", "local"), make_snippet("local-new")]
    remote = [make_snippet("base", "v1"), make_snippet("remote-new")]
    result = plan_sync(base, local, remote)
    actions = {item.snippet_id: item.action for item in result.items}
    assert actions == {"base": TAKE_LOCAL, "local-new": ADD_LOCAL, "remote-new": ADD_REMOTE}
    assert {item.id for item in merged(result)} == {"base", "local-new", "remote-new"}


def test_sync_plan_propagates_one_sided_deletions():
    base = [make_snippet("local-delete"), make_snippet("remote-delete")]
    local = [make_snippet("remote-delete")]
    remote = [make_snippet("local-delete")]
    result = plan_sync(base, local, remote)
    actions = {item.snippet_id: item.action for item in result.items}
    assert actions == {"local-delete": DELETE_REMOTE, "remote-delete": DELETE_LOCAL}
    assert merged(result) == []


def test_sync_plan_conflict_can_be_resolved():
    base = [make_snippet("one", "base")]
    local = [make_snippet("one", "local")]
    remote = [make_snippet("one", "remote")]
    result = plan_sync(base, local, remote)
    assert result.items[0].action == SYNC_CONFLICT
    assert changed_ids(result) == ["one"]
    with pytest.raises(ValueError):
        merged(result)
    assert result.resolve("one", "remote")
    assert merged(result)[0].body == "remote"
    assert "take_remote" in result.render()


def test_selection_evaluates_query_pins_and_exclusions():
    python = make_snippet("py", tags=["web"])
    sql = make_snippet("sql", language="sql")
    selection = SavedSelection("web", "tag:web", pinned_ids=["sql"], excluded_ids=["missing"])
    assert [item.id for item in selection.evaluate([python, sql])] == ["py", "sql"]
    assert selection.exclude("py")
    assert [item.id for item in selection.evaluate([python, sql])] == ["sql"]
    assert selection.pin("py")
    assert "py" not in selection.excluded_ids


def test_selection_library_crud_and_book_round_trip(empty_book):
    library = SelectionLibrary([SavedSelection("python", "lang:python")])
    assert library.rename("python", "code")
    assert library.get("CODE").query == "lang:python"
    save_library(empty_book, library)
    restored = library_for_book(empty_book)
    assert restored.list()[0].name == "code"
    assert restored.remove("code")


def test_service_add_update_query_revision_and_delete(empty_book):
    service = SnippetService(empty_book)
    item = make_snippet("one", tags=["web"])
    added = service.add(item, request_review=True)
    assert added.changed
    assert added.revision.sequence == 1
    assert service.reviews().get("one") is not None
    assert service.structured_query("tag:web") == [item]
    item.body = "print(2)"
    updated = service.update(item, revision_message="change")
    assert updated.revision.sequence == 2
    assert service.related("missing") == []
    deleted = service.delete("one")
    assert deleted.changed
    assert empty_book.get("one") is None
    assert service.reviews().get("one") is None


def test_service_templates_batch_snapshot_health_and_share(empty_book):
    service = SnippetService(empty_book)
    assert service.add_template(
        SnippetTemplate("hello", "print(${value})", title="Hello ${value}", language="python")
    )
    created = service.instantiate("hello", {"value": "42"}, add=True)
    assert empty_book.get(created.id) is not None
    batch_plan = service.plan_batch([BatchOperation("add_tag", "generated")])
    assert service.apply_batch(batch_plan) == 1
    assert empty_book.get(created.id).has_tag("generated")
    assert service.snapshot(label="test", store=True).label == "test"
    assert service.health().metrics["snippets"] == 1
    assert service.quality().scores
    assert service.share()[0].snippet.source == ""


def test_service_review_transition_and_missing_errors(empty_book):
    service = SnippetService(empty_book)
    item = make_snippet("one")
    service.add(item)
    record = service.request_review("one", priority=2)
    assert record.priority == 2
    event = service.transition_review("one", "in_review", reviewer="Z")
    assert event.to_status == "in_review"
    with pytest.raises(KeyError):
        service.request_review("missing")
