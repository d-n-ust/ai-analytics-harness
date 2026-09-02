"""The trace-contract gates: deterministic pieces pinned without a model or a warehouse.

Each test drives one mechanism from the frozen-suite diagnosis through a stubbed _Run: the
binding equality (question names one reading, another is served), the derivability check (a
headline figure must come from the run's own values), the window-substitution disclosure, and
the hand-back budget that constructions must not consume.
"""
from types import SimpleNamespace as NS

from agent.runtime.loop import _Run
from agent.core.outcomes import *  # noqa: F401,F403  (import side effects none; keeps parity with loop)


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


def test_binding_stands_down_when_served_equals_named_and_constructs_both_at_the_cap():
    obj = _stub()
    exit_call = NS(name="answer", args={"answer": "2754.00", "explanation": ""})
    assert obj._binding_gate(exit_call, "gross_mrr", "gross_mrr", "q", "d", 2754.0, 2754.0) is None
    assert exit_call.args["answer"] == "2754.00"           # clean match: nothing appended
    # burn the budget with prior hand-backs, then the mismatch CONSTRUCTS BOTH READINGS into the
    # ANSWER field — what the reader (and pile-A grading) treats as served
    obj.repairs = [{"a": 1}, {"b": 2}, {"c": 3}]
    exit_call = NS(name="answer", args={"answer": "2685.08", "explanation": ""})
    assert obj._binding_gate(exit_call, "mrr", "gross_mrr", "counting refunded",
                             "gross of refunds", 2685.08, 2754.0) is None
    assert "2754" in exit_call.args["answer"] and "2685" in exit_call.args["answer"]


def test_a_forced_swap_always_leaves_both_figures_with_the_reader():
    """The inversion floor: when a binding hand-back FORCED the swap that produced this match,
    the judgement behind it may have been wrong — so both readings reach the answer field. A
    judge inversion then costs a redundant clause, never a silent number."""
    obj = _stub()
    obj.repairs = [{"binding_mismatch": {"named": "mrr", "served": "gross_mrr", "quote": "q"}}]
    exit_call = NS(name="answer", args={"answer": "2685.08", "explanation": ""})
    assert obj._binding_gate(exit_call, "mrr", "mrr", "counting refunded",
                             "net of refunds", 2685.08, 2685.08) is None   # served==named values equal -> no other
    # distinct values: the OTHER reading must be appended
    obj2 = _stub()
    obj2.repairs = [{"binding_mismatch": {"named": "mrr", "served": "gross_mrr", "quote": "q"}}]
    exit_call = NS(name="answer", args={"answer": "2685.08", "explanation": ""})
    assert obj2._binding_gate(exit_call, "mrr", "mrr", "counting refunded",
                              "net of refunds", 2754.0, 2685.08) is None
    assert "2754" in exit_call.args["answer"]


def test_the_member_anchor_decides_over_predicates_and_stays_silent_on_language():
    """v2 of the anchor: sides decided by parsed predicates evaluated on member vocabularies —
    never by catalogue prose. The decisive property v1 lacked: it DECIDES the mrr pair (both
    descriptions mention refunds, but only one SCOPE contains the refunded member)."""
    from agent.gates.disclosure import member_anchor

    FILTERS = {"mrr": ("{{ Dimension('subscription__status') }} = 'active'",),
               "gross_mrr": ("{{ Dimension('subscription__status') }} != 'canceled'",),
               "marketing_spend": (),
               "acquisition_spend": ("{{ Dimension('spend_row__channel') }} != 'partnerships'",),
               "active_users": ("{{ Dimension('activity__is_internal') }} = false",),
               "active_accounts": ()}
    MEMBERS = {"subscription__status": ["active", "refunded"],
               "spend_row__channel": ["content_seo", "paid_search", "partnerships", "referral"],
               "activity__is_internal": ["False", "True"]}
    fo, mo = FILTERS.get, MEMBERS.get

    # the mrr pair, both polarities — the case v1 could not decide
    side, why = member_anchor("Counting subscriptions that were later refunded",
                              "mrr", "gross_mrr", fo, mo)
    assert side == "gross_mrr", why
    side, _ = member_anchor("Excluding the terms we later refunded", "mrr", "gross_mrr", fo, mo)
    assert side == "mrr"
    # order of the pair must not matter
    side, _ = member_anchor("Counting subscriptions that were later refunded",
                            "gross_mrr", "mrr", fo, mo)
    assert side == "gross_mrr"
    # channel member, both polarities
    side, _ = member_anchor("Including the internal partnerships test integration",
                            "marketing_spend", "acquisition_spend", fo, mo)
    assert side == "marketing_spend"
    side, _ = member_anchor("excluding the partnerships channel",
                            "marketing_spend", "acquisition_spend", fo, mo)
    assert side == "acquisition_spend"
    # boolean dimension, matched through its NAME tokens
    side, _ = member_anchor("counting our internal staff and test accounts as well",
                            "active_users", "active_accounts", fo, mo)
    assert side == "active_accounts"
    side, _ = member_anchor("excluding staff and internal test accounts",
                            "active_users", "active_accounts", fo, mo)
    assert side == "active_users"
    # SILENCE where structure cannot decide — real language stays the judge's
    assert member_anchor("the Finance definition of MRR", "mrr", "gross_mrr", fo, mo)[0] == ""
    assert member_anchor("counting the ones we gave money back to",
                         "mrr", "gross_mrr", fo, mo)[0] == ""          # concept not a member token
    assert member_anchor("counting refunded terms", "mrr", "gross_mrr",
                         lambda m: ("something un-parseable",), mo)[0] == ""


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


# ── the loaded-question contract (B1) ─────────────────────────────────────────────────────────
def _premise_stub(record, pair):
    import agent.gates.contract as gc

    obj = _stub()
    obj.grounding = NS(semantic=NS(clusters=None), guardrails=NS(answer_spec=True))
    obj.model = None
    obj._premise = record
    obj.question = "why did signups collapse?"
    obj._before_after_from_calls = lambda s: pair
    obj._series_from_calls = lambda s: None
    return obj, gc


def test_the_premise_note_constructs_the_correction_into_the_answer():
    obj, gc = _premise_stub({"type": "direction", "claim": "fell", "quote": "collapse"},
                            ("new_signups", 637, 1214))
    exit_call = NS(name="answer", args={"answer": "1,214", "direction": "", "explanation": ""})
    assert gc.premise_note(obj, exit_call) is None            # constructs, never blocks
    a = exit_call.args["answer"]
    assert "presumes" in a and "637" in a and "1214" in a and "rose" in a
    assert obj.repairs[-1]["premise_note"]["constructed"]


def test_the_note_stands_down_when_the_model_took_the_correct_stance():
    obj, gc = _premise_stub({"type": "direction", "claim": "fell", "quote": "collapse"},
                            ("new_signups", 637, 1214))
    exit_call = NS(name="answer", args={"answer": "they rose by 577", "direction": "rose"})
    assert gc.premise_note(obj, exit_call) is None
    assert exit_call.args["answer"] == "they rose by 577"      # nothing appended
    # and a question that asserts nothing has no record to fire from
    obj2, gc = _premise_stub({"type": "none", "claim": "", "quote": ""}, ("m", 1, 2))
    exit_call = NS(name="answer", args={"answer": "42", "direction": ""})
    assert gc.premise_note(obj2, exit_call) is None
    assert exit_call.args["answer"] == "42"


def test_a_stance_free_answer_under_a_contradicted_premise_is_handed_back(monkeypatch):
    import agent.gates.contract as gc

    obj, _ = _premise_stub({"type": "direction", "claim": "fell", "quote": "collapse"},
                           ("new_signups", 637, 1214))
    monkeypatch.setattr(gc, "_true_direction",
                        lambda run, s: ("new_signups", "rose", "637 then 1214", "637->1214"))
    exit_call = NS(name="answer", args={"answer": "1,214", "direction": "not_a_change",
                                        "value": 1214, "explanation": ""})
    r = gc.direction_vs_evidence(obj, exit_call)
    assert r is not None and r.is_error
    assert "PRESUMES" in r.content and "false_premise" in r.content
