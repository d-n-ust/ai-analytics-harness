"""`_change_disclosure` supplies a contested change's BOTH readings by construction.

The failure this guards was a silent error: a "by how many did X change from May to June" answer
whose delta was computed in prose (15,329 - 11,640 written as 1,689) and served with only one of two
governed readings. The mechanism computes the delta and the rival's delta from the run's OWN two
windows, so a delta mis-computed in prose is corrected and both readings reach the reader on every
run — the deterministic core the full-suite run exercises only probabilistically.

The one warehouse touchpoint (`before.value_of`) is stubbed with the fixture's real figures; every
other collaborator runs for real.
"""
from types import SimpleNamespace as NS

import agent.loop as loop
from agent.loop import _Run

# value_moments (customer-facing) and total_value_moments (includes internal/test) at the two months.
_VALUES = {
    ("value_moments", "2026-05"): 11640, ("value_moments", "2026-06"): 15329,
    ("total_value_moments", "2026-05"): 12249, ("total_value_moments", "2026-06"): 16041,
}


def _fake_value_of(_sem, args, metric):
    v = _VALUES.get((metric, args.get("period")))
    return {(): v} if v is not None else None


class _Competitor:
    def __init__(self, name, disc):
        self.name, self.discriminator = name, disc


class _Clusters:
    def competitors(self, metric):
        if metric == "value_moments":
            return (_Competitor("total_value_moments", "is_internal = false"),)
        return ()


def _stub(steps):
    obj = _Run.__new__(_Run)        # bypass __init__; we exercise one method
    obj.steps = steps
    obj.grounding = NS(semantic=NS(clusters=_Clusters()),
                       guardrails=NS(construct_disclosure=True, scope_classifier=False))
    obj.repairs, obj.acts = [], []
    return obj


_PAIR = [{"tool": "query_metric", "args": {"metric": "value_moments", "period": "2026-05"}},
         {"tool": "query_metric", "args": {"metric": "value_moments", "period": "2026-06"}}]


def _norm(s):
    return s.replace(",", "")


def test_wrong_prose_delta_is_corrected_and_both_readings_supplied(monkeypatch):
    monkeypatch.setattr(loop.before, "value_of", _fake_value_of)
    obj = _stub(_PAIR)
    # The served answer carries a WRONG delta (1,689) and only one reading.
    exit_call = NS(name="answer",
                   args={"answer": "1,689", "explanation": "15,329 - 11,640 = 1,689"})
    tag, res = obj._change_disclosure(exit_call, obj.grounding.guardrails, [1689, 15329, 11640])
    assert tag == "handled" and res is None            # constructed (augmented) and served
    expl = _norm(exit_call.args["explanation"])
    assert "3689" in expl and "3792" in expl           # both CORRECT governed deltas now present
    assert "is_internal = false" in exit_call.args["explanation"]
    assert obj.repairs and obj.repairs[-1].get("constructed")


def test_stands_down_when_both_deltas_already_disclosed(monkeypatch):
    monkeypatch.setattr(loop.before, "value_of", _fake_value_of)
    obj = _stub(_PAIR)
    exit_call = NS(name="answer", args={"answer": "3,689 and 3,792", "explanation": "both shown"})
    tag, res = obj._change_disclosure(exit_call, obj.grounding.guardrails, [3689, 3792])
    assert tag == "handled" and res is None
    assert exit_call.args["explanation"] == "both shown"   # nothing appended
    assert not obj.repairs


def test_falls_through_when_the_changed_metric_has_no_rival(monkeypatch):
    monkeypatch.setattr(loop.before, "value_of",
                        lambda _s, a, m: {(): 100 if a.get("period") == "2026-05" else 150})
    obj = _stub([{"tool": "query_metric", "args": {"metric": "new_signups", "period": "2026-05"}},
                 {"tool": "query_metric", "args": {"metric": "new_signups", "period": "2026-06"}}])
    exit_call = NS(name="answer", args={"answer": "50", "explanation": ""})
    tag, res = obj._change_disclosure(exit_call, obj.grounding.guardrails, [50])
    assert (tag, res) == ("none", None)                 # not a contested change: fall through
