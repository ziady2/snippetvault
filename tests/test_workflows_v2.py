from __future__ import annotations

import pytest

from snippetbox.dependencies import DependencyGraph, extract_references
from snippetbox.diffing import apply_line_replacements, changed_line_numbers, compare, side_by_side, similarity
from snippetbox.revision import Revision, RevisionStore, record_many, store_for_book
from snippetbox.review import (
    APPROVED,
    CHANGES_REQUESTED,
    IN_REVIEW,
    PENDING,
    ReviewQueue,
    ReviewRecord,
    queue_for_book,
    save_queue,
)
from snippetbox.snippet import Snippet
from snippetbox.template import SnippetTemplate, TemplateLibrary, parse_assignments, render, variables
from snippetbox.timeline import (
    TimelineEvent,
    between,
    busiest_days,
    counts_by_kind,
    filter_events,
    from_list,
    from_snippets,
    group_by_day,
    merge,
    render_text,
    to_list,
)


def snippet(identifier: str = "one", body: str = "print(1)\n", **kwargs) -> Snippet:
    return Snippet(
        id=identifier,
        title=kwargs.pop("title", identifier),
        body=body,
        created_at=kwargs.pop("created_at", 10.0),
        updated_at=kwargs.pop("updated_at", 10.0),
        **kwargs,
    )


def test_diff_counts_changes_and_renders_unified():
    result = compare("one\ntwo\n", "one\nthree\nfour\n", old_label="v1", new_label="v2")
    assert result.changed()
    assert result.additions == 2
    assert result.deletions == 1
    assert result.unchanged == 1
    assert result.summary() == "+2 -1 (1 unchanged)"
    assert "--- v1" in result.unified()
    assert "+three" in result.unified()


def test_diff_can_ignore_trailing_space():
    assert not compare("value  \n", "value\n", ignore_trailing_space=True).changed()


def test_diff_helpers_report_line_numbers_and_side_by_side():
    result = compare("a\nb", "a\nc")
    assert changed_line_numbers(result) == ([2], [2])
    assert "! b" in side_by_side(result)


def test_similarity_and_line_replacements():
    assert similarity("abc", "abc") == 1.0
    assert apply_line_replacements("a\nb\nc\n", [(1, 2, ["B", "BB"])]) == "a\nB\nBB\nc\n"


def test_line_replacements_reject_overlap():
    with pytest.raises(ValueError):
        apply_line_replacements("a\nb\nc", [(0, 2, ["x"]), (1, 3, ["y"])])


def test_revision_store_records_skips_unchanged_and_restores():
    store = RevisionStore({})
    original = snippet()
    first = store.record(original, message="initial", created_at=10)
    assert first.sequence == 1
    assert store.record(original) is None
    changed = snippet(body="print(2)\n")
    second = store.record(changed, message="fix", created_at=20)
    assert second.sequence == 2
    restored = store.restore("one", "1", touch=False)
    assert restored.body == "print(1)\n"
    assert store.diff("one", first.id, second.id).changed()


def test_revision_detects_tampered_snapshot():
    revision = Revision("r", "one", 1, snippet().to_dict())
    revision.snapshot["body"] = "tampered"
    with pytest.raises(ValueError, match="checksum"):
        revision.validate()


def test_revision_prune_remove_and_validate():
    store = RevisionStore({})
    for number in range(3):
        store.record(snippet(body=f"print({number})"), created_at=number)
    assert store.prune("one", keep=2) == 1
    assert store.count("one") == 2
    assert store.remove("one", "2")
    assert store.count("one") == 1
    assert store.validate() == ["one: expected revision 1, got 3"]


def test_revision_book_helpers(empty_book):
    store = store_for_book(empty_book)
    assert record_many(store, [snippet("a"), snippet("b")], message="seed") == 2
    assert store.count() == 2


def test_template_variables_defaults_and_rendering():
    found = variables("hello ${name}; port=${port:-8080}; again ${name}")
    assert [(item.name, item.default, item.occurrences) for item in found] == [
        ("name", None, 2),
        ("port", "8080", 1),
    ]
    result = render(r"${name} \${literal} ${port:-8080}", {"name": "api", "unused": "x"})
    assert result.text == "api ${literal} 8080"
    assert result.unused == ["unused"]


def test_template_missing_values_strict_and_lenient():
    strict = render("${required}", {})
    assert strict.missing == ["required"]
    with pytest.raises(ValueError):
        strict.require_complete()
    assert render("${required}", {}, strict=False).text == ""


def test_assignment_parser_validates_names():
    assert parse_assignments(["name=value", "empty="]) == {"name": "value", "empty": ""}
    with pytest.raises(ValueError):
        parse_assignments(["bad-name=value"])


def test_snippet_template_instantiation_and_library_round_trip():
    template = SnippetTemplate(
        "python-main",
        "def ${function}():\n    return ${value:-None}\n",
        title="${function} function",
        language="python",
        tags=["template", "template"],
    )
    library = TemplateLibrary([template])
    created = library.instantiate("PYTHON-MAIN", {"function": "main"})
    assert created.title == "main function"
    assert "return None" in created.body
    assert created.extra["template"] == "python-main"
    restored = TemplateLibrary.from_list(library.to_list())
    assert restored.names() == ["python-main"]


def test_dependency_reference_extraction_is_unique():
    text = "@snippet(base) then snippet:helper and @snippet(base)"
    assert extract_references(text) == ["base", "helper"]


def test_dependency_graph_resolves_slugs_and_orders_dependencies():
    base = snippet("base", title="Base")
    child = snippet("child", "@snippet(base)\n", title="Child")
    top = snippet("top", f"snippet:{child.slug}\n", title="Top")
    graph = DependencyGraph.from_snippets([top, child, base])
    assert graph.dependencies_of("top", transitive=True) == {"child", "base"}
    assert graph.dependents_of("base", transitive=True) == {"child", "top"}
    assert graph.topological_order().index("base") < graph.topological_order().index("top")
    assert graph.layers() == [["base"], ["child"], ["top"]]


def test_dependency_graph_reports_missing_and_cycles():
    first = snippet("a", "snippet:b")
    second = snippet("b", "snippet:a snippet:missing")
    graph = DependencyGraph.from_snippets([first, second])
    assert graph.missing() == {"b": {"missing"}}
    assert len(graph.cycles()) == 1
    assert {issue.code for issue in graph.issues()} == {"missing_dependency", "dependency_cycle"}
    with pytest.raises(ValueError, match="cycle"):
        graph.topological_order()


def test_dependency_graph_round_trip():
    graph = DependencyGraph({"a": {"b"}, "b": set()}, {"a": "A"})
    restored = DependencyGraph.from_dict(graph.to_dict())
    assert restored.edges == graph.edges
    assert restored.titles == graph.titles


def test_review_record_enforces_transitions():
    record = ReviewRecord("one", priority=3, labels=["API", "api"])
    assert record.status == PENDING
    assert record.labels == ["api"]
    record.transition(IN_REVIEW, reviewer="Z", at=20)
    event = record.transition(CHANGES_REQUESTED, note="add example", at=30)
    assert event.from_status == IN_REVIEW
    record.transition(APPROVED, at=40)
    with pytest.raises(ValueError):
        record.transition(PENDING)


def test_review_queue_filters_orders_and_marks_stale():
    queue = ReviewQueue()
    first = queue.request("a", priority=1, assignee="Z", labels=["api"])
    second = queue.request("b", priority=5, assignee="Z", labels=["docs"])
    first.updated_at = 10
    second.updated_at = 90
    assert [item.snippet_id for item in queue.list(assignee="z")] == ["b", "a"]
    assert [item.snippet_id for item in queue.list(labels=["api"])] == ["a"]
    assert [item.snippet_id for item in queue.stale(older_than_seconds=50, now=100)] == ["a"]


def test_review_queue_book_round_trip(empty_book):
    queue = queue_for_book(empty_book)
    queue.request("one")
    save_queue(empty_book, queue)
    restored = queue_for_book(empty_book)
    assert restored.get("one").status == PENDING
    assert restored.counts()[PENDING] == 1


def test_timeline_from_snippets_merge_filter_and_render():
    one = snippet("one", created_at=100, updated_at=200)
    events = from_snippets([one])
    manual = TimelineEvent("reviewed", 250, "one", actor="Z")
    combined = merge(events, [manual])
    assert [event.kind for event in combined] == ["snippet_created", "snippet_updated", "reviewed"]
    assert filter_events(combined, actor="z") == [manual]
    assert len(between(combined, start=150, end=250)) == 1
    assert "reviewed" in render_text(combined)


def test_timeline_group_counts_and_round_trip():
    events = [
        TimelineEvent("created", 1_700_000_000, "a"),
        TimelineEvent("created", 1_700_000_100, "b"),
        TimelineEvent("updated", 1_700_086_400, "a"),
    ]
    assert counts_by_kind(events) == {"created": 2, "updated": 1}
    assert sorted(len(group) for group in group_by_day(events).values()) == [1, 2]
    assert busiest_days(events, limit=1)[0][1] == 2
    assert from_list(to_list(events)) == events
