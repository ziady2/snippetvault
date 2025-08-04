from snippetbox.collection import (
    Collection,
    difference,
    find_by_name,
    intersection,
    merge,
    names,
    sort_alpha,
    sort_by_size,
)


def test_collection_strips_name():
    c = Collection(name="  pythons  ")
    assert c.name == "pythons"


def test_collection_dedupes_initial_ids():
    c = Collection(name="x", snippet_ids=["a", "b", "a"])
    assert c.snippet_ids == ["a", "b"]


def test_add_appends_unique_id():
    c = Collection(name="x")
    assert c.add("id1") is True
    assert c.add("id1") is False
    assert c.snippet_ids == ["id1"]


def test_add_blank_returns_false():
    c = Collection(name="x")
    assert c.add("") is False


def test_remove_existing_id():
    c = Collection(name="x", snippet_ids=["a", "b"])
    assert c.remove("b") is True
    assert c.snippet_ids == ["a"]


def test_remove_missing_id():
    c = Collection(name="x", snippet_ids=["a"])
    assert c.remove("missing") is False


def test_contains():
    c = Collection(name="x", snippet_ids=["a"])
    assert c.contains("a") is True
    assert c.contains("b") is False


def test_size_and_is_empty():
    c = Collection(name="x")
    assert c.is_empty() is True
    assert c.size() == 0
    c.add("a")
    assert c.is_empty() is False
    assert c.size() == 1


def test_rename_changes_name():
    c = Collection(name="x")
    c.rename("y")
    assert c.name == "y"


def test_rename_blank_keeps_old():
    c = Collection(name="x")
    c.rename("")
    assert c.name == "x"


def test_replace_ids_dedupes():
    c = Collection(name="x")
    c.replace_ids(["a", "a", "b"])
    assert c.snippet_ids == ["a", "b"]


def test_to_dict_round_trip():
    c = Collection(name="x", description="d", snippet_ids=["a"])
    d = c.to_dict()
    c2 = Collection.from_dict(d)
    assert c2.name == c.name
    assert c2.snippet_ids == c.snippet_ids


def test_merge_combines_unique():
    a = Collection(name="A", snippet_ids=["1", "2"])
    b = Collection(name="B", snippet_ids=["2", "3"])
    out = merge(a, b)
    assert out.snippet_ids == ["1", "2", "3"]


def test_merge_takes_explicit_name():
    a = Collection(name="A", snippet_ids=["1"])
    b = Collection(name="B", snippet_ids=["2"])
    out = merge(a, b, name="combined")
    assert out.name == "combined"


def test_difference_drops_overlap():
    a = Collection(name="A", snippet_ids=["1", "2", "3"])
    b = Collection(name="B", snippet_ids=["2"])
    out = difference(a, b)
    assert out.snippet_ids == ["1", "3"]


def test_intersection_keeps_overlap():
    a = Collection(name="A", snippet_ids=["1", "2"])
    b = Collection(name="B", snippet_ids=["2", "3"])
    out = intersection(a, b)
    assert out.snippet_ids == ["2"]


def test_find_by_name():
    a = Collection(name="A")
    b = Collection(name="B")
    assert find_by_name([a, b], "B") is b


def test_find_by_name_missing():
    assert find_by_name([Collection(name="A")], "Z") is None


def test_names_helper():
    cs = [Collection(name="A"), Collection(name="B")]
    assert names(cs) == ["A", "B"]


def test_sort_by_size_descending():
    a = Collection(name="A", snippet_ids=["1"])
    b = Collection(name="B", snippet_ids=["1", "2"])
    assert sort_by_size([a, b])[0] is b


def test_sort_alpha_case_insensitive():
    a = Collection(name="zzz")
    b = Collection(name="Aaa")
    assert sort_alpha([a, b])[0] is b
