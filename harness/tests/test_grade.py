"""What counts as a correct response — pure, no run and no model needed.

`grade()` is the thermometer. Everything published is a count of what it decided, so a change
here silently re-scores every stored run. The two rules below were added together because a
sweep exposed the same blind spot twice: the gold set could say "refuse" or "answer", and had
no way to say **"do not guess"** — which is what a genuinely ambiguous question, or a question
asked without the context that defines its terms, actually demands.

Run: PYTHONPATH=. uv run python tests/test_grade.py
"""

from __future__ import annotations

from pathlib import Path

from agent.loop import Answer
from evals.gold import load_questions
from evals.grade import grade

_AMBIGUOUS = {"id": "q", "question": "?", "expect": {"type": "ambiguous",
                                                     "reason": "segment_undefined"}}
_NEEDS_KB = {"id": "q", "question": "?", "requires": ["knowledge"],
             "expect": {"type": "keywords", "keywords": ["days per user"]}}


def _answer(outcome, **kw):
    return Answer(question="?", rung=kw.pop("rung", 7), model="m", answer=kw.pop("answer", None),
                  outcome=outcome, abstained=outcome in ("refuse", "clarify"), **kw)


def test_an_ambiguous_question_accepts_both_declining_and_asking():
    """`adv_whales` asks for MRR on "whale accounts", which nothing defines — not the layer, not
    the knowledge base — and which has two plausible governed readings. Refusing and asking which
    are both the analyst doing the right thing, and 27 attempts split 14 to 11 between them. The
    old refuse-only gold scored the 11 as failures."""
    assert grade(_answer("refuse", reason="segment_undefined"), _AMBIGUOUS, None)["correct"]
    assert grade(_answer("clarify"), _AMBIGUOUS, None)["correct"]
    # a refusal still has to name the right code — the extra allowance is the question, not a pass
    assert not grade(_answer("refuse", reason="out_of_coverage"), _AMBIGUOUS, None)["correct"]
    # and GUESSING is still the failure the case exists to catch
    served = _answer("answer", answer="4820", declared_value=4820.0, typed_value=True)
    assert not grade(served, _AMBIGUOUS, None)["correct"]


def test_a_case_stops_demanding_an_answer_where_its_context_was_never_supplied():
    """Only the knowledge base says "retention" means days per user. Rung 7 is governed-only —
    layer plus tree, NO knowledge base — so at that rung nothing has ever told the agent what the
    word means, and it asked on 19 of 27 attempts. The case scored 4 of 27 and counted every one
    of those as a failure: it was being asked at a rung it does not apply to.

    Where the required context IS supplied, nothing changes — the case still demands the mapping,
    which is the only reason it exists."""
    assert grade(_answer("clarify", rung=7), _NEEDS_KB, None)["correct"]
    assert grade(_answer("refuse", rung=7, reason="no_governed_definition"), _NEEDS_KB,
                 None)["correct"]
    # rung 5 has the knowledge base, so the mapping is demanded again
    assert not grade(_answer("clarify", rung=5), _NEEDS_KB, None)["correct"]
    right = _answer("answer", rung=5, answer="days per user rose to 2.7")
    assert grade(right, _NEEDS_KB, None)["correct"]
    # …and reasoning to the right answer WITHOUT being told still counts, at either rung
    assert grade(_answer("answer", rung=7, answer="days per user rose to 2.7"),
                 _NEEDS_KB, None)["correct"]


def test_the_widening_only_touches_cases_that_declare_it():
    """A rule that quietly relaxed the rest of the set would be worse than the problem it fixes.
    A plain refuse case rejects a clarification at every rung, as it always has."""
    plain = {"id": "q", "question": "?", "expect": {"type": "refuse", "reason": "out_of_coverage"}}
    for rung in (1, 3, 5, 7):
        assert not grade(_answer("clarify", rung=rung), plain, None)["correct"], rung
    assert grade(_answer("refuse", rung=7, reason="out_of_coverage"), plain, None)["correct"]


def test_exactly_which_cases_carry_the_two_new_rules():
    """Pinned by name. Both rules widen what passes, so the set of cases using them is itself a
    published claim — it must change deliberately and visibly, not by someone adding a line."""
    cases = load_questions()
    ambiguous = sorted(c["id"] for c in cases if c["expect"]["type"] == "ambiguous")
    requires = sorted(c["id"] for c in cases if c.get("requires"))
    # Grew from one to three on 2026-08-02. One ambiguous case cannot measure whether the agent
    # asks or guesses, and the bar for the two added is that the READINGS DISAGREE: "healthiest
    # region" is EMEA on volume and Americas on per-user engagement; "best channel" is organic on
    # signups and paid_search on activation. A term with several readings that all give the same
    # answer is not ambiguous, it is just vague.
    assert ambiguous == ["adv_whales", "amb_best_channel", "amb_healthiest_region"], ambiguous
    assert requires == ["t4_business_health", "t4_retention_trend"], requires
    assert len(cases) == 65, len(cases)

    # A THIRD widening, pinned for the same reason: a case may accept more than one refusal code
    # where one defect is truly describable two ways. It is the loosest of the three, so the list
    # of cases using it is the one most worth keeping short — anything here is a case where
    # reason accuracy has stopped discriminating, deliberately.
    multi = sorted(c["id"] for c in cases
                   if not isinstance(c["expect"].get("reason", ""), str))
    assert multi == ["u_july_partial_month"], multi


def test_the_frozen_cases_all_name_their_metric():
    """Naming the metric is the default. A study-local case may opt out with
    `no_governed_metric: true` where the layer genuinely has none, but the frozen set never may:
    selecting the right metric IS the measurement there, and a case that lost its `metric` would
    grade a right number computed from the wrong definition as correct."""
    import yaml
    root = Path(__file__).resolve().parent.parent / "evals" / "cases"
    missing = [f"{path.name}:{case['id']}"
               for path in sorted(root.rglob("*.yml"))
               for case in (yaml.safe_load(path.read_text()) or {}).get("cases", [])
               if case.get("expect", {}).get("type") == "metric_answer"
               and not case["expect"].get("metric")]
    assert not missing, f"frozen metric_answer cases with no metric: {missing}"


if __name__ == "__main__":
    test_the_frozen_cases_all_name_their_metric()
    test_an_ambiguous_question_accepts_both_declining_and_asking()
    test_a_case_stops_demanding_an_answer_where_its_context_was_never_supplied()
    test_the_widening_only_touches_cases_that_declare_it()
    test_exactly_which_cases_carry_the_two_new_rules()
    print("OK — ambiguous cases accept declining or asking, a case without its required context "
          "only insists the agent did not guess, neither rule leaks into the other 54, and every "
          "frozen metric_answer still names its metric.")
