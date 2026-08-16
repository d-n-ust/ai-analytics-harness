"""Population algebra: predicate normalisation, segment resolution, and subsumption."""

from hypothesis import given
from hypothesis import strategies as st

from preflight.scope import (
    build_scope,
    is_subset,
    parse_predicates,
    scope_equal,
    subsumes,
)


def _set(col, *vals):
    return (col, "set", frozenset(vals))


# ── predicate parsing ────────────────────────────────────────────────────────────────────────────
def test_equality_becomes_a_value_set():
    assert parse_predicates("status = 'completed'") == [_set("status", "completed")]


def test_in_becomes_a_value_set():
    preds = parse_predicates("status in ('completed', 'shipped')")
    assert preds == [_set("status", "completed", "shipped")]


def test_boolean_forms_all_normalise():
    # bare column, = true, = 1 all mean {'true'}
    for expr in ("is_internal", "is_internal = true", "is_internal = 1"):
        assert parse_predicates(expr) == [_set("is_internal", "true")], expr
    # negation, = false, = 0 all mean {'false'}
    for expr in ("not is_internal", "is_internal = false", "is_internal = 0"):
        assert parse_predicates(expr) == [_set("is_internal", "false")], expr


def test_is_null_variants():
    assert parse_predicates("deleted_at is null") == [_set("deleted_at", "false")]
    assert parse_predicates("deleted_at is not null") == [_set("deleted_at", "true")]


def test_top_level_and_splits_into_leaves():
    preds = parse_predicates("status = 'completed' and region = 'us'")
    assert _set("status", "completed") in preds
    assert _set("region", "us") in preds
    assert len(preds) == 2


def test_comparison_kept_as_cmp():
    (col, kind, _), = parse_predicates("amount >= 100")
    assert (col, kind) == ("amount", "cmp")


def test_empty_filter_is_empty_scope():
    assert parse_predicates(None) == []
    assert build_scope(None) == ()


# ── segment resolution ─────────────────────────────────────────────────────────────────────────--
def test_declared_segment_resolves_to_its_filter():
    seg_map = {"active": "is_active = true"}
    assert build_scope(None, segment="active", seg_map=seg_map) == (_set("is_active", "true"),)


def test_unknown_segment_kept_as_marker():
    assert build_scope(None, segment="vip", seg_map={}) == (_set("segment", "vip"),)


def test_segment_all_is_ignored():
    assert build_scope(None, segment="all") == ()


# ── subsumption ────────────────────────────────────────────────────────────────────────────────--
def test_everything_is_a_subset_of_the_empty_population():
    assert is_subset((_set("status", "completed"),), ()) is True


def test_narrower_value_set_is_a_subset():
    narrow = (_set("status", "completed"),)
    wide = (_set("status", "completed", "shipped"),)
    assert is_subset(narrow, wide) is True
    assert is_subset(wide, narrow) is False


def test_subsumes_is_false_for_equal_and_for_incomparable():
    s = (_set("status", "completed"),)
    assert subsumes(s, s) is False                                   # equal, not strict
    other = (_set("region", "us"),)
    assert subsumes(s, other) is False                              # incomparable
    assert subsumes((), s) is True                                  # () wider than a filtered pop


# ── properties ─────────────────────────────────────────────────────────────────────────────────--
_scopes = st.lists(
    st.tuples(st.sampled_from(["status", "region", "is_internal"]),
              st.just("set"),
              st.frozensets(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=3)),
    max_size=4,
).map(lambda xs: tuple(sorted(set(xs), key=lambda p: (p[0], p[1], str(p[2])))))


@given(_scopes)
def test_scope_equal_and_subset_are_reflexive(s):
    assert scope_equal(s, s)
    assert is_subset(s, s)


@given(_scopes, _scopes)
def test_scope_equal_is_symmetric(a, b):
    assert scope_equal(a, b) == scope_equal(b, a)
