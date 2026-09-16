"""A clarification is followed up, answered from the case, and scored — no model needed.

The wording of the simulated reply and the rule for when to follow up are policy, not behaviour,
so both are proved here rather than observed in a run. A run would only show that something
happened; these show that the right thing happens and the wrong things do not.

Run: uv run python -m pytest harness/tests/test_second_turn.py -q     (or run this file directly)
"""

from __future__ import annotations

from agent.core.outcomes import Answer
from evals.second_turn import RESOLVED_CORRECT, RESOLVED_WRONG, UNRESOLVED, follow_up, reply_for

CONTESTED = {
    "id": "c1", "tier": "contested_level",
    "question": "How many active users did we have in October 2025?",
    "expect": {"type": "contested", "tolerance": 0.005, "candidates": [
        {"metric": "active_users", "owner": "Product", "consumer": "the weekly product review",
         "gold_sql": "SELECT 886", "value": 886.0},
        {"metric": "active_accounts", "owner": "Platform", "consumer": "capacity planning",
         "gold_sql": "SELECT 919", "value": 919.0}]}}

ANSWERABLE = {"id": "a1", "tier": "answerable", "question": "How many signups in June?",
              "expect": {"type": "metric_answer", "metric": "new_signups",
                         "gold_sql": "SELECT 42", "tolerance": 0.005}}


def _answer(outcome="clarify", **kw) -> Answer:
    base = dict(question=CONTESTED["question"], rung=3, model="gpt-5-mini",
                answer=None, outcome=outcome)
    return Answer(**{**base, **kw})


def _served(value: float) -> Answer:
    return _answer(outcome="answer", answer=f"{value:,.0f}", declared_value=value,
                   source_metric="active_users", typed_value=True)


def test_the_reply_is_read_off_the_case_and_never_invented():
    """A model-written reply would add a second source of variance to the thing being measured.
    Every part of this one is a field of the case."""
    r = reply_for(CONTESTED)
    assert r is not None
    for part in ("Product", "the weekly product review", "active_users"):
        assert part in r.text, f"the reply does not name {part}, which the case declares"
    assert (r.metric, r.value) == ("active_users", 886.0)


def test_the_first_candidate_is_the_convention():
    """On a genuinely contested question neither reading is 'the' intended one — that is what makes
    it contested — so the choice is arbitrary and must be consistent."""
    assert reply_for(CONTESTED).metric == CONTESTED["expect"]["candidates"][0]["metric"]
    flipped = {**CONTESTED, "expect": {**CONTESTED["expect"],
                                       "candidates": CONTESTED["expect"]["candidates"][::-1]}}
    assert reply_for(flipped).metric == "active_accounts"


def test_nothing_to_follow_up_on_a_case_with_one_answer():
    assert reply_for(ANSWERABLE) is None
    assert follow_up(_answer(), ANSWERABLE, lambda q: _served(42)) is None


def test_an_unresolved_oracle_produces_no_reply():
    """A candidate whose gold never resolved cannot grade an answer, and inventing a target would
    score the second turn against a number nobody computed."""
    unresolved = {**CONTESTED, "expect": {**CONTESTED["expect"], "candidates": [
        {**CONTESTED["expect"]["candidates"][0], "value": None}]}}
    assert reply_for(unresolved) is None


def test_only_a_clarification_is_followed_up():
    """A refusal is a visible decline someone can act on; an answer already ended the episode.
    Re-asking either would price a round trip nobody spent."""
    for outcome in ("answer", "refuse", "error"):
        assert follow_up(_answer(outcome=outcome), CONTESTED, lambda q: _served(886)) is None


def test_the_three_resolutions():
    seen = {}
    for name, second in (
        (RESOLVED_CORRECT, _served(886)),                      # answered the reading it was given
        (RESOLVED_WRONG, _served(919)),                        # answered the OTHER reading
        (UNRESOLVED, _answer(outcome="clarify")),              # asked again
    ):
        rec = follow_up(_answer(), CONTESTED, lambda q, s=second: s)
        seen[name] = rec["resolution"]
        assert rec["resolution"] == name, f"expected {name}, got {rec['resolution']}"
    assert seen[RESOLVED_CORRECT] != seen[RESOLVED_WRONG] != seen[UNRESOLVED]
    # A refusal on the second turn is also nothing bought.
    assert follow_up(_answer(), CONTESTED,
                     lambda q: _answer(outcome="refuse"))["resolution"] == UNRESOLVED


def test_the_question_is_re_asked_with_the_ambiguity_resolved():
    """The engine has no memory by design, so a second turn is the original question with the
    reading stated — which is also what a real user does when asked to be more specific."""
    captured = {}

    def run_one(text):
        captured["asked"] = text
        return _served(886)

    rec = follow_up(_answer(), CONTESTED, run_one)
    assert captured["asked"].startswith(CONTESTED["question"])
    assert "active_users" in captured["asked"]
    assert rec["asked"] == captured["asked"]


def test_the_second_turn_carries_its_own_meter():
    """The row's telemetry stays the first attempt's. Folding them together would make 'what the
    first attempt cost' unrecoverable, and the two price different things."""
    second = Answer(question="q", rung=3, model="gpt-5-mini", answer="886", outcome="answer",
                    declared_value=886.0, input_tokens=4_000, output_tokens=120, model_calls=2)
    rec = follow_up(_answer(), CONTESTED, lambda q: second)
    assert (rec["input_tokens"], rec["output_tokens"], rec["model_calls"]) == (4_000, 120, 2)


if __name__ == "__main__":
    # `bench test` runs each file as a SCRIPT, so a test absent from this block runs nowhere.
    test_the_reply_is_read_off_the_case_and_never_invented()
    test_the_first_candidate_is_the_convention()
    test_nothing_to_follow_up_on_a_case_with_one_answer()
    test_an_unresolved_oracle_produces_no_reply()
    test_only_a_clarification_is_followed_up()
    test_the_three_resolutions()
    test_the_question_is_re_asked_with_the_ambiguity_resolved()
    test_the_second_turn_carries_its_own_meter()
    print("OK — the asker's reply is read off the case, only a clarification is followed up, the "
          "three resolutions separate, and the second turn keeps its own meter.")
