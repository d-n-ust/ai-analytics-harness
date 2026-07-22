"""Grade one response, and assign it to exactly one bucket.

Every response reduces to a single `bucket` — the one lens the whole project reports:

  right      answered, and correct (a right number, or the right driver/metric)
  wrong      asserted a WRONG NUMBER: a wrong value on an answerable question, or any
             number on a question that has no valid answer (fabrication)
  idk        refused or clarified — "I don't know", by form (a correct refusal of an
             impossible question is still `bucket=idk`; its correctness is tracked in
             `correct`)
  deferred   a false-premise question answered through the answer channel — a correct
             rebuttal ("it didn't collapse — it rose") and a fabricated cause look
             alike to a heuristic, so the grader abstains and a human/judge rules
  other      a non-number wrong answer (a wrong *analysis*, or abstention prose like
             "I can't compute that" typed through the answer channel — a protocol
             miss, not a fabrication)
  error      an infrastructure failure (crash / API error); never a model behaviour

`bucket` is the single source of truth; `confident_wrong`, `fabricated`, `correct`,
and `score` are consistent with it by construction. This replaces a pile of
independent heuristics that disagreed with each other.

Graders (question `grader` field): numeric (default) checks whether ANY number in the
answer matches gold within tolerance (robust to a leading date, e.g. "in June 2026,
MRR was 2685"); keywords names the right metric; diagnostic names the right *driver*
(not a cause — the generated world has no reminder->activity cause; see
data/generate.py and audit/generator_check.py).
"""

from __future__ import annotations

import re

from harness.numbers import parse_numbers as _numbers


def _mentions(text: str, keywords: list[str]) -> bool:
    """Does the text name any of these keywords, at a word boundary? A LEADING boundary
    (not a raw substring) so a keyword can't match mid-word — "active" must not fire on
    "inactive" — while inflections and plurals still count ("reminder" hits "reminders").
    Multi-word phrases and separators (days/user) match literally."""
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
    cause_ok = _mentions(text, spec.get("cause", []))  # descriptive only, not a gate
    return {"executed": True, "correct": driver_ok,
            "driver_ok": driver_ok, "cause_ok": cause_ok}


def grade(answer, question: dict, gold: float | None) -> dict:
    outcome = answer.outcome
    unanswerable = "gold_refuse" in question
    is_false_premise = question.get("gold_refuse") == "false_premise"
    grader = question.get("grader", "numeric")
    has_number = bool(_numbers(answer.answer))

    correct = fabricated = confident_wrong = needs_judge = executed = False
    reason_match = driver_ok = cause_ok = None

    if outcome == "error":
        bucket = "error"
    elif outcome == "refuse":
        correct = unanswerable                    # refusing an unanswerable question is the right call
        reason_match = (answer.reason == question["gold_refuse"]) if unanswerable else None
        bucket = "idk"                            # by form, a refusal is "I don't know"
    elif outcome == "clarify":
        bucket = "idk"
    elif unanswerable and is_false_premise:
        needs_judge = True                        # rebuttal vs accepted-premise — defer to a judge
        bucket = "deferred"
    elif unanswerable:
        if has_number:                            # a number for a question with no valid answer
            fabricated = True
            bucket = "wrong"
        else:                                     # "I can't compute that" through the answer channel
            bucket = "other"                      # a protocol miss, not a fabrication
    else:                                         # answerable, answered
        executed = True
        if grader == "diagnostic":
            g = grade_diagnostic(f"{answer.answer or ''} {answer.explanation or ''}",
                                 question["gold_diagnostic"])
            correct, driver_ok, cause_ok = g["correct"], g["driver_ok"], g["cause_ok"]
            bucket = "right" if correct else "other"     # a wrong *analysis* is not a wrong *number*
        elif grader == "keywords":
            correct = grade_keywords(f"{answer.answer or ''} {answer.explanation or ''}",
                                     question["gold_keywords"])["correct"]
            bucket = "right" if correct else "other"
        else:                                            # numeric
            correct = grade_numeric(answer.answer, gold, question.get("tolerance", 0.02))["correct"]
            if correct:
                bucket = "right"
            elif has_number:                             # asserted a wrong number
                confident_wrong = True
                bucket = "wrong"
            else:
                bucket = "other"

    wrong_number = confident_wrong or fabricated
    return {
        "executed": executed, "correct": correct, "bucket": bucket,
        "abstained": outcome == "refuse", "confident_wrong": confident_wrong,
        "fabricated": fabricated, "needs_judge": needs_judge, "expected_refuse": unanswerable,
        "reason_match": reason_match, "driver_ok": driver_ok, "cause_ok": cause_ok,
        "score": 1.0 if correct else (-WRONG_COST if wrong_number else 0.0),
    }
