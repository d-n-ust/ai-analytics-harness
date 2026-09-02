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
