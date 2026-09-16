"""The cost model says what it claims, on rows whose right answer is known in advance.

A utility model checked against a real run can only be checked for plausibility, and a wrong
crossover is entirely plausible-looking. Every arm here is constructed so the crossing can be
worked out by hand and asserted.

Run: uv run python -m pytest harness/tests/test_utility.py -q     (or run this file directly)
"""

from __future__ import annotations

from evals.utility import DEFAULT_MISS, compare, crossover, profile, render


def row(qid, outcome="answer", *, wrong=False, expected="answer", resolution=None,
        usd=0.001, secs=5.0):
    return {"qid": qid, "outcome": outcome, "confident_wrong": wrong, "fabricated": False,
            "off_governance": False, "expected_action": expected, "resolution": resolution,
            "cost_usd": usd, "elapsed_s": secs}


def test_a_perfect_arm_costs_nothing_at_any_price():
    p = profile([row(f"q{i}") for i in range(10)], "perfect")
    assert (p.r_weight, p.fixed) == (0.0, 0.0)
    assert p.cost(0) == p.cost(1000) == 0.0


def test_each_outcome_is_charged_to_the_right_side_of_the_line():
    """The slope carries wrong answers; the intercept carries friction. Getting this backwards
    would make the crossover invert, and every branch is a claim about who pays."""
    cases = {
        "right":            (row("q", "answer"),                                      (0.0, 0.0)),
        "correct refusal":  (row("q", "refuse", expected="refuse"),                   (0.0, 0.0)),
        "silent wrong":     (row("q", "answer", wrong=True),                          (1.0, 0.0)),
        "over-refusal":     (row("q", "refuse", expected="answer"),          (0.0, DEFAULT_MISS)),
        "asked, worked":    (row("q", "clarify", expected="clarify",
                                 resolution="resolved_correct"),                      (0.0, 1.0)),
        "asked, wrong":     (row("q", "clarify", expected="clarify",
                                 resolution="resolved_wrong"),                        (1.0, 1.0)),
        "asked, unresolved": (row("q", "clarify", expected="clarify",
                                  resolution="unresolved"),          (0.0, 1.0 + DEFAULT_MISS)),
        "asked, no follow-up": (row("q", "clarify", expected="clarify"),              (0.0, 1.0)),
    }
    for name, (r, want) in cases.items():
        p = profile([r], name)
        assert (p.r_weight, p.fixed) == want, f"{name}: charged {(p.r_weight, p.fixed)}, want {want}"


def test_an_unfollowed_clarification_is_flagged_because_it_understates_cost():
    """A run without the second turn cannot tell a clarification that worked from one that did
    not, so it charges only the round trip. That biases toward arms that ask, which is the bias
    second_turn.py exists to remove — so it is flagged rather than silently absorbed."""
    silent = profile([row("q1", "clarify", expected="clarify")], "no follow-up")
    assert not silent.followed_up
    assert "clarifications not followed up" in render([silent])

    done = profile([row("q1", "clarify", expected="clarify", resolution="resolved_correct")], "ok")
    assert done.followed_up


def test_the_crossover_is_where_two_lines_meet():
    """A gate that never serves a wrong number but interrupts half the suite, against a disclosure
    that never interrupts but is wrong one time in ten. Cost lines: gate = 0.5, disclose = 0.1r.
    They meet at r = 5."""
    gate = [row(f"q{i}", "clarify", expected="clarify", resolution="resolved_correct")
            for i in range(5)] + [row(f"q{i}") for i in range(5, 10)]
    disclose = [row("q0", wrong=True)] + [row(f"q{i}") for i in range(1, 10)]

    pg, pd = profile(gate, "gate"), profile(disclose, "disclose")
    assert (pg.r_weight, pg.fixed) == (0.0, 0.5)
    assert (pd.r_weight, pd.fixed) == (0.1, 0.0)
    assert abs(crossover(pd, pg) - 5.0) < 1e-9

    c = compare(disclose, gate, name_a="disclose", name_b="gate")
    assert abs(c.r - 5.0) < 1e-9
    assert c.cheaper_below == "disclose", "below the crossing the cheaper answer is to disclose"
    assert c.cheaper_above == "gate", "above it, avoiding a wrong number is worth the interruption"


def test_parallel_arms_never_cross():
    """Same wrong-answer exposure, different friction. No price of a wrong answer separates them,
    and saying so is more useful than reporting a crossing nobody can reach."""
    a = [row("q0", wrong=True)] + [row(f"q{i}") for i in range(1, 10)]
    b = ([row("q0", wrong=True)] + [row("q1", "refuse", expected="answer")]
         + [row(f"q{i}") for i in range(2, 10)])
    assert crossover(profile(a, "a"), profile(b, "b")) is None
    c = compare(a, b, name_a="a", name_b="b")
    assert c.r is None and c.cheaper_below == "a"


def test_a_dominated_arm_reports_no_crossing_rather_than_a_negative_price():
    """Arm b is worse on both terms. They cross only at a negative r, where a wrong answer is
    worth less than nothing, so there is no price anybody would ask about."""
    a = [row(f"q{i}") for i in range(10)]
    b = ([row("q0", wrong=True)]
         + [row("q1", "clarify", expected="clarify", resolution="unresolved")]
         + [row(f"q{i}") for i in range(2, 10)])
    assert crossover(profile(a, "a"), profile(b, "b")) is None


def test_the_interval_comes_from_resampling_questions():
    gate = [row(f"q{i}", "clarify", expected="clarify", resolution="resolved_correct")
            for i in range(10)] + [row(f"q{i}") for i in range(10, 20)]
    disclose = [row(f"q{i}", wrong=True) for i in range(2)] + [row(f"q{i}") for i in range(2, 20)]
    c = compare(disclose, gate, name_a="disclose", name_b="gate")
    assert c.n_questions == 20
    assert c.lo is not None and c.lo <= c.r <= c.hi
    assert compare(disclose, gate, name_a="disclose", name_b="gate").as_dict() == c.as_dict(), \
        "same rows must give the same interval"


def test_money_is_reported_and_not_modelled():
    """Showing that money is not where the cost is is a finding. Folding it into the curve would
    hide it behind a second parameter."""
    p = profile([row(f"q{i}", usd=0.0012, secs=8.2) for i in range(10)], "arm")
    assert abs(p.usd_per_question - 0.0012) < 1e-9
    assert abs(p.seconds_per_question - 8.2) < 1e-9
    # It reaches the table and never the cost line.
    assert "$0.00120" in render([p]) and p.cost(1000) == 0.0


if __name__ == "__main__":
    # `bench test` runs each file as a SCRIPT, so a test absent from this block runs nowhere.
    test_a_perfect_arm_costs_nothing_at_any_price()
    test_each_outcome_is_charged_to_the_right_side_of_the_line()
    test_an_unfollowed_clarification_is_flagged_because_it_understates_cost()
    test_the_crossover_is_where_two_lines_meet()
    test_parallel_arms_never_cross()
    test_a_dominated_arm_reports_no_crossing_rather_than_a_negative_price()
    test_the_interval_comes_from_resampling_questions()
    test_money_is_reported_and_not_modelled()
    print("OK — every outcome is charged to the right side of the line, the crossing is where the "
          "lines meet, parallel and dominated arms report no crossing, and money stays out of it.")
