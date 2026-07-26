"""Score the trajectory verifier against the INDEPENDENT gold, from stored rows.

`verifier_audit.py` scores the judge against human labels. That is the stronger instrument and
it is also the expensive one: it needs someone to label a blind sheet, and the labels go stale
every time the judge's prompt changes — which, in the July series, was five times in a day.

This is the cheap complement. Every `metric_answer` question carries a `gold_sql` that computes
the answer straight from the fact tables, without touching the semantic layer the agent used. So
for any judged row with a numeric gold, whether the answer was right is already known, and the
judge's verdict can be SCORED rather than merely compared with what it said last time:

    judge REFUSED an answer that matched gold   -> false flag   (lost coverage)
    judge PASSED  an answer that missed gold    -> miss         (a served wrong number)

No model calls, no labelling, and it re-runs over any stored run in a second. Two honest limits,
both of which is why it complements the human panel rather than replacing it:

  * It covers only rows with a numeric gold. Diagnostic and keyword questions have none, so the
    judge's behaviour there is still unscored — those are exactly the rows the panel must label.
  * `gold_sql` is an independent COMPUTATION, not an independent JUDGEMENT. It is written by the
    same hand that wrote the questions and the layer. It kills "the semantic layer graded its own
    homework" — the gold never goes through it — and it does not kill "the author graded their
    own homework".

    uv run python evals/components/verifier_vs_gold.py results/latest/raw.jsonl [more.jsonl ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LABELS_DIR = Path(__file__).resolve().parent.parent / "labels"
OUT = LABELS_DIR / "verifier_vs_gold.json"


def scored_rows(paths: list[str]) -> list[dict]:
    """Judged rows where an independent gold says whether the answer was right."""
    out = []
    for p in paths:
        for line in Path(p).open():
            r = json.loads(line)
            v = r.get("verifier_verdict")
            gold, declared = r.get("gold"), r.get("declared_value")
            if not v or v.get("answers_question") is None or gold is None or declared is None:
                continue
            out.append({
                "qid": r["qid"], "rung": r["rung"], "config": r["config"], "rep": r.get("rep"),
                "passed": bool(v["answers_question"]), "mismatch": v.get("mismatch"),
                "value_role": v.get("value_role"),
                # The tolerance the grader itself uses, so this agrees with `correct` by
                # construction rather than by a second opinion about rounding.
                "answer_right": abs(declared - gold) <= max(abs(gold) * 0.02, 1e-9),
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
    record = {"method": "independent gold_sql (no human labels; numeric questions only)",
              "prompt_fingerprint": prompt_fingerprint(), "source_runs": paths, **s}
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2))

    print(f"judge vs independent gold — n={s['n']}  (fingerprint {record['prompt_fingerprint']})\n")
    print(f"                       answer RIGHT   answer WRONG")
    print(f"    judge PASSED     {s['ok_pass']:>10}      {s['miss']:>10}  <- miss")
    print(f"    judge REFUSED    {s['false_flag']:>10}      {s['catch']:>10}  <- catch")
    print(f"       ^ false flag")
    print(f"\n    agreement       {s['agreement']:.1%}")
    print(f"    false-flag rate {s['false_flag_rate']:.1%}   (refused {s['false_flag']} correct answers)")
    print(f"    catch rate      {s['catch_rate']:.1%}   (caught {s['catch']} wrong answers)")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
