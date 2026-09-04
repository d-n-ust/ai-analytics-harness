"""The measure spec's pure core — NO LLM, NO database.

    PYTHONPATH=engine/src uv run python engine/tests/test_measure.py   # or: pytest engine/tests/test_measure.py

`bind_scope` is the completeness half of aptness: every segment / period / qualifier the question
named must be bound in the spec, or it is reported unbound. These tests fix that behaviour against
the exact silent-drop cases it exists to catch (cost-per-signup, web-growth, MRR-this-year), and the
recursion through a derived spec's inputs. Each test states WHY it matters.

Interpretation — whether a bound component is read correctly — is the adversary's and is NOT tested
here; this module only owns completeness.
"""
from __future__ import annotations

from ontology.graph import MartsOntology

from agent.core.measure import Scope, Spec, applied_segments, bind_scope, coherent, ground, periods

# A closed-world graph built PURELY (no DB) — user⋈activity are related, spend is an island. Enough
# to exercise grounding: a governed metric, computable ingredients that join, and an unjoinable pair.
_SOURCE = {
    "entities": {
        "user": {"table": "dim_users", "measures": (), "relationships": ()},
        "activity": {"table": "fct_user_days", "measures": ("value_moments",),
                     "relationships": [("user", "user_id")]},
        "spend": {"table": "fct_marketing_spend", "measures": ("spend",), "relationships": ()},
    },
    "metrics": {"active_users": "distinct active accounts", "new_signups": "accounts created"},
}
_COLUMNS = {
    "dim_users": ("user_id", "signup_date", "channel"),
    "fct_user_days": ("user_id", "active_date", "value_moments"),
    "fct_marketing_spend": ("channel", "spend_date", "spend"),
}
_ONT = MartsOntology.from_source(_SOURCE, _COLUMNS)


# ── constructors + the uniform surface ────────────────────────────────────────────────────────
def test_a_governed_metric_is_the_trivial_spec():
    """Governed and ad-hoc must flow through one shape, or the whole design forks. A metric spec with
    no filters covers a scope with no components."""
    spec = Spec.governed("active_users")
    assert spec.kind == "metric" and spec.metric == "active_users"
    assert bind_scope(Scope(measure="active users"), spec) == ()


def test_applied_segments_gathers_across_a_derived_tree():
    """A filter on any input of a derived spec binds the question's segment — 'web' on a ratio's
    numerator is 'web' for the ratio. A per-input filter that did not propagate would read as a drop."""
    num = Spec.governed("marketing_spend", filters=[("activity__platform", "web")])
    den = Spec.governed("new_signups")
    ratio = Spec.derived("ratio", inputs=[num, den])
    assert ("platform", "web") in applied_segments(ratio)


def test_periods_gathers_both_windows_of_a_change():
    """A period-over-period change computes over two windows; both must surface, or a binding check
    on the later window would miss the earlier one."""
    this = Spec.governed("active_users", period="last_week")
    prior = Spec.governed("active_users", period="prev_week")
    change = Spec.derived("difference", inputs=[this, prior])
    assert periods(change) == {"last_week", "prev_week"}


# ── bind_scope: the segment component (the web-growth / paid-search class) ───────────────────────
def test_segment_bound_when_the_spec_applies_it():
    """The question restricts to web and the spec filters to web -> nothing unbound."""
    scope = Scope(measure="active users", segments=(("activity__platform", "web"),))
    spec = Spec.governed("active_users", filters=[("activity__platform", "web")])
    assert bind_scope(scope, spec) == ()


def test_segment_unbound_when_the_spec_drops_it():
    """The question restricts to web but the spec applies no such filter -> the silent-drop this
    catches (active_users served as the all-platform total, labelled 'web')."""
    scope = Scope(measure="active users", segments=(("activity__platform", "web"),))
    spec = Spec.governed("active_users")            # no filter
    unbound = bind_scope(scope, spec)
    assert unbound == (("segment", "activity__platform=web"),)


def test_segment_matches_by_leaf_and_is_case_insensitive():
    """`activity__platform` and `platform`, 'Web' and 'web', are one thing — the same normalisation
    applied_segment uses, so scope and spec agree on what a segment is."""
    scope = Scope(segments=(("platform", "Web"),))
    spec = Spec.governed("active_users", filters=[("activity__platform", "web")])
    assert bind_scope(scope, spec) == ()


def test_segment_bound_through_a_derived_input():
    """cost-per-signup on web: the filter sits on the ratio's numerator, and that binds the scope's
    'web' for the whole derived measure."""
    scope = Scope(measure="spend per signup", segments=(("activity__platform", "web"),))
    num = Spec.governed("marketing_spend", filters=[("activity__platform", "web")])
    ratio = Spec.derived("ratio", inputs=[num, Spec.governed("new_signups")])
    assert bind_scope(scope, ratio) == ()


# ── bind_scope: the period component (the MRR-this-year / gross-mrr-ytd class) ──────────────────
def test_period_bound_and_unbound():
    """The question names a window; the spec must compute over it. 'this year' served as January is
    the drop this catches — a spec period that differs from the scope's is unbound."""
    scope = Scope(measure="gross mrr", period="2026")
    assert bind_scope(scope, Spec.governed("gross_mrr", period="2026")) == ()
    assert bind_scope(scope, Spec.governed("gross_mrr", period="2026-01")) == (("period", "2026"),)


def test_period_bound_through_a_derived_input():
    """A derived spec whose inputs carry the period binds the scope's period without the wrapper
    repeating it."""
    scope = Scope(measure="active users growth", period="last_week")
    change = Spec.derived("difference",
                          inputs=[Spec.governed("active_users", period="last_week"),
                                  Spec.governed("active_users", period="prev_week")])
    assert bind_scope(scope, change) == ()


# ── bind_scope: the qualifier component (definitional constraints) ──────────────────────────────
def test_qualifier_unbound_unless_the_spec_addresses_it():
    """A definitional constraint the question states ('including refunds') must be acknowledged by the
    spec, or it is unbound. This is COMPLETENESS — the spec claims it handled it; whether it handled
    it correctly is the adversary's, not this check's."""
    scope = Scope(measure="mrr", qualifiers=("including refunds",))
    assert bind_scope(scope, Spec.governed("gross_mrr")) == (("qualifier", "including refunds"),)
    assert bind_scope(scope, Spec.governed("gross_mrr", addressed=("including refunds",))) == ()


# ── bind_scope: multiple components, and full coverage ──────────────────────────────────────────
def test_reports_every_unbound_component():
    """A spec that drops several components reports all of them, so one hand-back names the whole gap
    rather than surfacing them one round trip at a time."""
    scope = Scope(measure="spend per signup",
                  segments=(("activity__platform", "web"),),
                  period="2026-Q2",
                  qualifiers=("real acquisition channels only",))
    spec = Spec.derived("ratio", inputs=[Spec.governed("marketing_spend"), Spec.governed("new_signups")])
    kinds = {k for k, _ in bind_scope(scope, spec)}
    assert kinds == {"segment", "period", "qualifier"}


def test_fully_bound_scope_is_empty():
    """Every component present -> nothing unbound -> the spec is complete against the question."""
    scope = Scope(measure="spend per signup",
                  segments=(("activity__platform", "web"),), period="2026-Q2",
                  qualifiers=("real acquisition channels only",))
    num = Spec.governed("acquisition_spend", filters=[("activity__platform", "web")], period="2026-Q2",
                      addressed=("real acquisition channels only",))
    den = Spec.governed("new_signups", filters=[("activity__platform", "web")], period="2026-Q2")
    ratio = Spec.derived("ratio", inputs=[num, den], period="2026-Q2")
    assert bind_scope(scope, ratio) == ()


def test_empty_scope_binds_against_anything():
    """A question naming no segment, period or qualifier (a bare governed measure) leaves nothing to
    bind, whatever the spec is — the check never invents a requirement the question did not state."""
    assert bind_scope(Scope(measure="active users"), Spec.governed("active_users")) == ()
    assert bind_scope(Scope(), Spec.raw(sql="select 1", definition="x")) == ()


# ── ground: the spec against the closed-world graph ─────────────────────────────────────────────
def test_ground_metric_spec():
    """A governed metric spec grounds as instrumented; a metric the graph lacks is uninstrumented —
    a spec cannot claim a metric the warehouse does not define."""
    assert ground(Spec.governed("active_users"), _ONT)[0] == "instrumented"
    assert ground(Spec.governed("retention"), _ONT)[0] == "uninstrumented"


def test_ground_query_spec_computable_when_parts_exist_and_join():
    """An ad-hoc query over a real measure of a real entity grounds as computable — the same
    existence+join check retention rests on."""
    spec = Spec.query(source="activity", measure="value_moments", agg="sum",
                      filters=[("user__channel", "organic")])
    assert ground(spec, _ONT)[0] == "computable"


def test_ground_query_spec_uninstrumented_when_a_part_is_absent():
    """A query naming a column the graph does not hold is uninstrumented, not computable — the spec
    is refused rather than believed."""
    spec = Spec.query(source="activity", measure="duration", agg="sum")   # no such column
    assert ground(spec, _ONT)[0] == "uninstrumented"


def test_ground_query_spec_uninstrumented_when_entities_do_not_join():
    """A query whose filter dimension lives on an entity that cannot be joined to the source is
    uninstrumented — the joinability guard a node-only check would miss."""
    spec = Spec.query(source="spend", measure="spend", agg="sum",
                      filters=[("user__channel", "organic")])   # spend is an island; user won't join
    assert ground(spec, _ONT)[0] == "uninstrumented"


def test_ground_derived_spec_instrumented_when_all_inputs_governed():
    """A ratio of two governed metrics is itself instrumented — the derived value grounds iff its
    parts do, and both parts here are governed."""
    ratio = Spec.derived("ratio", inputs=[Spec.governed("active_users"), Spec.governed("new_signups")])
    assert ground(ratio, _ONT)[0] == "instrumented"


def test_ground_derived_spec_fails_when_an_input_is_ungrounded():
    """One ungrounded input makes the whole derived value uninstrumented — a composition cannot be
    stronger than its weakest part."""
    ratio = Spec.derived("ratio", inputs=[Spec.governed("active_users"), Spec.governed("no_such_metric")])
    assert ground(ratio, _ONT)[0] == "uninstrumented"


def test_ground_derived_spec_with_no_inputs_is_uninstrumented():
    """A derived spec with nothing to combine grounds to nothing — a malformed spec is refused, not
    silently passed."""
    assert ground(Spec.derived("ratio", inputs=[]), _ONT)[0] == "uninstrumented"


def test_ground_raw_spec_is_raw():
    """Bespoke SQL the graph cannot decompose is named `raw` — grounded by disclosure and the
    adversary, not forced to a graph verdict it cannot earn."""
    assert ground(Spec.raw(sql="select 1", definition="x"), _ONT)[0] == "raw"


# ── coherent: reject an invalid definition before it computes ───────────────────────────────────
def test_coherent_accepts_well_formed_specs():
    """A governed metric, a well-formed query, and a ratio of metrics are all valid definitions —
    coherence must not false-flag the normal cases."""
    assert coherent(Spec.governed("active_users")) == ()
    assert coherent(Spec.query(source="activity", measure="value_moments", agg="sum")) == ()
    assert coherent(Spec.derived("ratio", inputs=[Spec.governed("marketing_spend"),
                                                  Spec.governed("new_signups")])) == ()


def test_coherent_flags_structural_holes():
    """A spec missing its load-bearing parts is not a definition — caught here, not as a cryptic
    engine error at execution."""
    assert coherent(Spec.query(source="", measure="", agg="sum"))          # no source/measure
    assert coherent(Spec.query(source="activity", measure="x", agg="totalize"))  # bad agg
    assert coherent(Spec.derived("blend", inputs=[Spec.governed("a")]))      # bad op
    assert coherent(Spec.derived("ratio", inputs=[]))                      # no inputs
    assert coherent(Spec.raw(sql="select 1", definition=""))               # raw needs a definition


def test_coherent_rejects_summing_a_semi_additive_across_periods():
    """Distinct counts do not add over time — someone active in both weeks is counted twice. A SUM of
    a count_distinct query across two periods is the Kimball trap, rejected before it computes."""
    wk1 = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W1")
    wk2 = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W2")
    viol = coherent(Spec.derived("sum", inputs=[wk1, wk2]))
    assert any(k == "additivity" for k, _ in viol)


def test_coherent_allows_a_change_of_a_semi_additive_across_periods():
    """A DIFFERENCE of a semi-additive across periods is a period-over-period change, computed at each
    period's own grain — valid, and must NOT be flagged (this is active_users_growth's shape)."""
    wk1 = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W1")
    wk2 = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W2")
    assert coherent(Spec.derived("difference", inputs=[wk2, wk1])) == ()


def test_coherent_allows_summing_a_semi_additive_within_one_period():
    """Summing across a segment WITHIN one period is fine — the trap is summing across TIME, so a
    single-period sum of a semi-additive is not flagged."""
    a = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W1")
    b = Spec.query(source="activity", measure="user_id", agg="count_distinct", period="2026-W1")
    add = [k for k, _ in coherent(Spec.derived("sum", inputs=[a, b])) if k == "additivity"]
    assert add == []


def test_raw_declared_filter_needs_sql_evidence():
    """A raw spec's SQL runs verbatim, so a declared filter is only a claim. It binds when the SQL
    shows the value or the leaf column; declared-with-no-trace routes to unbound, and the authoring
    loop asks for it inside the SQL. This closes the one unverified input to bind_scope."""
    scope = Scope(measure="retention", segments=(("user__channel", "paid_search"),))
    honest = Spec.raw("SELECT ... WHERE u.channel = 'paid_search'", "retention by channel",
                      filters=[("user__channel", "paid_search")])
    assert bind_scope(scope, honest) == ()
    claimed = Spec.raw("SELECT count(*) FROM user u", "retention",
                       filters=[("user__channel", "paid_search")])
    assert ("segment", "user__channel=paid_search") in bind_scope(scope, claimed)


def test_raw_declared_filter_scan_confirms_never_refutes():
    """The scan accepts the leaf column alone — expression shapes (CASE, IN-lists, joins) mention
    the column without the exact literal, and a correct SQL must never be rejected here."""
    scope = Scope(measure="retention", segments=(("user__channel", "paid_search"),))
    by_column = Spec.raw("SELECT ... WHERE channel IN ('paid_search','paid_social')", "x",
                         filters=[("user__channel", "paid_search")])
    assert bind_scope(scope, by_column) == ()


def test_raw_declared_period_needs_date_evidence():
    """Same reasoning for the period: declared '2026-Q1' with no date constraint in the SQL is a
    silent whole-history figure. Any year the period names counts as evidence — loose on purpose,
    because date arithmetic takes many shapes."""
    scope = Scope(measure="signup share", period="2026-Q1")
    dated = Spec.raw("... WHERE signup_date >= '2026-01-01' AND signup_date < '2026-04-01'", "x",
                     period="2026-Q1")
    assert bind_scope(scope, dated) == ()
    undated = Spec.raw("SELECT count(*) FROM user", "x", period="2026-Q1")
    assert ("period", "2026-Q1") in bind_scope(scope, undated)


def test_metric_declared_filter_still_binds_without_sql():
    """The scan is raw-only: a metric spec's filters compile into the engine query, so the
    declaration IS the application and no SQL evidence exists to ask for."""
    scope = Scope(measure="spend", segments=(("user__channel", "paid_search"),))
    spec = Spec.governed("marketing_spend", filters=[("user__channel", "paid_search")])
    assert bind_scope(scope, spec) == ()


def test_derived_period_pushes_into_inputs():
    """A period declared on a ratio means: on every input. bind_scope passed the declaration
    (periods() gathers across the tree) while the executor computed each input as its leaf declared
    — so a Q1 ratio served the whole-history figure, matching all-time spend/signups to six decimal
    places. Push-down at construction makes the declared window the executed one."""
    ratio = Spec.derived("ratio",
                         inputs=[Spec.governed("marketing_spend"), Spec.governed("new_signups")],
                         period="2026-Q1")
    assert all(s.period == "2026-Q1" for s in ratio.inputs)


def test_derived_input_period_wins_over_the_top():
    """A period-over-period difference declares one window per input; the top-level period (if any)
    must not overwrite them, or every change-metric collapses to one window minus itself."""
    change = Spec.derived("difference",
                          inputs=[Spec.governed("active_users", period="last_week"),
                                  Spec.governed("active_users", period="prev_week")],
                          period="last_week")
    assert [s.period for s in change.inputs] == ["last_week", "prev_week"]


def test_derived_filter_pushes_into_inputs():
    """Same rule for filters: 'web' on a ratio filters both parts; an input's own filters stand."""
    ratio = Spec.derived("ratio",
                         inputs=[Spec.governed("marketing_spend"),
                                 Spec.governed("new_signups", filters=[("user__channel", "paid")])],
                         filters=[("activity__platform", "web")])
    assert ratio.inputs[0].filters == (("activity__platform", "web"),)
    assert ratio.inputs[1].filters == (("user__channel", "paid"),)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(tests)} passed")
