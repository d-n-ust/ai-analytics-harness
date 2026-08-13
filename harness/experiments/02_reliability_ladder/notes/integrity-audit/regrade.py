"""Integrity audit, part 1: regrade a raw.jsonl without trusting the graders.

Three questions, answered from the rows alone:
  1. Do the stored per-rung numbers reproduce from the row-level fields?
  2. How often did `abstained` and `correct` end up true on the same row
     (a refusal credited as a correct answer)?
  3. For the diagnostic tier: was the gold cause-word ("reminder"/"notification")
     already sitting in the model's context — a tool result or the grounding
     itself — before it answered? If so, the grader's keyword match can't
     distinguish reasoning from echo.

Usage: python experiments/02_reliability_ladder/notes/integrity-audit/regrade.py <raw.jsonl>
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

CAUSE_WORDS = ("remind", "notif")


def leak_source(row: dict) -> dict | None:
    """First step whose tool result handed the model a cause word."""
    for i, s in enumerate(row.get("steps") or []):
        blob = f"{s.get('tool', '')} {json.dumps(s.get('args') or {})} {s.get('result') or ''}".lower()
        if any(w in blob for w in CAUSE_WORDS):
            return {"step": i, "tool": s.get("tool"), "args": s.get("args")}
    return None


def main(path: str) -> None:
    rows = [json.loads(line) for line in open(path)]
    print(f"{len(rows)} rows from {path}\n")

    # -- 1. per-rung reproduction ------------------------------------------
    per_rung = defaultdict(lambda: {"n": 0, "correct": 0, "cw": 0, "abstained": 0})
    for r in rows:
        b = per_rung[r["rung"]]
        b["n"] += 1
        b["correct"] += bool(r["correct"])
        b["cw"] += bool(r["confident_wrong"])
        b["abstained"] += bool(r["abstained"])
    print("rung  n   correct  confident_wrong  abstained")
    for rung in sorted(per_rung):
        b = per_rung[rung]
        print(f"  {rung}   {b['n']}    {b['correct']:>3}        {b['cw']:>3}           {b['abstained']:>3}")

    # -- 2. refusal credited as correct ------------------------------------
    both = [r for r in rows if r["correct"] and r["abstained"]]
    print(f"\nrows with correct=True AND abstained=True: {len(both)}")
    for r in both:
        print(f"  rung {r['rung']}  {r['qid']}  answer={r['answer']!r}")

    # -- 3. diagnostic tier: dump + leak analysis --------------------------
    diags = sorted((r for r in rows if r["tier"] == "diagnostic"),
                   key=lambda r: (r["rung"], r["qid"]))
    print(f"\n{len(diags)} diagnostic rows -> experiments/02_reliability_ladder/notes/integrity-audit/diagnostic_rows.json")
    out = []
    for r in diags:
        leak = leak_source(r)
        out.append({
            "rung": r["rung"], "qid": r["qid"],
            "graded_correct": r["correct"], "driver_ok": r["driver_ok"],
            "cause_ok": r["cause_ok"], "abstained": r["abstained"],
            "cause_word_in_context": leak,
            "answer": r["answer"], "explanation": r["explanation"],
            "tools_used": [s.get("tool") for s in (r.get("steps") or [])],
        })
    with open("experiments/02_reliability_ladder/notes/integrity-audit/diagnostic_rows.json", "w") as f:
        json.dump(out, f, indent=2)

    leaked = sum(1 for o in out if o["cause_word_in_context"])
    passed = sum(1 for o in out if o["graded_correct"])
    passed_and_leaked = sum(1 for o in out if o["graded_correct"] and o["cause_word_in_context"])
    print(f"  graded correct: {passed}/{len(diags)}")
    print(f"  cause word visible in a tool result first: {leaked}/{len(diags)}")
    print(f"  graded correct AND word was in context: {passed_and_leaked}/{passed if passed else 1}")
    by_rung = defaultdict(lambda: [0, 0])
    for o in out:
        by_rung[o["rung"]][0] += bool(o["cause_word_in_context"])
        by_rung[o["rung"]][1] += 1
    print("  leak by rung: " + ", ".join(f"r{k}: {v[0]}/{v[1]}" for k, v in sorted(by_rung.items())))


if __name__ == "__main__":
    main(sys.argv[1])
