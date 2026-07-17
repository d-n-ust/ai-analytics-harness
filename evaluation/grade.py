"""Grade an answer. Three graders, picked by the question's `grader` field:

- numeric (default): did it produce a value, and is it correct within tolerance
  (accepting a rate answered as a percentage, e.g. 0.53 vs 53%).
- keywords: for fuzzy-mapping questions — did it name the right metric.
- diagnostic: did it identify the right driver AND the root cause.

Plus, for every question, whether it abstained and whether it was *confidently wrong*
(a number, not an abstention, but wrong — the dangerous case).
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
    cause_ok = any(k in t for k in spec.get("cause", []))
    return {"executed": True, "correct": driver_ok and cause_ok,
            "driver_ok": driver_ok, "cause_ok": cause_ok}


def grade(answer, question: dict, gold: float | None) -> dict:
    grader = question.get("grader", "numeric")
    text = f"{answer.answer or ''} {answer.explanation or ''}"
    if grader == "diagnostic":
        g = grade_diagnostic(text, question["gold_diagnostic"])
    elif grader == "keywords":
        g = grade_keywords(text, question["gold_keywords"])
    else:
        g = grade_numeric(answer.answer, gold, question.get("tolerance", 0.02))
    g["abstained"] = answer.abstained
    g["confident_wrong"] = (not answer.abstained and not g["correct"]
                            and answer.answer is not None and answer.error is None)
    return g
