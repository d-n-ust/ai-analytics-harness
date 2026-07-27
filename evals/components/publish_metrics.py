"""Persist a run's METRICS, not its rows.

The rows are 19M for one series and gzipping them only hides that; a tracked blob nobody opens is
not evidence. What a later analysis actually reads is a table — one line per cell, every measure
already computed — and that is 40KB, diffs in review, and can be loaded by anything.

Three tables, because they have different grains and jamming them together would force a wide,
mostly-empty file:

    cells.csv   one row per (run, rung, config): the selective-prediction point, the two question
                families, buckets, cost, tokens, latency, loop shape, judge behaviour
    tiers.csv   one row per (cell, tier): correct / n — which question types a cell wins and loses
    tools.csv   one row per (cell, tool): calls per question — what the agent actually reached for

What is deliberately NOT kept: the per-row traces. They are what you need to re-derive a number
from scratch or replay a judge call, and they are 84% of the bytes. The trade is stated rather
than hidden — these tables let you CHECK a published figure and compare cells; they do not let
you audit an individual answer. For that, re-run the cell: the manifest records the model,
reasoning effort and surface fingerprint needed to reproduce it.

    PYTHONPATH=. uv run python evals/components/publish_metrics.py <out-dir> <run-dir> [...]
"""

from __future__ import annotations

import csv
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from agent.models import MODEL_SPECS
from evals.selective import selective

CACHED_DISCOUNT = 0.1


def _cases() -> dict:
    out = {}
    for p in glob.glob("evals/cases/*/*.yml"):
        d = yaml.safe_load(open(p))
        for c in (d if isinstance(d, list) else d.get("cases") or []):
            out[c["id"]] = c
    return out


def _pctl(vals, p):
    s = sorted(v for v in vals if v is not None)
    return round(s[max(0, min(len(s) - 1, round(p * (len(s) - 1))))], 2) if s else None


def cell_metrics(rows: list[dict]) -> dict:
    """Everything worth knowing about one (rung, config) cell, from its rows."""
    first = rows[0]
    sel = selective(rows)
    answered = [r for r in rows if not r.get("expected_refuse") and r["outcome"] == "answer"]
    correct_ans = sum(1 for r in answered if r.get("correct"))
    una = [r for r in rows if r.get("expected_refuse") and r["outcome"] != "error"
           and not r.get("needs_judge")]
    fabricated = sum(1 for r in una if r.get("fabricated"))
    # The two families come from `expected_refuse`, which is written from the case's `expect.type`.
    # They used to come from a tier allow-list, which put the one deliberately-answerable control in
    # the `valid_but_wrong` tier on the wrong side and made this table disagree with every other
    # analysis by one question.
    ansf = [r for r in rows if not r.get("expected_refuse")]
    relf = [r for r in rows if r.get("expected_refuse")]
    buckets = Counter(r["bucket"] for r in rows)
    spec = MODEL_SPECS.get(first["model"])
    cached = sum(r.get("cached_tokens", 0) or 0 for r in rows)
    tin = sum(r.get("input_tokens", 0) for r in rows)
    tout = sum(r.get("output_tokens", 0) for r in rows)
    cost = ((tin - cached) * spec.input_price + cached * spec.input_price * CACHED_DISCOUNT
            + tout * spec.output_price) / 1e6 if spec else None
    lat = [r.get("elapsed_s") for r in rows]
    judged = [r for r in rows if r.get("verifier_verdict")]
    j_rej = [r for r in judged if r["verifier_verdict"].get("answers_question") is False]
    refusals = [r for r in rows if r["outcome"] == "refuse"]
    n = len(rows)
    return {
        # what was measured
        "run": first.get("_run"), "rung": first["rung"], "config": first["config"],
        "model": first["model"], "main_reasoning": first.get("main_reasoning"),
        "verifier_model": first.get("verifier_model"),
        "verifier_reasoning": first.get("verifier_reasoning"),
        "verifier_stance": first.get("verifier_stance"),
        "schema_version": first.get("schema_version"),
        "surface_fingerprint": first.get("surface_fingerprint"),
        "n_rows": n, "n_questions": len({r["qid"] for r in rows}),
        "reps": len({r.get("rep") for r in rows}),
        # selective prediction — the three reported metrics, from the one module that defines them
        **sel.as_dict(),
        "precision": round(correct_ans / len(answered), 4) if answered else None,
        "groundedness": round(1 - fabricated / len(una), 4) if una else None,
        "fabrications": fabricated, "n_unanswerable_scored": len(una),
        # the two families — the split the whole series turns on
        "answerable_correct": sum(1 for r in ansf if r.get("correct")), "answerable_n": len(ansf),
        "reliability_correct": sum(1 for r in relf if r.get("correct")), "reliability_n": len(relf),
        # outcomes
        "yield": sum(1 for r in rows if r.get("correct")),
        "score": round(sum(r.get("score", 0) for r in rows), 1),
        **{f"bucket_{b}": buckets.get(b, 0)
           for b in ("right", "wrong", "idk", "other", "deferred", "error")},
        "outcome_answer": sum(1 for r in rows if r["outcome"] == "answer"),
        "outcome_refuse": len(refusals),
        "outcome_clarify": sum(1 for r in rows if r["outcome"] == "clarify"),
        "confident_wrong": sum(1 for r in rows if r.get("confident_wrong")),
        # refusal quality — the typed reject option, scored on WHICH reason
        "refusal_reason_matched": sum(1 for r in refusals if r.get("reason_match") is True),
        "refusal_reason_wrong": sum(1 for r in refusals if r.get("reason_match") is False),
        "over_refused_answerable": sum(1 for r in rows
                                       if not r.get("expected_refuse") and r["outcome"] == "refuse"),
        **{f"refused_by_{g}": sum(1 for r in rows if r.get("refused_by") == g)
           for g in ("governed_numbers", "output_validation", "trajectory_verify")},
        # the judge, where it ran
        "judge_ran": len(judged), "judge_rejected": len(j_rej),
        "judge_role_evidence": sum(1 for r in judged
                                   if (r["verifier_verdict"] or {}).get("value_role") == "evidence"),
        # cost and shape
        "cost_usd": round(cost, 4) if cost is not None else None,
        "input_tokens": tin, "output_tokens": tout, "cached_tokens": cached,
        "tokens_per_question": round((tin + tout) / n),
        "latency_mean_s": round(sum(v for v in lat if v) / n, 2),
        "latency_p50_s": _pctl(lat, 0.5), "latency_p90_s": _pctl(lat, 0.9),
        "tool_calls_per_question": round(sum(r.get("tool_calls", 0) for r in rows) / n, 2),
        "model_calls_per_question": round(sum(len(r.get("turns") or []) for r in rows) / n, 2),
        "iterations_per_question": round(
            sum(r.get("iterations") or 0 for r in rows) / n, 2) if any(
            r.get("iterations") for r in rows) else None,
        # provenance adoption — a declared field the model ignores is not a guarantee
        "source_result_declared": sum(1 for r in rows if r.get("source_result")),
        "value_recovered": sum(1 for r in rows if r.get("value_recovered")),
        "errors": sum(1 for r in rows if r["outcome"] == "error"),
    }


def main() -> None:
    out_dir, run_dirs = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = _cases()

    cells, tiers, tools = [], [], []
    for run_dir in run_dirs:
        rows = []
        for line in (run_dir / "raw.jsonl").open():
            r = json.loads(line)
            r["_run"] = run_dir.name
            rows.append(r)
        by_cell = {}
        for r in rows:
            by_cell.setdefault((r["rung"], r["config"]), []).append(r)
        for (rung, config), rs in sorted(by_cell.items()):
            cells.append(cell_metrics(rs))
            key = {"run": run_dir.name, "rung": rung, "config": config}
            # Grouped by (tier, family), not tier alone: `valid_but_wrong` holds both a set of traps
            # and one answerable control, so a single row per tier would average a question that
            # should be answered together with questions that should be refused.
            grain = {(cases[r["qid"]]["tier"],
                      "reliability" if r.get("expected_refuse") else "answerable") for r in rs}
            for tier, family in sorted(grain):
                trs = [r for r in rs if cases[r["qid"]]["tier"] == tier
                       and ("reliability" if r.get("expected_refuse") else "answerable") == family]
                tiers.append({**key, "tier": tier, "family": family, "n": len(trs),
                              "correct": sum(1 for r in trs if r.get("correct"))})
            calls = Counter(s.get("tool") for r in rs for s in (r.get("steps") or []))
            for tool, k in calls.most_common():
                tools.append({**key, "tool": tool, "calls": k,
                              "calls_per_question": round(k / len(rs), 3)})

    for name, table in (("cells", cells), ("tiers", tiers), ("tools", tools)):
        path = out_dir / f"{name}.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
        print(f"  {path}  {len(table)} rows  {path.stat().st_size/1024:.1f}KB")


if __name__ == "__main__":
    main()
