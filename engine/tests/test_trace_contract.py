"""The trace-contract gates: deterministic pieces pinned without a model or a warehouse.

Each test drives one mechanism from the frozen-suite diagnosis through a stubbed _Run: the
binding equality (question names one reading, another is served), the derivability check (a
headline figure must come from the run's own values), the window-substitution disclosure, and
the hand-back budget that constructions must not consume.
"""
from types import SimpleNamespace as NS

from agent.loop import _Run
from agent.outcomes import *  # noqa: F401,F403  (import side effects none; keeps parity with loop)


def _stub(steps=(), guardrails=None):
    obj = _Run.__new__(_Run)
    obj.steps = list(steps)
    obj.grounding = NS(semantic=None,
                       guardrails=guardrails or NS(answer_spec=True, construct_disclosure=True,
                                                   scope_classifier=True))
    obj.repairs, obj.acts = [], []
    return obj


def _step(values, args=None, tool="query_metric", blocked=""):
    return {"tool": tool, "args": args or {}, "result_values": list(values),
            "blocked_by": blocked, "blocked_reason": "past coverage" if blocked else ""}


# ── underived_figure ──────────────────────────────────────────────────────────────────────────
def test_a_figure_matching_no_evidence_or_composition_is_handed_back():
    obj = _stub([_step([19173]), _step([25188])])
    exit_call = NS(name="answer", args={"value": -60015, "explanation": ""})
    r = obj.underived_figure(exit_call)
    assert r is not None and r.is_error
    assert "matches none" in r.content


def test_evidence_values_and_their_compositions_are_accepted():
    obj = _stub([_step([19173]), _step([25188])])
    for ok in (25188, 19173, 6015, -6015, 44361, 25188 / 19173, 60.15):  # 6015/100 = 60.15
        exit_call = NS(name="answer", args={"value": ok, "explanation": ""})
        assert obj.underived_figure(exit_call) is None, ok


def test_a_row_count_is_a_derivable_figure():
    obj = _stub([_step([10.0, 20.0, 70.0])])
    exit_call = NS(name="answer", args={"value": 3, "explanation": ""})
    assert obj.underived_figure(exit_call) is None


# ── substituted_window ────────────────────────────────────────────────────────────────────────
def test_a_served_figure_from_a_different_window_is_disclosed_by_construction():
    steps = [_step([], args={"metric": "new_signups", "period": "last_week"}, blocked="coverage"),
             _step([161], args={"metric": "new_signups", "start": "2026-06-29", "end": "2026-07-05"})]
    obj = _stub(steps)
    exit_call = NS(name="answer", args={"value": 161, "explanation": "signups"})
    assert obj.substituted_window(exit_call) is None            # constructs, never blocks
    expl = exit_call.args["explanation"]
    assert "last_week" in expl and "2026-06-29..2026-07-05" in expl
    assert obj.repairs and obj.repairs[-1]["substituted_window"]["constructed"]


def test_no_blocked_window_means_no_note():
    obj = _stub([_step([161], args={"metric": "new_signups", "period": "2026-06"})])
    exit_call = NS(name="answer", args={"value": 161, "explanation": "x"})
    assert obj.substituted_window(exit_call) is None
    assert exit_call.args["explanation"] == "x"


# ── the hand-back budget ──────────────────────────────────────────────────────────────────────
def test_constructions_do_not_consume_the_correction_budget():
    obj = _stub()
    obj.repairs = [{"undisclosed": ["x"], "constructed": True},
                   {"applied_segment": {"dimension": "d", "value": "v"}, "constructed": True},
                   {"binding_mismatch": {"named": "a", "served": "b", "quote": "q"}}]
    assert obj.claim_retries == 3          # the published count is unchanged
    assert obj.hand_backs == 1             # only the hand-back spends budget


# ── the binding gate ──────────────────────────────────────────────────────────────────────────
def test_binding_hands_back_when_the_served_reading_is_not_the_named_one():
    obj = _stub()
    exit_call = NS(name="answer", args={"explanation": ""})
    r = obj._binding_gate(exit_call, served_name="mrr", named="gross_mrr",
                          quote="counting refunded", discriminator="gross of refunds",
                          served_value=2685.08, named_value=2754.0)
    assert r is not None and r.is_error
    assert "gross_mrr" in r.content and "2754" in r.content
    assert obj.repairs[-1]["binding_mismatch"]["served"] == "mrr"


def test_binding_stands_down_when_served_equals_named_and_constructs_at_the_cap():
    obj = _stub()
    exit_call = NS(name="answer", args={"explanation": ""})
    assert obj._binding_gate(exit_call, "gross_mrr", "gross_mrr", "q", "d", 2754.0, 2754.0) is None
    # burn the budget with prior hand-backs, then the mismatch is CONSTRUCTED, not handed back
    obj.repairs = [{"a": 1}, {"b": 2}, {"c": 3}]
    assert obj._binding_gate(exit_call, "mrr", "gross_mrr", "counting refunded",
                             "gross of refunds", 2685.08, 2754.0) is None
    assert "gross_mrr" in exit_call.args["explanation"]
    assert "2754" in exit_call.args["explanation"]


# ── the scope-quote overlap guard ─────────────────────────────────────────────────────────────
def test_a_segment_phrase_inside_the_consumed_scope_quote_is_not_a_filter(monkeypatch):
    """"Counting subscriptions that were later refunded" chose gross_mrr; the same words must not
    ALSO become status='refunded' — the double read overrode a binding-verified 2,754 with the
    refunded-only slice."""
    import agent.guardrails.classify as classify

    obj = _stub()
    obj.grounding = NS(semantic=NS(segment_vocabulary=lambda: {"subscription__status":
                                                              ("active", "refunded", "canceled")}),
                       guardrails=NS(answer_spec=True))
    obj.model = None
    obj._scope_verdict = (True, "gross_mrr", "Counting subscriptions that were later refunded")
    obj.question = "Counting subscriptions that were later refunded, what is our MRR today?"
    monkeypatch.setattr(classify, "segment_named",
                        lambda *a, **k: (True, "later refunded", "subscription__status", "refunded"))
    assert obj._resolve_segment() is None                      # stood down, not a filter
    assert any(a.get("outcome") == "allowed" for a in obj.acts)
    # the same phrase OUTSIDE any consumed quote still resolves as a segment
    obj2 = _stub()
    obj2.grounding, obj2.model = obj.grounding, None
    obj2._scope_verdict = None
    obj2.question = "How much MRR sits on refunded subscriptions?"
    monkeypatch.setattr(classify, "segment_named",
                        lambda *a, **k: (True, "refunded", "subscription__status", "refunded"))
    seg = obj2._resolve_segment()
    assert seg is not None and seg["linked"]


# ── the sign-claim gate ───────────────────────────────────────────────────────────────────────
def test_a_negative_declared_delta_against_rising_evidence_is_handed_back(monkeypatch):
    obj = _stub()
    obj.grounding = NS(semantic=NS(clusters=None), guardrails=NS(answer_spec=True))
    obj.model = None
    monkeypatch.setattr(_Run, "_true_direction",
                        lambda self, s: ("app_opens", "rose", "19173 then 25188", "19173->25188"))
    monkeypatch.setattr(_Run, "_before_after_from_calls",
                        lambda self, s: ("app_opens", 19173, 25188))
    exit_call = NS(name="answer", args={"value": -6015, "direction": "not_a_change",
                                        "answer": "-6015", "explanation": "rose actually"})
    r = obj.direction_vs_evidence(exit_call)
    assert r is not None and r.is_error and "rise" in r.content
    # a POSITIVE magnitude with falling evidence is the conventional "dropped by N" — left alone
    monkeypatch.setattr(_Run, "_true_direction",
                        lambda self, s: ("app_opens", "fell", "25188 then 19173", "25188->19173"))
    monkeypatch.setattr(_Run, "_before_after_from_calls",
                        lambda self, s: ("app_opens", 25188, 19173))
    monkeypatch.setattr(classify_mod, "text_asserts_direction", lambda m, t: "fell")
    exit_call = NS(name="answer", args={"value": 6015, "direction": "fell",
                                        "answer": "dropped by 6015", "explanation": ""})
    assert obj.direction_vs_evidence(exit_call) is None


import agent.guardrails.classify as classify_mod  # noqa: E402  (used by the sign test)


# ── the pipeline's composition law, held by a test ────────────────────────────────────────────
def test_the_pipeline_orders_supply_verify_construct():
    """A later hand-back must never destroy an earlier construction (findings §53): the phases in
    the pipeline list must be SUPPLY*, then VERIFY*, then CONSTRUCT* — any interleaving is the
    active_users_feb bug waiting to recur."""
    from agent.gates.pipeline import CONSTRUCT, PIPELINE, SUPPLY, VERIFY

    order = {SUPPLY: 0, VERIFY: 1, CONSTRUCT: 2}
    phases = [order[g.phase] for g in PIPELINE]
    assert phases == sorted(phases), [g.name for g in PIPELINE]
    assert len({g.name for g in PIPELINE}) == len(PIPELINE)


# ── the proxy-lean route (the live suite caught an orphaned constant here) ────────────────────
def test_the_proxy_route_serves_with_disclosure_under_the_default_lean(monkeypatch):
    """substituted_measure's proxy branch — reachable only on a live proxy verdict, which is why
    a unit pin exists: the phase-3 extraction orphaned MEASURE_PROXY_LEAN and 4 live rows died
    with AttributeError before this test did their job."""
    import agent.gates.measure as gm

    obj = _stub()
    obj.grounding = NS(semantic=NS(clusters=None), guardrails=NS(grounded_measure=True))
    obj.model = None
    obj.question = "How many reminder notifications were opened?"
    obj.steps = []
    monkeypatch.setattr(gm._classify, "answer_measures_asked",
                        lambda m, q, t: ("proxy", "reminder notifications opened", "app opens"))
    exit_call = NS(name="answer", args={"answer": "42", "explanation": "app opens as a proxy"})
    r = obj.substituted_measure(exit_call)
    assert r is not None and r.is_error            # disclose lean: hand back to disclose the gap
    assert "proxy" in r.content.lower() or "stood in" in r.content.lower() or "related" in r.content.lower()
