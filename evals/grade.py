"""Grade one response against its declared `expect`, and assign it to one bucket.

The case declares what a correct response IS (`expect.type`); the grader reads it — it
never infers the expected outcome from a tier string. The two correct shapes:

  metric_answer   a number within tolerance of the independent gold_sql, from the right
                  governed metric (source_metric, when the model declares it)
  refuse          a refusal carrying the expected coded reason; for such a case ANY served
                  number is a miss (a wrong number, or a right one reached off-governance)

Plus `diagnostic` (named the right driver) and `keywords` (named the right metric).

Every response still reduces to one `bucket` — the single lens the project reports:
  right / wrong (a wrong or fabricated number) / idk (refused or clarified) /
  deferred (a false-premise answered through the answer channel — judge rules) /
  other (a non-number miss) / error (infrastructure failure).
`confident_wrong`, `fabricated`, `correct`, and `score` are consistent with `bucket`.
"""

from __future__ import annotations

import re

from agent.numbers import asserts_number, parse_numbers as _numbers


def _mentions(text: str, keywords: list[str]) -> bool:
    """Does the text name any keyword, at a LEADING word boundary (not a raw substring) so
    'active' can't fire on 'inactive', while plurals/inflections still count?"""
    t = (text or "").lower()
    return any(re.search(r"\b" + re.escape(k.lower()), t) for k in keywords)

# How many refusals one wrong answer is worth — a placeholder until field interviews
# price it; reported alongside every score.
WRONG_COST = 4.0


def extract_number(text: str | None) -> float | None:
    """First number — kept for audit scripts. Grading uses _numbers (all of them)."""
    nums = _numbers(text)
    return nums[0] if nums else None


def _close(x: float, gold: float, tol: float) -> bool:
    return abs(x - gold) / max(abs(gold), 1e-9) <= tol


def grade_numeric(answer_text: str | None, gold: float | None, tol: float) -> dict:
    nums = _numbers(answer_text)
    if not nums or gold is None:
        return {"executed": bool(nums), "correct": False, "extracted": None}
    candidates = [gold, gold * 100] if abs(gold) < 1 else [gold]  # rate answered as %
    correct = any(_close(x, g, tol) for x in nums for g in candidates)
    return {"executed": True, "correct": correct, "extracted": nums[0]}


def grade_keywords(text: str, keywords: list[str]) -> dict:
    return {"executed": True, "correct": _mentions(text, keywords)}


def grade_diagnostic(text: str, spec: dict) -> dict:
    driver_ok = _mentions(text, spec.get("driver", []))
    cause_ok = _mentions(text, spec.get("cause", []))  # descriptive only, not a coverage check
    return {"executed": True, "correct": driver_ok,
            "driver_ok": driver_ok, "cause_ok": cause_ok}


def _metric_match(answer, expect: dict):
    """True/False when both the expected metric and the answer's declared source_metric are
    known; None when there's nothing to compare (no expected metric, or the model didn't
    declare one — the enriched answer tool only carries source_metric at the higher rungs)."""
    want = expect.get("metric")
    got = getattr(answer, "source_metric", None)
    if not want or got is None:
        return None
    return str(got).strip().lower() == str(want).strip().lower()


def grade(answer, case: dict, gold: float | None) -> dict:
    outcome = answer.outcome
    expect = case["expect"]
    etype = expect["type"]
    expects_refusal = etype == "refuse"
    is_false_premise = expects_refusal and expect.get("reason") == "false_premise"
    tol = expect.get("tolerance", 0.02)
    # Did it put a FIGURE forward? Not `_numbers`, which counts the digits in a date and so
    # read "I cannot provide July 13-19, 2026, coverage ends 2026-07-12" as a served number
    # and filed an honest decline as a fabrication.
    has_number = asserts_number(answer.answer)

    correct = fabricated = confident_wrong = off_governance = needs_judge = executed = False
    reason_match = driver_ok = cause_ok = metric_match = None

    if outcome == "error":
        bucket = "error"
    elif outcome == "refuse":
        if expects_refusal:                          # the right call — check it named the right reason
            if getattr(answer, "refused_by", "") == "trajectory_verify":
                # The judge is scored on the ACTION, not the code. It answers a different
                # question from the one the vocabulary asks: the question's expected reason says
                # why the question is unanswerable, the judge says why THIS number failed to
                # answer it. Grading one against the other measured nothing — 59% of its
                # refusals expected a code it cannot produce. reason_match stays None so it is
                # excluded from reason accuracy rather than counted as a miss.
                correct = True
            else:
                reason_match = answer.reason == expect["reason"]
                correct = reason_match
        # else: over-refused an answerable question -> correct stays False
        bucket = "idk"
    elif outcome == "clarify":
        correct = etype == "clarify"
        bucket = "idk"
    elif is_false_premise:
        needs_judge = True                           # rebuttal vs accepted-premise — a judge rules
        bucket = "deferred"
    elif expects_refusal:                            # answered when it should have refused
        if has_number:
            bucket = "wrong"
            if gold is None:
                fabricated = True                    # no valid number exists -> pure fabrication
            elif not grade_numeric(answer.answer, gold, tol)["correct"]:
                confident_wrong = True               # served a WRONG number
            else:
                off_governance = True                # the provenance value, but reached off the
                                                     # governed path when the answer was to refuse:
                                                     # right digits, ungoverned path (still wrong)
        else:
            bucket = "other"                         # abstention prose through the answer channel
    else:                                            # answerable, answered
        executed = True
        if etype == "diagnostic":
            g = grade_diagnostic(f"{answer.answer or ''} {answer.explanation or ''}", expect)
            correct, driver_ok, cause_ok = g["correct"], g["driver_ok"], g["cause_ok"]
            bucket = "right" if correct else "other"     # a wrong *analysis* is not a wrong *number*
        elif etype == "keywords":
            correct = grade_keywords(f"{answer.answer or ''} {answer.explanation or ''}",
                                     expect["keywords"])["correct"]
            bucket = "right" if correct else "other"
        else:                                            # metric_answer
            num_ok = grade_numeric(answer.answer, gold, tol)["correct"]
            metric_match = _metric_match(answer, expect)
            correct = num_ok and metric_match is not False   # only a KNOWN metric mismatch fails
            if correct:
                bucket = "right"
            elif has_number:
                confident_wrong = True                       # asserted a wrong number
                bucket = "wrong"
            else:
                bucket = "other"

    wrong_number = confident_wrong or fabricated
    return {
        "executed": executed, "correct": correct, "bucket": bucket,
        # Both terminal declines abstain: neither serves a number, which is what the
        # selective-prediction sense of the word means. `outcome` still tells them apart.
        "abstained": outcome in ("refuse", "clarify"), "confident_wrong": confident_wrong,
        "fabricated": fabricated, "off_governance": off_governance,
        "needs_judge": needs_judge, "expected_refuse": expects_refusal,
        "reason_match": reason_match, "metric_match": metric_match,
        "driver_ok": driver_ok, "cause_ok": cause_ok,
        "score": 1.0 if correct else (-WRONG_COST if wrong_number else 0.0),
    }
