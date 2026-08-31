"""The marts ontology, proven without an LLM and — for the pure core — without a database.

    PYTHONPATH=src uv run python ontology/tests/test_graph.py    # or: pytest ontology/tests

The module is a functional core with an imperative shell, so the tests split the same way. Most
assert against `from_source`, `joinable`, `render`, `verify` and `fingerprint` — pure functions of
plain data, fast and DB-free. A short tail exercises `build`, the only part that touches a cursor.
Each test states WHY its assertion matters, not what it does.

The interpretive half — decomposing a natural-language measure into ingredients — is the model's and
lives in the agent; here we test only what the module owns: the deterministic seam.
"""
from __future__ import annotations

import duckdb

from ontology.graph import (COMPUTABLE, INSTRUMENTED, UNINSTRUMENTED, MartsOntology, island_source,
                            joinable)

# A `source` shaped like what the semantic layer's ontology_source() returns, and the columns each
# table would report. `spend` exists but is related to nothing — the case a node-only existence
# check would wrongly call computable, and the reason joinability is a separate check.
COLUMNS = {
    "dim_users": ("user_id", "signup_date", "channel", "is_internal"),
    "fct_user_days": ("user_id", "active_date", "value_moments", "app_opens"),
    "fct_marketing_spend": ("channel", "spend_date", "spend"),
}
SOURCE = {
    "entities": {
        "user": {"table": "dim_users", "grain": "one row per account",
                 "measures": (), "relationships": ()},
        "activity": {"table": "fct_user_days", "grain": "one row per account per active day",
                     "measures": ("value_moments", "app_opens"),
                     "relationships": [("user", "joined on user_id")]},
        "spend": {"table": "fct_marketing_spend", "grain": "one row per channel per day",
                  "measures": ("spend",), "relationships": ()},
    },
    "metrics": {"active_users": "distinct accounts with activity, excluding internal"},
    "measure_semantics": {"value_moments": "count of completed habits",
                          "app_opens": "count of app-open events", "spend": "marketing spend (currency)"},
}


def _ont(source=SOURCE, columns=COLUMNS):
    """A graph built purely — no database — so every core test is a plain function call."""
    return MartsOntology.from_source(source, columns)


# ── joinable: the extracted graph primitive ──────────────────────────────────────────────────
def test_joinable_is_trivial_below_two_entities():
    """A measure on one entity (or none) needs no join, so it must never be rejected for one."""
    assert joinable(frozenset(), set()) is True
    assert joinable(frozenset(), {"user"}) is True


def test_joinable_true_for_a_connected_pair():
    """Two entities linked by a relationship can be joined — the ordinary computable case."""
    assert joinable(frozenset({frozenset({"a", "b"})}), {"a", "b"}) is True


def test_joinable_false_for_a_disconnected_pair():
    """Two entities with no relationship between them cannot be joined; a derivation spanning them
    is not computable however real each node is."""
    assert joinable(frozenset({frozenset({"a", "b"})}), {"a", "c"}) is False


def test_joinable_follows_a_transitive_chain():
    """Joinability is connectivity, not adjacency: a—b and b—c means a and c can be joined via b."""
    edges = frozenset({frozenset({"a", "b"}), frozenset({"b", "c"})})
    assert joinable(edges, {"a", "c"}) is True


# ── from_source: pure assembly ───────────────────────────────────────────────────────────────
def test_every_column_becomes_a_node():
    """The graph is the complete present: each column of each entity table is a node, so existence
    can be decided by membership alone."""
    ont = _ont()
    assert {"user.signup_date", "user.is_internal", "activity.value_moments",
            "activity.app_opens", "spend.spend"} <= ont.nodes


def test_attributes_are_the_non_measure_columns():
    """Attributes and measures partition an entity's columns; getting the split wrong would let a
    measure be cited as a dimension or hide it from the model."""
    ont = _ont()
    assert set(ont.entities["activity"]["attributes"]) == {"user_id", "active_date"}
    assert ont.entities["activity"]["measures"] == ("value_moments", "app_opens")


def test_metrics_become_nodes_and_absent_concepts_do_not():
    """A governed metric is a node so `governed` can be verified; a concept the warehouse never
    captured is simply not a node — that is how absence is derived, not enumerated."""
    ont = _ont()
    assert "metric.active_users" in ont.nodes
    assert "activity.duration" not in ont.nodes and "user.dark_mode" not in ont.nodes


def test_measure_that_is_not_a_column_raises():
    """A declared measure absent from the table is a lie the graph must refuse at build time, not a
    node it silently invents."""
    bad = {"entities": {"e": {"table": "t", "measures": ("nope",)}}, "metrics": {}}
    try:
        MartsOntology.from_source(bad, {"t": ("a", "b")})
    except ValueError:
        return
    raise AssertionError("from_source should reject a measure that is not a column")


def test_measure_semantics_argument_overrides_source():
    """The optional argument lets a caller enrich a thin manifest description; it must win over the
    source's own text for the same measure."""
    ont = MartsOntology.from_source(SOURCE, COLUMNS, measure_semantics={"spend": "ad money, GBP"})
    assert ont.measure_semantics["spend"] == "ad money, GBP"
    assert ont.measure_semantics["app_opens"] == "count of app-open events"   # untouched


# ── render: the model's surface ──────────────────────────────────────────────────────────────
def test_render_asserts_the_closed_world_stance_without_enumerating_absence():
    """The model must be told the graph is COMPLETE (so absence means non-existence), and must NOT be
    handed a list of what is missing — that list is the anti-pattern this design removed."""
    r = _ont().render()
    assert "CLOSED WORLD" in r and "COMPLETE" in r
    assert "no duration" not in r.lower() and "no screen" not in r.lower()


def test_render_states_grain_and_describes_measures_positively():
    """Grain decides whether a derivation is computable; a positive measure description ('count of…')
    keeps the model from reading a count as a duration."""
    r = _ont().render()
    assert "one row per account per active day" in r
    assert "count of app-open events" in r


def test_render_lists_relationships():
    """The model needs to see which entities can be joined to decompose a cross-entity measure."""
    assert "activity <-> user" in _ont().render()


def test_render_truncates_long_metric_descriptions():
    """The surface stays bounded so one verbose metric cannot dominate the prompt."""
    long = {"entities": {}, "metrics": {"m": "x" * 500}}
    r = MartsOntology.from_source(long, {}).render(metric_desc_chars=40)
    assert "x" * 40 in r and "x" * 41 not in r


# ── verify: the seam ─────────────────────────────────────────────────────────────────────────
def test_governed_upholds_a_real_metric_and_rejects_a_fake_one():
    """`governed` is only safe if a claimed metric that does not exist is refused, not served."""
    ont = _ont()
    assert ont.verify("governed", metric="active_users")[0] == INSTRUMENTED
    assert ont.verify("governed", metric="retention")[0] == UNINSTRUMENTED


def test_governed_strips_a_metric_prefix():
    """The model may cite `metric.active_users` verbatim from the surface; that must resolve, not
    fail on a formatting difference."""
    assert _ont().verify("governed", metric="metric.active_users")[0] == INSTRUMENTED


def test_computable_when_ingredients_exist_and_join():
    """The ordinary computable case: real nodes on entities that can be joined (retention)."""
    v, _ = _ont().verify("computable", ingredients=["user.signup_date", "activity.active_date"])
    assert v == COMPUTABLE


def test_computable_rejects_an_absent_ingredient():
    """A derivation that needs a node the graph lacks is uninstrumented, not computable."""
    assert _ont().verify("computable", ingredients=["activity.duration"])[0] == UNINSTRUMENTED


def test_computable_rejects_unjoinable_entities():
    """Both nodes exist, but user and spend have no relationship, so the derivation cannot be
    computed — the joinability guard a node-only check would have passed."""
    v, why = _ont().verify("computable", ingredients=["user.channel", "spend.spend"])
    assert v == UNINSTRUMENTED and "not related" in why


def test_verify_tolerates_the_models_surface_formatting():
    """The model may wrap a node in a parenthetical or a description; existence is a property of the
    reference, not the exact string, so verify extracts the entity.column token before checking. An
    exact-string match would false-refuse a real node over an added space — the brittleness fixed."""
    ont = _ont()
    v, _ = ont.verify("computable",
                      ingredients=["user.signup_date (the signup date)", "activity.active_date"])
    assert v == COMPUTABLE
    assert ont.verify("governed", metric="metric.active_users (the active users metric)")[0] == INSTRUMENTED


def test_computable_rejects_a_claim_with_no_ingredients():
    """A `computable` verdict with nothing to verify must not pass vacuously — the model has to name
    the graph nodes it would derive from."""
    assert _ont().verify("computable", ingredients=[])[0] == UNINSTRUMENTED
    assert _ont().verify("computable", ingredients=["no dots here"])[0] == UNINSTRUMENTED


def test_uninstrumented_and_unknown_kinds_are_uninstrumented():
    """The explicit uninstrumented verdict, and any unrecognised kind, resolve to refuse — the safe
    default when the model's claim is not one the graph can uphold."""
    assert _ont().verify("uninstrumented")[0] == UNINSTRUMENTED
    assert _ont().verify("something_else")[0] == UNINSTRUMENTED


# ── fingerprint: covers the whole rendered surface ───────────────────────────────────────────
def test_fingerprint_is_stable_and_prefixed():
    """Same graph, same digest — so a fingerprint can be compared across runs to detect drift."""
    assert _ont().fingerprint() == _ont().fingerprint()
    assert _ont().fingerprint().startswith("sha256:")


def test_fingerprint_moves_with_a_new_column():
    """A schema change the model would see must change the digest, or a stale graph goes unnoticed."""
    cols = {**COLUMNS, "dim_users": COLUMNS["dim_users"] + ("plan",)}
    assert MartsOntology.from_source(SOURCE, cols).fingerprint() != _ont().fingerprint()


def test_fingerprint_moves_with_measure_semantics_and_grain():
    """These are part of the surface the model reads; the review's fix was to make the digest cover
    them too, so a reworded measure or a changed grain cannot slip past unchanged."""
    reworded = {**SOURCE, "measure_semantics": {**SOURCE["measure_semantics"], "spend": "changed"}}
    assert MartsOntology.from_source(reworded, COLUMNS).fingerprint() != _ont().fingerprint()
    regrained = {**SOURCE, "entities": {**SOURCE["entities"],
                 "user": {**SOURCE["entities"]["user"], "grain": "one row per household"}}}
    assert MartsOntology.from_source(regrained, COLUMNS).fingerprint() != _ont().fingerprint()


# ── build: the imperative shell (the only DB-backed tests) ──────────────────────────────────
def _con():
    con = duckdb.connect()
    con.execute("create schema m")
    con.execute("create table m.dim_users(user_id int, signup_date date, channel varchar, is_internal boolean)")
    con.execute("create table m.fct_user_days(user_id int, active_date date, value_moments int, app_opens int)")
    con.execute("create table m.fct_marketing_spend(channel varchar, spend_date date, spend double)")
    return con


def test_build_fetches_columns_and_matches_the_pure_core():
    """The shell must read exactly the columns the pure core was tested against — same source, same
    columns, same graph — so the DB path adds no behaviour beyond the I/O."""
    built = MartsOntology.build(_con(), "m", SOURCE)
    assert built.nodes == _ont().nodes
    assert built.fingerprint() == _ont().fingerprint()


def test_build_rejects_a_measure_that_is_not_a_column():
    """The honesty check must hold through the shell: a measure absent from the real table raises."""
    con = duckdb.connect(); con.execute("create schema m"); con.execute("create table m.t(a int)")
    src = {"entities": {"e": {"table": "t", "measures": ("not_a_column",)}}, "metrics": {}}
    try:
        MartsOntology.build(con, "m", src)
    except ValueError:
        return
    raise AssertionError("build should reject a measure that is not a column")


# ── island_source + build_marts: hybrid completeness ─────────────────────────────────────────
def test_island_source_adds_unmodeled_tables_as_islands():
    """Every marts table must become an entity so absence is derivable over the whole warehouse; a
    table the manifest does not model becomes an island with no relationships, so it can never be
    joined by inference."""
    all_tables = [d["table"] for d in SOURCE["entities"].values()] + ["fct_referrals", "dim_channel"]
    full = island_source(SOURCE, all_tables)
    assert set(full["entities"]) == {"user", "activity", "spend", "referrals", "channel"}
    assert full["entities"]["referrals"] == {"table": "fct_referrals", "grain": "one row per referrals",
                                             "measures": (), "relationships": ()}
    assert full["entities"]["user"] == SOURCE["entities"]["user"]          # modeled entity untouched
    assert full["metrics"] == SOURCE["metrics"]                            # metrics preserved


def test_island_source_keeps_the_table_name_on_a_prefix_collision():
    """Stripping dim_/fct_ is only for readability; if it would collide with a modeled entity name,
    keep the unambiguous table name rather than merge two entities into one."""
    src = {"entities": {"user": {"table": "dim_x", "measures": (), "relationships": ()}}, "metrics": {}}
    full = island_source(src, ["dim_x", "dim_user"])     # 'dim_user' strips to 'user', already taken
    assert full["entities"]["dim_user"]["table"] == "dim_user"


def test_build_marts_is_complete_and_islands_do_not_join():
    """The graph the agent trusts: an unmodeled table's columns EXIST (its own concepts resolve), but
    a derivation joining it to a modeled entity is refused until a relationship is curated — the
    under-claim that makes an incomplete graph safe rather than wrong."""
    con = _con()
    con.execute("create table m.fct_referrals(referral_id int, user_id int, referred_at date)")
    ont = MartsOntology.build_marts(con, "m", SOURCE)
    assert "referrals" in ont.entities and "referrals.referred_at" in ont.nodes         # island exists
    assert ont.verify("computable", ingredients=["referrals.referred_at"])[0] == COMPUTABLE
    v, why = ont.verify("computable", ingredients=["user.signup_date", "referrals.referred_at"])
    assert v == UNINSTRUMENTED and "not related" in why                                 # island won't join
    assert ont.verify("computable",                                                     # modeled join holds
                      ingredients=["user.signup_date", "activity.active_date"])[0] == COMPUTABLE


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(tests)} passed")
