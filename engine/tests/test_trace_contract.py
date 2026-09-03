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
    assert "match none" in r.content


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
    """The inversion floor, with REALISTIC operands: after a forced swap the match has
    served==named, so served_value and named_value are the SAME figure — the first pin passed
    those two as different numbers and blessed a floor that never fired in production. The
    figure the reader must also hold is the OTHER side's, passed explicitly."""
    obj = _stub()
    obj.repairs = [{"binding_mismatch": {"named": "active_users", "served": "active_accounts",
                                         "quote": "q"}}]
    exit_call = NS(name="answer", args={"answer": "1683", "explanation": ""})
    assert obj._binding_gate(exit_call, "active_accounts", "active_accounts",
                             "not counting staff", "is_internal", 1683.0, 1683.0,
                             other_value=1620.0) is None
    assert "1620" in exit_call.args["answer"]              # the swapped-away reading appended
    # no prior swap -> no append
    obj2 = _stub()
    exit_call = NS(name="answer", args={"answer": "1683", "explanation": ""})
    assert obj2._binding_gate(exit_call, "active_accounts", "active_accounts", "q", "d",
                              1683.0, 1683.0, other_value=1620.0) is None
    assert exit_call.args["answer"] == "1683"


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


def test_the_cluster_stand_down_logs_its_act(monkeypatch):
    """The contested-cluster short-circuit (a served figure that IS a queried cluster reading is
    the binding check's jurisdiction, not this gate's) was the one silent stand-down — and its
    first logged act crashed live with TypeError: rivals are Competitor objects, not strings.
    A scrutiny probe found both; this pins them."""
    import agent.gates.measure as gm

    class _Competitor:
        def __init__(self, name):
            self.name = name

    class _Clusters:
        def competitors(self, metric):
            return (_Competitor("acquisition_spend"),) if metric == "marketing_spend" else ()

    obj = _stub()
    obj.grounding = NS(semantic=NS(clusters=_Clusters()), guardrails=NS(grounded_measure=True))
    obj.model = None
    obj.question = "How much did we spend on referral marketing in March 2026?"
    obj.steps = [{"tool": "query_metric",
                  "args": {"metric": "marketing_spend", "filters": {"spend_row__channel": "referral"},
                           "period": "2026-03"}}]
    obj.acts = []
    monkeypatch.setattr(gm.before, "value_of", lambda sem, args, m: {"value": 1858.95})
    exit_call = NS(name="answer",
                   args={"answer": "1858.95", "explanation": "referral marketing spend, March 2026"})
    assert obj.substituted_measure(exit_call) is None
    acts = [a for a in obj.acts if a["guardrail"] == "grounded_measure"]
    assert len(acts) == 1 and acts[0]["outcome"] == "allowed"
    assert "acquisition_spend" in acts[0]["detail"]


def test_the_scope_record_is_the_premise_and_the_judge_is_retired(monkeypatch):
    """REPLACE (tier 4 wrap): with a record, the record IS the premise and the live judge is
    never called — measured through the GUARD phase (44-45/46 shadow agreement, both investigated
    disagreements resolved in the record's favour, one certified silent caught). Off means off:
    without the flag the live judge still owns the path, so archived cells keep their meaning."""
    import agent.gates.contract as gc

    def _stub_run(flag):
        obj = _stub()
        obj.grounding = NS(semantic=NS(clusters=None),
                           toolbox=NS(g=NS(scope_premise=flag)),
                           guardrails=NS(answer_spec=True))
        obj.model = None
        obj._premise = None
        obj.question = "Why did new signups collapse in the second quarter of 2026?"
        obj.acts = []
        obj.scope_shadow = {"presupposes": {"kind": "direction", "claim": "fell",
                                            "quote": "new signups collapse"}}
        return obj

    calls = []

    def _judge(m, q):
        calls.append(q)
        return {"type": "none", "claim": "", "quote": ""}

    monkeypatch.setattr(gc._classify, "question_presupposes", _judge)
    on = _stub_run(True)
    rec = gc.presupposition(on)
    assert rec["type"] == "direction" and rec["claim"] == "fell"
    assert calls == []                      # the judge is retired from the record path
    assert any("scope record" in a["detail"] for a in on.acts)
    off = _stub_run(False)
    assert gc.presupposition(off)["type"] == "none" and off.acts == []
    assert len(calls) == 1                  # without the flag the live judge still owns the path


def _chose_stub(flag, qualifiers, monkeypatch, judge):
    import agent.gates.disclosure as gd

    obj = _stub()
    obj.grounding = NS(semantic=None, guardrails=NS(scope_chose=flag, scope_classifier=True))
    obj.model = None
    obj.question = "What did it cost us in marketing for each person who signed up in Q1?"
    obj._scope_verdict = None
    obj.acts = []
    obj.scope_shadow = {"qualifiers": qualifiers}
    obj._describe = lambda m: ""
    monkeypatch.setattr(gd._classify, "question_chose_scope", judge)
    rival = NS(name="acquisition_spend", discriminator="channel <> 'partnerships'")
    return obj, gd, [("marketing_spend", rival, {"v": 1.0}, {"v": 2.0}, {"v": 1.0})]


def test_no_qualifier_spans_means_no_chose_and_no_judge_call(monkeypatch):
    """The chose license (tier 4): with a scope record and no qualifier spans, nothing in the
    question could have chosen a reading — the verdict is decided without a judge call, which is
    the spend-per-signup flake surface ('marketing for each person' licensed a silent single
    reading) removed rather than guarded."""
    def _forbidden(*a, **k):
        raise AssertionError("the judge must not be called when no span could license a chose")

    obj, gd, missing = _chose_stub(True, [], monkeypatch, _forbidden)
    assert gd._request_chose(obj, missing) is False
    assert any("no qualifier spans" in a["detail"] for a in obj.acts)


def _anchor_stub(obj):
    """The REPLACE path needs a semantic with a vocabulary; the anchor itself is monkeypatched —
    these pins hold the WIRING (anchor decides / anchor silent), member_anchor has its own."""
    obj.grounding = NS(semantic=NS(metric_filters=lambda m: (),
                                   segment_vocabulary=lambda: {"channel": ("partnerships",)}),
                       guardrails=NS(scope_chose=True, scope_classifier=True))
    return obj


def test_with_a_record_the_anchor_decides_and_the_judge_is_never_called(monkeypatch):
    """REPLACE (tier 4 wrap): qualifier spans + member anchor decide chose with zero model calls;
    the judge survives only for cells without a record."""
    def _forbidden(*a, **k):
        raise AssertionError("the chose judge is retired from the record path")

    obj, gd, missing = _chose_stub(
        True, ["including the partnerships integration"], monkeypatch, _forbidden)
    _anchor_stub(obj)
    monkeypatch.setattr(gd, "member_anchor",
                        lambda span, m, r, f, v: ("marketing_spend", "test-anchor"))
    assert gd._request_chose(obj, missing) is True
    assert obj._scope_verdict[1] == "marketing_spend"
    assert any("no judge call" in a["detail"] for a in obj.acts)


def test_an_anchor_silent_span_forces_disclosure_not_a_judge_call(monkeypatch):
    """Where member membership cannot decide the side, the verdict is False and the disclosure
    machinery supplies both figures — widening, never a fall back to the judge."""
    def _forbidden(*a, **k):
        raise AssertionError("the chose judge is retired from the record path")

    obj, gd, missing = _chose_stub(
        True, ["counting terms later refunded"], monkeypatch, _forbidden)
    _anchor_stub(obj)
    monkeypatch.setattr(gd, "member_anchor", lambda span, m, r, f, v: ("", "no member evidence"))
    assert gd._request_chose(obj, missing) is False
    assert any("disclosure required" in a["detail"] for a in obj.acts)


def test_the_chose_license_is_dead_without_its_flag(monkeypatch):
    """Off means off — the shadow cell's observational contract, and byte-identical live
    behaviour for every stored row from before the flag existed."""
    obj, gd, missing = _chose_stub(
        False, [], monkeypatch,
        lambda *a, **k: (True, "marketing_spend", "marketing for each person"))
    assert gd._request_chose(obj, missing) is True


def _refusal_stub(flag, reason, held):
    import agent.gates.measure as gm

    obj = _stub()
    obj.grounding = NS(semantic=None, guardrails=NS(computed_refusal=flag))
    obj.steps = ([{"tool": "define_measure", "result":
                   "[r2] COMPUTED (tier=raw). ...\nvalue = 294\nDEFINITION: count of DE signups"}]
                 if held else [])
    obj.repairs, obj.acts = [], []
    exit_call = NS(name="refuse", args={"reason": reason, "explanation": "x"})
    return obj, gm, exit_call


def test_a_junk_reason_refusal_over_a_computed_answer_is_handed_back():
    """Three A/B rows: define COMPUTED the correct value and the model refused with an invented
    reason (dimension_not_supported / segment_undefined / other) — the answer existed and was
    discarded. One bounded hand-back: serve it, or name the policy."""
    obj, gm, exit_call = _refusal_stub(True, "dimension_not_supported", held=True)
    r = gm.computed_refusal(obj, exit_call)
    assert r is not None and r.is_error and "COMPUTED" in r.content
    assert any(a["guardrail"] == "computed_refusal" for a in obj.acts)


def test_a_policy_reason_refusal_stands_even_over_a_computed_answer():
    """no_governed_definition IS the strict policy for a computed figure; coverage and premise
    reasons override a computation. The gate polices junk reasons, never policies."""
    obj, gm, exit_call = _refusal_stub(True, "no_governed_definition", held=True)
    assert gm.computed_refusal(obj, exit_call) is None


def test_uninstrumented_over_a_computed_answer_is_rewritten_not_handed_back():
    """A COMPUTED result is constructive proof the data is captured, so the correct refusal code
    is KNOWN — the gate constructs the rewrite (free) rather than spending a round trip: its
    first live firing arrived at an exhausted budget and the false reason survived."""
    obj, gm, exit_call = _refusal_stub(True, "uninstrumented", held=True)
    assert gm.computed_refusal(obj, exit_call) is None
    assert exit_call.args["reason"] == "no_governed_definition"
    assert any(a["outcome"] == "constructed" for a in obj.acts)


def test_no_computed_answer_means_no_computed_refusal_check():
    obj, gm, exit_call = _refusal_stub(True, "dimension_not_supported", held=False)
    assert gm.computed_refusal(obj, exit_call) is None


def test_computed_refusal_is_dead_without_its_flag():
    obj, gm, exit_call = _refusal_stub(False, "dimension_not_supported", held=True)
    assert gm.computed_refusal(obj, exit_call) is None


def test_entry_mappings_license_the_records_spans_deterministically():
    """scope_segments: the record's segment spans licensed at question entry, zero model calls.
    'from Germany' rides the description synonym ('DE (Germany)'); an unlicensed span is said to
    match nothing rather than dropped — the agent decides what that means, with the fact in hand."""
    import agent.gates.segments as gs

    sem = NS(segment_vocabulary=lambda: {"activity__country": ("US", "DE", "FR")},
             dimension_descriptions=lambda: {
                 "activity__country": "The account country, as an ISO code: US (the United "
                                      "States); DE (Germany); FR (France)."})
    notes = gs.entry_mappings({"segments": ["from Germany"]}, sem)
    assert "activity__country" in notes and "'DE'" in notes
    none = gs.entry_mappings({"segments": ["on Instagram ads"]}, sem)
    assert "no governed member" in none
    assert gs.entry_mappings({"segments": []}, sem) == ""
    assert gs.entry_mappings(None, sem) == ""


def test_the_reachability_bounce_removes_the_metric_kind_from_the_retry():
    """Protocol, not advice: the author stayed on kind='metric' through a reachability bounce
    that named the raw route in words, about half the time. After that bounce the retry's action
    space no longer offers the kind at all."""
    import agent.runtime.define as rd

    captured = {}

    class _Model:
        def respond(self, convo, tools, force_tool=None, temperature=None):
            captured["kinds"] = tools[0]["input_schema"]["properties"]["spec"]["properties"]["kind"]["enum"]
            return NS(tool_calls=[])

    rd._author(_Model(), "q", "ont", "wh", "feedback", banned_kinds=frozenset({"metric"}))
    assert "metric" not in captured["kinds"] and "raw" in captured["kinds"]
    rd._author(_Model(), "q", "ont", "wh", "")
    assert "metric" in captured["kinds"]          # no ban, full action space
    # the pristine module-level schema must never be mutated by a banned retry
    assert "metric" in rd._DEFINE_TOOL["input_schema"]["properties"]["spec"]["properties"]["kind"]["enum"]


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


# ── B2: derivability is the READER's contract ─────────────────────────────────────────────────
def test_fabricated_prose_figures_are_caught_even_with_no_typed_value():
    """The frozen suite served "fell by 39%, from 1,039 to 636" (truth 637 -> 1,214) with the
    value slot empty — the slot-only check stood down. The answer FIELD is what the reader
    receives, so its numbers are the checked set."""
    obj = _stub([_step([637], args={"metric": "new_signups", "period": "2026-Q1"}),
                 _step([1214], args={"metric": "new_signups", "period": "2026-Q2"})])
    exit_call = NS(name="answer", args={
        "answer": "New signups fell by 39% (from 1,039 in Q1 to 636 in Q2)",
        "value": None, "explanation": ""})
    r = obj.underived_figure(exit_call)
    assert r is not None and r.is_error
    assert "1039" in r.content and "39" in r.content
    # 636 is NOT flagged, deliberately: it sits within the 0.5% slack of the true 637 — inside
    # the suite's own grading tolerance, where "wrong" is not a category. The gate polices
    # fabrication beyond the materiality line, not rounding.
    assert "636.0" not in r.content


def test_legitimate_derivations_pass_including_percent_renderings():
    obj = _stub([_step([637]), _step([1214])])
    exit_call = NS(name="answer", args={
        "answer": "They rose to 1,214 from 637 in Q1 2026 — a rise of 577 (+90.6%)",
        "value": 577, "explanation": ""})
    assert obj.underived_figure(exit_call) is None       # 577=diff, 90.6=(577/637)*100, dates masked


def test_a_figure_echoed_from_a_mechanism_written_result_line_is_derived():
    """The [also]/[premise] lines put figures in front of the model as result TEXT, not typed
    values; a model that copies one has derived it from the run, not from its head."""
    step = _step([947], args={"metric": "value_moments"})
    step["result"] = "value 947\n[also] total_value_moments gives 1131 here, 19% apart"
    obj = _stub([step])
    exit_call = NS(name="answer", args={"answer": "947 (or 1,131 including internal)",
                                        "value": 947, "explanation": ""})
    assert obj.underived_figure(exit_call) is None


def test_a_stated_total_of_a_breakdown_derives_but_an_arbitrary_missum_does_not():
    cells = [195.0, 202.0, 240.0]
    obj = _stub([_step(cells, args={"metric": "new_signups"})])
    obj.grounding = NS(semantic=NS(clusters=None, additivity=lambda m: "additive"),
                       guardrails=NS(answer_spec=True))
    ok = NS(name="answer", args={"answer": "637 total across the quarter", "value": 637,
                                 "explanation": ""})
    assert obj.underived_figure(ok) is None              # sum of the step's own rows
    bad = NS(name="answer", args={"answer": "734 total", "value": 734, "explanation": ""})
    r = obj.underived_figure(bad)
    assert r is not None and r.is_error


def test_explanation_numbers_stay_advisory():
    obj = _stub([_step([100.0])])
    exit_call = NS(name="answer", args={"answer": "100", "value": 100,
                                        "explanation": "context: back in 1999 we had 42 users"})
    assert obj.underived_figure(exit_call) is None


def test_negated_polarity_words_are_not_read_as_inclusion():
    from agent.gates.disclosure import member_anchor

    FILTERS = {"active_users": ("{{ Dimension('activity__is_internal') }} = false",),
               "active_accounts": ()}
    MEMBERS = {"activity__is_internal": ["False", "True"]}
    side, why = member_anchor("not counting staff or test users",
                              "active_users", "active_accounts", FILTERS.get, MEMBERS.get)
    assert side == "active_users", why       # "not counting" is exclusion, whatever it contains


def test_a_semi_additive_step_sum_is_not_derivable():
    obj = _stub([_step([600.0, 610.0, 613.0], args={"metric": "active_users"})])
    obj.grounding = NS(semantic=NS(clusters=None, additivity=lambda m: "semi_additive"),
                       guardrails=NS(answer_spec=True))
    exit_call = NS(name="answer", args={"answer": "1,823", "value": 1823, "explanation": ""})
    r = obj.underived_figure(exit_call)
    assert r is not None and r.is_error      # summing distinct counts is the roll-up error
    # the same sum over an ADDITIVE metric derives
    obj2 = _stub([_step([600.0, 610.0, 613.0], args={"metric": "app_opens"})])
    obj2.grounding = NS(semantic=NS(clusters=None, additivity=lambda m: "additive"),
                        guardrails=NS(answer_spec=True))
    exit_call = NS(name="answer", args={"answer": "1,823", "value": 1823, "explanation": ""})
    assert obj2.underived_figure(exit_call) is None


# ── the member license (Instagram / SEO / Google search) ──────────────────────────────────────
CHANNELS = ["content_seo", "organic", "paid_search", "partnerships", "referral"]
CH_DESC = ("The acquisition channel of the account. content_seo is content marketing and SEO; "
           "organic is organic; paid_search is paid search; partnerships is an internal test "
           "integration; referral is referrals.")


def test_member_licenses_route_serve_contest_refuse():
    from agent.core.members import licenses

    assert licenses("Instagram", CHANNELS, CH_DESC) == []                 # no referent
    assert licenses("SEO", CHANNELS, CH_DESC) == ["content_seo"]          # documentary license
    assert licenses("Google search", CHANNELS, CH_DESC) == ["paid_search"]  # name license
    assert licenses("referrals", CHANNELS, CH_DESC) == ["referral"]
    assert licenses("the spend", CHANNELS, CH_DESC) == []                 # stopwords only
    # the four failure modes the first full-suite exposure found (findings §59):
    assert licenses("organically", CHANNELS, CH_DESC) == ["organic"]      # morphology (stems)
    countries = ["US", "BR", "GB", "DE", "FR", "PH", "ID", "IN"]
    c_desc = ("The account country, as an ISO code: US (the United States); BR (Brazil); GB (the "
              "United Kingdom); DE (Germany); FR (France); PH (the Philippines); ID (Indonesia); "
              "IN (India).")
    assert licenses("Germany", countries, c_desc, "activity__country") == ["DE"]   # declared synonym
    assert licenses("the Philippines", countries, c_desc, "activity__country") == ["PH"]
    # NOT ["IN","PH"]: the code IN sits inside "PhilippINes" — word-boundary clause assignment
    plats = ["android", "ios", "unknown", "web"]
    p_desc = "The registered client platform: android, ios, web, or unknown."
    assert licenses("web platform", plats, p_desc, "activity__platform") == ["web"]
    # NOT all four: 'platform' is a dimension descriptor, suppressed; 'web' selects


def test_the_segment_gate_blocks_an_unlicensed_fold(monkeypatch):
    import agent.gates.segments as gs

    obj = _stub()
    obj.grounding = NS(
        semantic=NS(ontology_text=lambda: "x",
                    segment_vocabulary=lambda: {"spend_row__channel": CHANNELS},
                    dimension_descriptions=lambda: {"spend_row__channel": CH_DESC}),
        guardrails=NS(segment_gate=True))
    obj.model = None
    obj.question = "How much did we spend on Instagram ads in June 2026?"
    obj._scope_verdict = (False, "", "")
    # the resolver reports the model's fold: Instagram mapped onto paid_search
    monkeypatch.setattr(gs._classify, "segment_named",
                        lambda m, q, v: (True, "Instagram", "spend_row__channel", "paid_search"))
    exit_call = NS(name="answer", args={"answer": "12,786.81"})
    r = obj.segment_gate(exit_call)
    assert r is not None and r.is_error
    assert "NO value" in r.content and "ungoverned_dimension_value" in r.content
    # a licensed mapping passes through to the ground_question path untouched
    obj2 = _stub()
    obj2.grounding, obj2.model = obj.grounding, None
    obj2._scope_verdict = (False, "", "")
    obj2.question = "SEO spend in June?"
    monkeypatch.setattr(gs._classify, "segment_named",
                        lambda m, q, v: (True, "SEO", "spend_row__channel", "content_seo"))
    monkeypatch.setattr(gs._classify, "ground_question", lambda m, q, o: (True, "", ""))
    assert obj2.segment_gate(NS(name="answer", args={"answer": "1,858.95"})) is None
