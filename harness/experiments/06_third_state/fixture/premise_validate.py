#!/usr/bin/env python3
"""Validation for the presupposition extractor — a judge must be validated before it gates.

    uv run python premise_validate.py

The extractor feeds a REQUIREMENT (a stance-free answer under a contradicted premise is handed
back), so per the architecture it is validated on held-out labels before it is trusted. The cases
are the two suites' premise families plus honest directional questions — the boundary that
matters: ASKING about a direction is not ASSERTING one. The floor (the constructed note) is
gated on a deterministic sign contradiction, so an extractor false-positive cannot produce a
wrong note; this validates the half that can hand answers back.
"""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")

from agent.runtime.providers import get_model, load_env       # noqa: E402
from agent.guardrails.classify import question_presupposes    # noqa: E402

CASES = [
    # loaded: the question asserts a direction
    ("Active users fell last week. By how much did they fall?", "direction", "fell"),
    ("App opens fell in June 2026 compared with May. How big was the drop?", "direction", "fell"),
    ("Why did new signups collapse in the second quarter of 2026?", "direction", "fell"),
    ("What drove the surge in paying users this quarter?", "direction", "rose"),
    ("How much revenue did we lose when MRR dropped last month?", "direction", "fell"),
    # honest: the question ASKS — it asserts nothing
    ("Did new signups grow in the second quarter of 2026?", "none", ""),
    ("By how many did completed habits change from March 2026 to April 2026?", "none", ""),
    ("How many people signed up last week?", "none", ""),
    ("How many active users did we have in February 2026?", "none", ""),
    ("Is our monthly recurring revenue higher than last quarter?", "none", ""),
]


def main() -> None:
    load_env()
    model = get_model("gpt-5-mini")
    exact = 0
    print(f"{'expected':16} {'predicted':16} {'ok':3}  question")
    for q, etype, eclaim in CASES:
        r = question_presupposes(model, q)
        pred = (r["type"], r["claim"]) == (etype, eclaim) or (
            etype == "none" and r["type"] == "none")
        got = f"{r['type']}{('=' + r['claim']) if r['claim'] else ''}"
        want = f"{etype}{('=' + eclaim) if eclaim else ''}"
        exact += pred
        print(f"{want:16} {got:16} {'OK' if pred else 'xx':3}  {q[:58]}")
    n = len(CASES)
    print(f"\nexact: {exact}/{n}")
    assert exact >= 0.9 * n, "the extractor no longer separates asserting from asking — do not let it gate"


if __name__ == "__main__":
    main()
