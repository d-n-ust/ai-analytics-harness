"""Score the trajectory verifier against the INDEPENDENT gold, from stored rows.

`verifier_audit.py` scores the judge against human labels. That is the stronger instrument and
it is also the expensive one: it needs someone to label a blind sheet, and the labels go stale
every time the judge's prompt changes — which, in the July series, was five times in a day.

This is the cheap complement. Two kinds of row already know whether the answer was right, so the
judge's verdict can be SCORED rather than merely compared with what it said last time. A numeric
question carries a `gold_sql` computed straight from the fact tables, without touching the
semantic layer the agent used. An UNANSWERABLE question has no correct number at all, so any
number served is wrong by construction — no tolerance, no label needed.

    judge REFUSED an answer the gold says was right  -> false flag   (lost coverage)
    judge PASSED  an answer the gold says was wrong  -> miss         (a served wrong number)

No model calls, no labelling, and it re-runs over any stored run in a second. Two honest limits,
which are why it complements the human panel rather than replacing it:

  * It cannot see PROSE answers. Diagnostic and keyword questions are arguments, not figures, and
    have no gold of either kind — the panel must label those. An instrument blind to a set of
    rows must not report a number that implies otherwise, so they are excluded rather than
    assumed correct.
  * `gold_sql` is an independent COMPUTATION, not an independent JUDGEMENT. It is written by the
    same hand that wrote the questions and the layer. It kills "the semantic layer graded its own
    homework" — the gold never goes through it — and it does not kill "the author graded their
    own homework".

    uv run python evals/components/verifier_vs_gold.py results/latest/raw.jsonl [more.jsonl ...]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

LABELS_DIR = Path(__file__).resolve().parent.parent / "labels"
OUT = LABELS_DIR / "verifier_vs_gold.json"


def scored_rows(paths: list[str]) -> list[dict]:
    """Judged rows where something other than a human already says whether the answer was right.

    Two such rows, and the second costs nothing extra:

      * a numeric question with a `gold_sql` — the answer is right iff it matches, within the
        grader's own tolerance so this cannot disagree with `correct` about rounding.
      * an UNANSWERABLE question with no gold at all. No correct number exists, so any number
        served is wrong by construction. That needs no tolerance and no label; a judge that
        passed one missed.

    What is left after both is the prose set — diagnostic and keyword questions where the answer
    is an argument rather than a figure. Those are the rows a human panel has to label, and
    keeping them out of this score is the point: an instrument that cannot see them should not
    report a number that implies it did."""
    out = []
    for p in paths:
        for line in Path(p).open():
            r = json.loads(line)
            v = r.get("verifier_verdict")
            if not v or v.get("answers_question") is None:
                continue
            gold, declared = r.get("gold"), r.get("declared_value")
            if gold is not None and declared is not None:
                right, basis = abs(declared - gold) <= max(abs(gold) * 0.02, 1e-9), "gold_sql"
            elif r.get("expected_refuse") and declared is not None:
                right, basis = False, "unanswerable"      # no correct number exists
            else:
                continue                                   # prose — for the human panel
            out.append({
                "qid": r["qid"], "rung": r["rung"], "config": r["config"], "rep": r.get("rep"),
                "passed": bool(v["answers_question"]), "mismatch": v.get("mismatch"),
                "value_role": v.get("value_role"), "basis": basis, "answer_right": right,
            })
    return out


def score(rows: list[dict]) -> dict:
    catch = sum(1 for r in rows if not r["passed"] and not r["answer_right"])
    false_flag = sum(1 for r in rows if not r["passed"] and r["answer_right"])
    ok_pass = sum(1 for r in rows if r["passed"] and r["answer_right"])
    miss = sum(1 for r in rows if r["passed"] and not r["answer_right"])
    n = len(rows)
    return {
        "n": n, "catch": catch, "false_flag": false_flag, "ok_pass": ok_pass, "miss": miss,
        "agreement": (catch + ok_pass) / n if n else None,
        # Denominators are the two populations, not n: a false-flag rate over all decisions
        # shrinks as the judge sees more correct answers, which is not a property of the judge.
        "false_flag_rate": false_flag / (false_flag + ok_pass) if (false_flag + ok_pass) else None,
        "catch_rate": catch / (catch + miss) if (catch + miss) else None,
    }


def main() -> None:
    paths = sys.argv[1:] or ["results/latest/raw.jsonl"]
    rows = scored_rows(paths)
    if not rows:
        raise SystemExit("no judged rows with a numeric gold in those runs")
    s = score(rows)

    from agent.guardrails.judge import prompt_fingerprint
    by_basis = Counter(r["basis"] for r in rows)
    record = {"method": "independent gold (no human labels): gold_sql on numeric questions, "
                        "plus unanswerable questions where any served number is wrong",
              "covers": dict(by_basis), "excludes": "prose answers (diagnostic/keywords)",
              "prompt_fingerprint": prompt_fingerprint(), "source_runs": paths, **s}
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2))

    print(f"judge vs independent gold — n={s['n']}  (fingerprint {record['prompt_fingerprint']})\n")
    print("                       answer RIGHT   answer WRONG")
    print(f"    judge PASSED     {s['ok_pass']:>10}      {s['miss']:>10}  <- miss")
    print(f"    judge REFUSED    {s['false_flag']:>10}      {s['catch']:>10}  <- catch")
    print("       ^ false flag")
    print(f"\n    agreement       {s['agreement']:.1%}")
    print(f"    false-flag rate {s['false_flag_rate']:.1%}   (refused {s['false_flag']} correct answers)")
    print(f"    catch rate      {s['catch_rate']:.1%}   (caught {s['catch']} wrong answers)")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
