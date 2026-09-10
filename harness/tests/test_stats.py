"""The statistics say what they claim — proved on constructed data, not on a run.

Every check here builds rows whose right answer is known in advance, because a statistics module
tested against real data can only be checked for plausibility, and plausibility is exactly what a
wrong interval looks like.

Run: uv run python -m pytest harness/tests/test_stats.py -q     (or run this file directly)
"""

from __future__ import annotations

from evals.stats import MIN_DISCORDANT, detectable, interval, paired


def rows(pattern: dict[str, list[bool]], arm: str = "a") -> list[dict]:
    """`{"q1": [True, True, False]}` becomes three rows for q1, one per rep."""
    return [{"qid": q, "rep": i, "correct": ok, "arm": arm}
            for q, oks in pattern.items() for i, ok in enumerate(oks)]


def rate(rs: list[dict]) -> float:
    return sum(r["correct"] for r in rs) / len(rs) if rs else float("nan")


def test_the_point_estimate_is_just_the_metric():
    r = rows({f"q{i}": [i % 2 == 0] for i in range(10)})
    assert interval(r, rate).point == rate(r)


def test_the_interval_brackets_the_truth_and_is_deterministic():
    r = rows({f"q{i}": [i < 7] for i in range(10)})       # 70% correct, one rep each
    e = interval(r, rate)
    assert e.lo <= e.point <= e.hi
    assert 0.0 <= e.lo and e.hi <= 1.0
    assert interval(r, rate).as_dict() == e.as_dict(), "same rows must give the same interval"


def test_reps_do_not_masquerade_as_sample_size():
    """THE DEFECT THE MODULE EXISTS FOR. Five reps of ten questions is ten independent units, not
    fifty. Resampling rows would shrink the interval by roughly sqrt(5); resampling questions must
    not, because nothing new was learned by asking the same question again."""
    one = rows({f"q{i}": [i < 7] for i in range(10)})
    five = rows({f"q{i}": [i < 7] * 5 for i in range(10)})
    a, b = interval(one, rate), interval(five, rate)
    assert a.n_questions == b.n_questions == 10
    assert a.n_rows == 10 and b.n_rows == 50
    # The same ten questions, so the same uncertainty. Allow a little slack for resampling jitter.
    assert abs(a.width - b.width) < 0.06, (
        f"repeating each question five times moved the interval from {a.width:.3f} to {b.width:.3f}, "
        "so reps are being counted as independent observations")


def test_a_single_question_is_not_a_sample():
    e = interval(rows({"q1": [True, True, False]}), rate)
    assert e.n_questions == 1
    assert e.lo != e.lo and e.hi != e.hi, "one question must give NaN bounds, never a zero width"


def test_identical_arms_are_not_a_difference():
    r = {f"q{i}": [i < 6] for i in range(12)}
    c = paired(rows(r, "a"), rows(r, "b"), rate)
    assert c.delta == 0.0
    assert c.discordant == 0 and c.p_value == 1.0
    assert not c.significant


def test_a_clean_sweep_is_a_difference():
    """Arm A wins eight questions outright and loses none. Eight discordant, all one way, so the
    exact test reaches 2 x 0.5^8 = 0.0078."""
    a = rows({f"q{i}": [True] for i in range(8)} | {f"c{i}": [True] for i in range(6)}, "a")
    b = rows({f"q{i}": [False] for i in range(8)} | {f"c{i}": [True] for i in range(6)}, "b")
    c = paired(a, b, rate)
    assert (c.favours_a, c.favours_b, c.discordant) == (8, 0, 8)
    assert c.p_value < 0.01 and c.significant
    assert c.delta > 0 and c.lo > 0, "an interval on a real difference should exclude zero"


def test_five_discordant_questions_cannot_reach_significance():
    """The floor, stated as a property rather than a comment. Even when EVERY discordant question
    favours the same arm, five of them give 2 x 0.5^5 = 0.0625."""
    a = rows({f"q{i}": [True] for i in range(5)} | {f"c{i}": [True] for i in range(20)}, "a")
    b = rows({f"q{i}": [False] for i in range(5)} | {f"c{i}": [True] for i in range(20)}, "b")
    c = paired(a, b, rate)
    assert c.discordant == 5 < MIN_DISCORDANT
    assert not c.significant, "five discordant questions must never be called a result"


def test_concordant_questions_do_not_dilute_the_test():
    """Adding questions both arms answer identically changes the size of the difference and must
    not change whether it is real: they carry no information about which arm is better."""
    disc_a = {f"q{i}": [True] for i in range(8)}
    disc_b = {f"q{i}": [False] for i in range(8)}
    lean = paired(rows(disc_a, "a"), rows(disc_b, "b"), rate)
    padded = paired(rows(disc_a | {f"c{i}": [True] for i in range(40)}, "a"),
                    rows(disc_b | {f"c{i}": [True] for i in range(40)}, "b"), rate)
    assert lean.p_value == padded.p_value
    assert lean.discordant == padded.discordant == 8
    assert padded.delta < lean.delta, "the SIZE of the difference should shrink; its reality should not"


def test_pairing_is_tighter_than_two_absolute_intervals():
    """Why `paired` exists. Question difficulty dominates the absolute scores and cancels in the
    difference, so the interval on the difference is much narrower than either arm's own."""
    hard = [f"h{i}" for i in range(10)]
    easy = [f"e{i}" for i in range(10)]
    # Both arms fail every hard question and pass every easy one; A additionally wins six extra.
    a = rows({q: [False] for q in hard} | {q: [True] for q in easy}
             | {f"x{i}": [True] for i in range(6)}, "a")
    b = rows({q: [False] for q in hard} | {q: [True] for q in easy}
             | {f"x{i}": [False] for i in range(6)}, "b")
    c = paired(a, b, rate)
    solo = interval(a, rate)
    assert c.hi - c.lo < solo.width, (
        f"paired width {c.hi - c.lo:.3f} should beat the absolute width {solo.width:.3f}; "
        "the pairing is not cancelling question difficulty")


def test_unshared_questions_are_dropped_rather_than_half_counted():
    a = rows({"q1": [True], "q2": [True], "only_a": [True]}, "a")
    b = rows({"q1": [False], "q2": [False], "only_b": [False]}, "b")
    c = paired(a, b, rate)
    assert c.n_questions == 2, "a comparison is paired or it is not one"


def test_the_detectable_floor_is_six_questions_worth():
    assert detectable(46) == MIN_DISCORDANT / 46
    assert abs(detectable(46) - 0.130) < 0.001, "46 questions cannot resolve below ~13 points"
    assert detectable(0) != detectable(0), "no questions means no floor, not a zero one"


if __name__ == "__main__":
    # `bench test` runs each file as a SCRIPT, so a test absent from this block runs nowhere.
    test_the_point_estimate_is_just_the_metric()
    test_the_interval_brackets_the_truth_and_is_deterministic()
    test_reps_do_not_masquerade_as_sample_size()
    test_a_single_question_is_not_a_sample()
    test_identical_arms_are_not_a_difference()
    test_a_clean_sweep_is_a_difference()
    test_five_discordant_questions_cannot_reach_significance()
    test_concordant_questions_do_not_dilute_the_test()
    test_pairing_is_tighter_than_two_absolute_intervals()
    test_unshared_questions_are_dropped_rather_than_half_counted()
    test_the_detectable_floor_is_six_questions_worth()
    print("OK — questions are the unit, pairing cancels difficulty, concordance does not dilute, "
          "and five discordant questions are never a result.")
