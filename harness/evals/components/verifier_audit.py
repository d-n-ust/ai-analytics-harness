"""Score the trajectory verifier against human labels.

The verifier is a JUDGE — an LLM deciding whether a served number answers the question —
and every "zero confident-wrong" result rests on it. A judge is only trustworthy once its
error rate is measured against held-out human labels; `verifier_eval.py` is a hand-picked
smoke test, not that measurement. This scores it from STORED runs: no re-running, no model
calls, so the same rows can be re-scored whenever the label set grows.

    sample:  uv run python evals/components/verifier_audit.py sample --run runs/latest --n 20
             Writes a BLIND sheet (the verdict withheld) plus a hidden key file.
    score:   uv run python evals/components/verifier_audit.py score

Two error directions, and they cost different things:
    false-flag  the judge REFUSED an answer a human says is correct  -> lost coverage
    miss        the judge PASSED an answer a human says is wrong     -> a served wrong number,
                the failure the whole ladder exists to prevent
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import yaml

LABELS_DIR = Path(__file__).resolve().parent.parent / "labels"   # evals/labels (this file is in evals/components/)
SHEET = LABELS_DIR / "verifier_sample.yml"
KEY = LABELS_DIR / "verifier_sample.key.json"
SEED = 20260724       # fixed, so the same run yields the same sample


def _verdict_rows(run_dir: Path) -> list[dict]:
    rows = []
    for line in (run_dir / "raw.jsonl").open():
        r = json.loads(line)
        if r.get("verifier_verdict"):
            rows.append(r)
    return rows


def cmd_sample(args) -> None:
    run_dir = Path(args.run).resolve()
    rows = _verdict_rows(run_dir)
    if not rows:
        raise SystemExit(f"no stored verifier verdicts in {run_dir} — run at rrung 9 first")

    # Stratify by the judge's own verdict so BOTH error directions are measurable; prefer
    # distinct questions so one item can't dominate the rate.
    passed = [r for r in rows if r["verifier_verdict"]["answers_question"]]
    failed = [r for r in rows if not r["verifier_verdict"]["answers_question"]]
    rng = random.Random(SEED)

    def pick(pool: list[dict], k: int) -> list[dict]:
        by_qid: dict[str, dict] = {}
        for r in sorted(pool, key=lambda x: (x["qid"], x.get("rep", 0))):
            by_qid.setdefault(r["qid"], r)          # one row per question first
        chosen = list(by_qid.values())
        rng.shuffle(chosen)
        return chosen[:k]

    half = max(1, args.n // 2)
    sample = pick(passed, half) + pick(failed, args.n - half)
    rng.shuffle(sample)                              # so the sheet order leaks nothing

    LABELS_DIR.mkdir(exist_ok=True)
    sheet, key = [], {}
    for i, r in enumerate(sample, 1):
        v = r["verifier_verdict"]
        cid = f"V{i:03d}"
        sheet.append({
            "id": cid,
            "question": r["question"],
            "metric_used": v["metric"],
            "analyst_added_filters": v["applied_filters"],
            "time_window": v["time_window"],
            "sql": v["sql"],
            "query_result": v["governed_value"],
            "served_answer": v["claim"],
            # Label this: does the served answer actually answer the question?
            "human": "",                             # "yes" | "no"
        })
        key[cid] = {"answers_question": v["answers_question"], "mismatch": v["mismatch"],
                    "judge_reason": v["reason"], "qid": r["qid"], "tier": r["tier"],
                    "run": run_dir.name}

    SHEET.write_text(
        "# BLIND labelling sheet for the trajectory verifier.\n"
        "# For each case, read the question and what the analyst computed, then set\n"
        "#   human: yes   -> the served answer DOES answer the question\n"
        "#   human: no    -> it does not (wrong thing / wrong scope / wrong kind / wrong definition)\n"
        "# The judge's own verdict is deliberately withheld; it lives in the key file.\n"
        + yaml.safe_dump({"cases": sheet}, sort_keys=False, allow_unicode=True, width=100))
    KEY.write_text(json.dumps(key, indent=2))
    print(f"wrote {SHEET}  ({len(sheet)} cases: {len(pick(passed, half))} judged PASS, "
          f"{len(pick(failed, args.n - half))} judged FAIL — withheld)")
    print(f"key   {KEY}  (do not open before labelling)")


def cmd_score(args) -> None:
    sheet = yaml.safe_load(SHEET.read_text())["cases"]
    key = json.loads(KEY.read_text())
    labelled = [c for c in sheet if str(c.get("human", "")).strip().lower() in ("yes", "no")]
    if not labelled:
        raise SystemExit(f"no labels filled in {SHEET}")

    ff = miss = agree = 0
    for c in labelled:
        human_ok = str(c["human"]).strip().lower() == "yes"
        judge_ok = key[c["id"]]["answers_question"]
        if judge_ok and not human_ok:
            miss += 1
        elif not judge_ok and human_ok:
            ff += 1
        else:
            agree += 1

    n = len(labelled)
    n_pass = sum(1 for c in labelled if key[c["id"]]["answers_question"])
    n_fail = n - n_pass
    print(f"labelled: {n}/{len(sheet)}   (judge passed {n_pass}, judge failed {n_fail})")
    print(f"  agreement   : {agree}/{n} ({agree / n:.0%})")
    print(f"  MISS RATE   : {miss}/{n_pass or 1} of judged-PASS  -> a wrong number was served")
    print(f"  FALSE-FLAG  : {ff}/{n_fail or 1} of judged-FAIL   -> a correct answer was refused")
    print(f"\nn={n}. Directional at this size — report the n with any rate.")

    # Persist the validation, fingerprinted with the verifier prompt that was scored, so the report
    # can flag it stale the moment the prompt changes. This is what makes the "0 confident-wrong"
    # headline self-checking instead of resting on an unverifiable assumption.
    from datetime import date

    from agent.guardrails.judge import prompt_fingerprint
    record = {"labelled": n, "agreement": agree,
              "miss": miss, "miss_rate": round(miss / (n_pass or 1), 3),
              "false_flag": ff, "false_flag_rate": round(ff / (n_fail or 1), 3),
              "prompt_fingerprint": prompt_fingerprint(),
              "run": key[labelled[0]["id"]]["run"], "date": date.today().isoformat()}
    (LABELS_DIR / "verifier_validation.json").write_text(json.dumps(record, indent=2))
    print(f"wrote {LABELS_DIR / 'verifier_validation.json'}  (fingerprint {record['prompt_fingerprint']})")


def main() -> None:
    p = argparse.ArgumentParser(prog="verifier_audit.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw a blind labelling sheet from a stored run")
    s.add_argument("--run", default="runs/latest")
    s.add_argument("--n", type=int, default=20)
    s.set_defaults(func=cmd_sample)
    s = sub.add_parser("score", help="score the filled sheet against the withheld verdicts")
    s.set_defaults(func=cmd_score)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
