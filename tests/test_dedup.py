from snippetbox import dedup
from snippetbox.snippet import Snippet


def test_fingerprint_is_stable_for_same_body():
    a = Snippet(title="x", body="x = 1", language="python")
    b = Snippet(title="y", body="x = 1", language="python")
    assert dedup.fingerprint(a) == dedup.fingerprint(b)


def test_fingerprint_ignores_trailing_whitespace():
    a = Snippet(title="x", body="x = 1   ", language="python")
    b = Snippet(title="y", body="x = 1", language="python")
    assert dedup.fingerprint(a) == dedup.fingerprint(b)


def test_fingerprint_differs_for_different_bodies():
    a = Snippet(title="x", body="a", language="python")
    b = Snippet(title="y", body="b", language="python")
    assert dedup.fingerprint(a) != dedup.fingerprint(b)


def test_fingerprint_with_drop_comments():
    a = Snippet(title="x", body="# comment\nx = 1", language="python")
    b = Snippet(title="y", body="x = 1", language="python")
    assert dedup.fingerprint(a, drop_comments=True) == dedup.fingerprint(b, drop_comments=True)


def test_find_duplicates_finds_pairs():
    a = Snippet(title="x", body="same body", language="python")
    b = Snippet(title="y", body="same body", language="python")
    c = Snippet(title="z", body="different", language="python")
    clusters = dedup.find_duplicates([a, b, c])
    assert len(clusters) == 1


def test_find_duplicates_no_duplicates():
    a = Snippet(title="x", body="a", language="python")
    b = Snippet(title="y", body="b", language="python")
    assert dedup.find_duplicates([a, b]) == []


def test_cluster_primary_returns_earliest():
    a = Snippet(title="x", body="b", language="python")
    a.created_at = 100
    b = Snippet(title="y", body="b", language="python")
    b.created_at = 50
    cluster = dedup.Cluster([a, b])
    assert cluster.primary() is b


def test_cluster_others():
    a = Snippet(title="x", body="b", language="python")
    a.created_at = 100
    b = Snippet(title="y", body="b", language="python")
    b.created_at = 50
    cluster = dedup.Cluster([a, b])
    others = cluster.others()
    assert others == [a]


def test_cluster_size():
    cluster = dedup.Cluster([Snippet(title="x", body="b"), Snippet(title="y", body="b")])
    assert cluster.size() == 2


def test_jaccard_identical():
    assert dedup.jaccard("a b c", "a b c") == 1.0


def test_jaccard_disjoint():
    assert dedup.jaccard("a b", "c d") == 0.0


def test_jaccard_partial():
    assert 0 < dedup.jaccard("a b c", "b c d") < 1.0


def test_jaccard_blank_blank():
    assert dedup.jaccard("", "") == 1.0


def test_jaccard_one_blank():
    assert dedup.jaccard("a", "") == 0.0


def test_find_near_duplicates_basic():
    a = Snippet(title="x", body="a b c d", language="python")
    b = Snippet(title="y", body="a b c e", language="python")
    pairs = dedup.find_near_duplicates([a, b], threshold=0.5)
    assert len(pairs) == 1


def test_find_near_duplicates_threshold():
    a = Snippet(title="x", body="a b c d", language="python")
    b = Snippet(title="y", body="x y z w", language="python")
    pairs = dedup.find_near_duplicates([a, b], threshold=0.5)
    assert pairs == []


def test_find_near_duplicates_skips_different_languages():
    a = Snippet(title="x", body="a b c", language="python")
    b = Snippet(title="y", body="a b c", language="javascript")
    pairs = dedup.find_near_duplicates([a, b], threshold=0.5)
    assert pairs == []


def test_find_near_duplicates_allows_cross_lang_when_off():
    a = Snippet(title="x", body="a b c", language="python")
    b = Snippet(title="y", body="a b c", language="javascript")
    pairs = dedup.find_near_duplicates([a, b], threshold=0.5, same_language=False)
    assert len(pairs) == 1


def test_merge_pair_combines_tags():
    a = Snippet(title="a", body="x", tags=["t1"])
    b = Snippet(title="b", body="x", tags=["t2"])
    out = dedup.merge_pair(a, b)
    assert "t1" in out.tags
    assert "t2" in out.tags


def test_merge_pair_combines_notes():
    a = Snippet(title="a", body="x", notes="A note")
    b = Snippet(title="b", body="x", notes="B note")
    out = dedup.merge_pair(a, b)
    assert "A note" in out.notes
    assert "B note" in out.notes


def test_merge_pair_picks_max_used():
    a = Snippet(title="a", body="x")
    a.used_count = 1
    b = Snippet(title="b", body="x")
    b.used_count = 5
    out = dedup.merge_pair(a, b)
    assert out.used_count == 5


def test_merge_pair_promotes_favourite():
    a = Snippet(title="a", body="x")
    b = Snippet(title="b", body="x", favourite=True)
    out = dedup.merge_pair(a, b)
    assert out.favourite is True


def test_report_describes_clusters():
    a = Snippet(title="a", body="x")
    b = Snippet(title="b", body="x")
    clusters = [dedup.Cluster([a, b])]
    out = dedup.report(clusters)
    assert "duplicate" in out


def test_report_empty():
    assert dedup.report([]) == ""


def test_total_duplicates_counts_extras():
    a = Snippet(title="a", body="x")
    b = Snippet(title="b", body="x")
    c = Snippet(title="c", body="y")
    d = Snippet(title="d", body="y")
    clusters = dedup.find_duplicates([a, b, c, d])
    assert dedup.total_duplicates(clusters) == 2
