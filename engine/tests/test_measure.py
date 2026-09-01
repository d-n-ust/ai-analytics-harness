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

from agent.measure import Scope, Spec, applied_segments, bind_scope, periods


# ── constructors + the uniform surface ────────────────────────────────────────────────────────
def test_a_governed_metric_is_the_trivial_spec():
    """Governed and ad-hoc must flow through one shape, or the whole design forks. A metric spec with
    no filters covers a scope with no components."""
    spec = Spec.metric("active_users")
    assert spec.kind == "metric" and spec.metric == "active_users"
    assert bind_scope(Scope(measure="active users"), spec) == ()


def test_applied_segments_gathers_across_a_derived_tree():
    """A filter on any input of a derived spec binds the question's segment — 'web' on a ratio's
    numerator is 'web' for the ratio. A per-input filter that did not propagate would read as a drop."""
    num = Spec.metric("marketing_spend", filters=[("activity__platform", "web")])
    den = Spec.metric("new_signups")
    ratio = Spec.derived("ratio", inputs=[num, den])
    assert ("platform", "web") in applied_segments(ratio)


def test_periods_gathers_both_windows_of_a_change():
    """A period-over-period change computes over two windows; both must surface, or a binding check
    on the later window would miss the earlier one."""
    this = Spec.metric("active_users", period="last_week")
    prior = Spec.metric("active_users", period="prev_week")
    change = Spec.derived("difference", inputs=[this, prior])
    assert periods(change) == {"last_week", "prev_week"}


# ── bind_scope: the segment component (the web-growth / paid-search class) ───────────────────────
def test_segment_bound_when_the_spec_applies_it():
    """The question restricts to web and the spec filters to web -> nothing unbound."""
    scope = Scope(measure="active users", segments=(("activity__platform", "web"),))
    spec = Spec.metric("active_users", filters=[("activity__platform", "web")])
    assert bind_scope(scope, spec) == ()


def test_segment_unbound_when_the_spec_drops_it():
    """The question restricts to web but the spec applies no such filter -> the silent-drop this
    catches (active_users served as the all-platform total, labelled 'web')."""
    scope = Scope(measure="active users", segments=(("activity__platform", "web"),))
    spec = Spec.metric("active_users")            # no filter
    unbound = bind_scope(scope, spec)
    assert unbound == (("segment", "activity__platform=web"),)


def test_segment_matches_by_leaf_and_is_case_insensitive():
    """`activity__platform` and `platform`, 'Web' and 'web', are one thing — the same normalisation
    applied_segment uses, so scope and spec agree on what a segment is."""
    scope = Scope(segments=(("platform", "Web"),))
    spec = Spec.metric("active_users", filters=[("activity__platform", "web")])
    assert bind_scope(scope, spec) == ()


def test_segment_bound_through_a_derived_input():
    """cost-per-signup on web: the filter sits on the ratio's numerator, and that binds the scope's
    'web' for the whole derived measure."""
    scope = Scope(measure="spend per signup", segments=(("activity__platform", "web"),))
    num = Spec.metric("marketing_spend", filters=[("activity__platform", "web")])
    ratio = Spec.derived("ratio", inputs=[num, Spec.metric("new_signups")])
    assert bind_scope(scope, ratio) == ()


# ── bind_scope: the period component (the MRR-this-year / gross-mrr-ytd class) ──────────────────
def test_period_bound_and_unbound():
    """The question names a window; the spec must compute over it. 'this year' served as January is
    the drop this catches — a spec period that differs from the scope's is unbound."""
    scope = Scope(measure="gross mrr", period="2026")
    assert bind_scope(scope, Spec.metric("gross_mrr", period="2026")) == ()
    assert bind_scope(scope, Spec.metric("gross_mrr", period="2026-01")) == (("period", "2026"),)


def test_period_bound_through_a_derived_input():
    """A derived spec whose inputs carry the period binds the scope's period without the wrapper
    repeating it."""
    scope = Scope(measure="active users growth", period="last_week")
    change = Spec.derived("difference",
                          inputs=[Spec.metric("active_users", period="last_week"),
                                  Spec.metric("active_users", period="prev_week")])
    assert bind_scope(scope, change) == ()


# ── bind_scope: the qualifier component (definitional constraints) ──────────────────────────────
def test_qualifier_unbound_unless_the_spec_addresses_it():
    """A definitional constraint the question states ('including refunds') must be acknowledged by the
    spec, or it is unbound. This is COMPLETENESS — the spec claims it handled it; whether it handled
    it correctly is the adversary's, not this check's."""
    scope = Scope(measure="mrr", qualifiers=("including refunds",))
    assert bind_scope(scope, Spec.metric("gross_mrr")) == (("qualifier", "including refunds"),)
    assert bind_scope(scope, Spec.metric("gross_mrr", addressed=("including refunds",))) == ()


# ── bind_scope: multiple components, and full coverage ──────────────────────────────────────────
def test_reports_every_unbound_component():
    """A spec that drops several components reports all of them, so one hand-back names the whole gap
    rather than surfacing them one round trip at a time."""
    scope = Scope(measure="spend per signup",
                  segments=(("activity__platform", "web"),),
                  period="2026-Q2",
                  qualifiers=("real acquisition channels only",))
    spec = Spec.derived("ratio", inputs=[Spec.metric("marketing_spend"), Spec.metric("new_signups")])
    kinds = {k for k, _ in bind_scope(scope, spec)}
    assert kinds == {"segment", "period", "qualifier"}


def test_fully_bound_scope_is_empty():
    """Every component present -> nothing unbound -> the spec is complete against the question."""
    scope = Scope(measure="spend per signup",
                  segments=(("activity__platform", "web"),), period="2026-Q2",
                  qualifiers=("real acquisition channels only",))
    num = Spec.metric("acquisition_spend", filters=[("activity__platform", "web")], period="2026-Q2",
                      addressed=("real acquisition channels only",))
    den = Spec.metric("new_signups", filters=[("activity__platform", "web")], period="2026-Q2")
    ratio = Spec.derived("ratio", inputs=[num, den], period="2026-Q2")
    assert bind_scope(scope, ratio) == ()


def test_empty_scope_binds_against_anything():
    """A question naming no segment, period or qualifier (a bare governed measure) leaves nothing to
    bind, whatever the spec is — the check never invents a requirement the question did not state."""
    assert bind_scope(Scope(measure="active users"), Spec.metric("active_users")) == ()
    assert bind_scope(Scope(), Spec.raw(sql="select 1", definition="x")) == ()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(tests)} passed")
