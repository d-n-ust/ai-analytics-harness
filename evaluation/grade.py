"""Grade an answer. Three graders, picked by the question's `grader` field:

- numeric (default): did it produce a value, and is it correct within tolerance
  (accepting a rate answered as a percentage, e.g. 0.53 vs 53%).
- keywords: for fuzzy-mapping questions — did it name the right metric.
- diagnostic: did it identify the right *driver* (which lever moved). It does NOT
  require naming a root cause: the generated world has no identifiable cause for the
  drop (reminder rate and days/user are siblings under one anomaly switch, not
  cause-and-effect — see data/generate.py and audit/generator_check.py), so demanding
  a named cause would reward the very fabrication this project studies. Whether the
  answer nonetheless asserted the (unsupported) reminder cause is recorded descriptively
  in `cause_ok`, never as a correctness gate.

Plus, for every question: whether it abstained (refused), and whether it *fabricated*
— asserted a number that is wrong (or asserted any number for a question with no valid
answer). Abstention-shaped prose smuggled through the answer channel ("no data") is a
protocol miss, not a fabrication, and is not penalized as one.
"""

from __future__ import annotations

import re


def extract_number(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"-?\d+\.?\d*", text.replace(",", "").replace("$", ""))
    return float(m.group()) if m else None


def _close(x: float, gold: float, tol: float) -> bool:
    return abs(x - gold) / max(abs(gold), 1e-9) <= tol


def grade_numeric(answer_text: str | None, gold: float | None, tol: float) -> dict:
    x = extract_number(answer_text)
    if x is None or gold is None:
        return {"executed": x is not None, "correct": False, "extracted": x}
    candidates = [gold, gold * 100] if abs(gold) < 1 else [gold]  # rate answered as %
    return {"executed": True, "correct": any(_close(x, g, tol) for g in candidates), "extracted": x}


def grade_keywords(text: str, keywords: list[str]) -> dict:
    t = text.lower()
    return {"executed": True, "correct": any(k in t for k in keywords)}


def grade_diagnostic(text: str, spec: dict) -> dict:
    t = text.lower()
    driver_ok = any(k in t for k in spec.get("driver", []))
    cause_ok = any(k in t for k in spec.get("cause", []))  # descriptive only, not a gate
    return {"executed": True, "correct": driver_ok,
            "driver_ok": driver_ok, "cause_ok": cause_ok}


# How many refusals one wrong answer is worth. A placeholder until the field
# interviews price it; every score is reported alongside this constant.
WRONG_COST = 4.0


def grade(answer, question: dict, gold: float | None) -> dict:
    """Outcome-aware grading. An unanswerable question (gold_refuse) is answered
    correctly by refusing; asserting a value for it is fabrication. On answerable
    questions a refusal is a coverage loss (score 0), never a wrong answer. Rows that
    crashed (outcome=error) are infrastructure failures, scored 0 and never counted as
    a model behaviour."""
    unanswerable = "gold_refuse" in question
    has_number = extract_number(answer.answer) is not None
    if answer.outcome == "error":
        g = {"executed": False, "correct": False, "reason_match": None}
    elif answer.outcome == "refuse":
        g = {"executed": False, "correct": unanswerable,
             "reason_match": (answer.reason == question["gold_refuse"]) if unanswerable else None}
    elif answer.outcome == "clarify":
        g = {"executed": False, "correct": False, "reason_match": None}
    elif unanswerable:
        g = {"executed": answer.answer is not None, "correct": False, "reason_match": None}
    else:
        grader = question.get("grader", "numeric")
        text = f"{answer.answer or ''} {answer.explanation or ''}"
        if grader == "diagnostic":
            g = grade_diagnostic(text, question["gold_diagnostic"])
        elif grader == "keywords":
            g = grade_keywords(text, question["gold_keywords"])
        else:
            g = grade_numeric(answer.answer, gold, question.get("tolerance", 0.02))
        g["reason_match"] = None
    g["abstained"] = answer.outcome == "refuse"
    # Fabrication is asserting a *number* that is wrong (or any number for an
    # unanswerable question). Abstention prose through the answer channel ("no data")
    # has no number: it's a protocol miss, not a fabrication, and carries no penalty.
    g["confident_wrong"] = (answer.outcome == "answer" and not g["correct"]
                            and has_number and answer.error is None)
    g["fabricated"] = unanswerable and answer.outcome == "answer" and has_number
    g["score"] = 1.0 if g["correct"] else (-WRONG_COST if g["confident_wrong"] else 0.0)
    return g
