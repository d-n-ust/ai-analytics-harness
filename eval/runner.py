"""Run the whole experiment: every question, every rung / guardrail config, every model.
Grade each response, then hand the rows to report.write (which emits summary.md +
summary.json). The model and the question set are frozen; only the grounding rung or the
guardrail config changes, so the deltas are attributable to that, not to prompt luck.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from agent.orchestrator import Answer, run_agent
from agent.prompt import RUNG_NAMES, build_grounding
from agent.models import MODEL_SPECS, get_model
from warehouse.warehouse import open_warehouse, set_star

from .gold import compute_gold, load_questions
from .grade import grade
from . import report

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
# Bumped when the raw-row schema changes, so a stored run is self-describing and downstream
# tooling (regrade, report, attribution) can detect skew. v2 adds the treatment fields
# (main_reasoning / verifier_model / verifier_reasoning).
ROW_SCHEMA_VERSION = 2


def _new_run_dir(models, mock: bool) -> Path:
    """Every run gets its own directory; nothing ever overwrites a previous run.
    (The v1 layout wrote results/raw.jsonl in place — one `make smoke` destroyed
    the published run's rows.)"""
    label = "mock" if mock else "-".join(models)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RESULTS_DIR / "runs" / f"{stamp}-{label}"
    run_dir.mkdir(parents=True)
    latest = RESULTS_DIR / "latest"
    latest.unlink(missing_ok=True)
    latest.symlink_to(run_dir.relative_to(RESULTS_DIR), target_is_directory=True)
    return run_dir


def run_experiment(mock: bool = False, models=("gpt-5.6-terra", "gpt-5.4-mini"), rungs=(1, 2, 3, 4, 5, 6),
                   only=None, sample: int | None = None, repeats: int = 1,
                   rrungs=(1,), cells=None, reasoning: str | None = None) -> None:
    from agent.guardrails import LADDER, incoherent, parse_cell
    con = open_warehouse(create_star_views=True)
    golds = compute_gold(con)
    questions = load_questions()
    if only:  # a hand-picked subset of question ids
        keep = set(only)
        questions = [q for q in questions if q["id"] in keep]
    elif sample:  # the first N questions per tier
        seen: dict = defaultdict(int)
        subset = []
        for q in questions:
            if seen[q["tier"]] < sample:
                subset.append(q)
                seen[q["tier"]] += 1
        questions = subset

    # A "config" is (label, nominal-rrung, guardrails). --cells overrides the ladder presets with
    # arbitrary ablation cells (R9-resolve, ...), skipping the ones incoherent() rejects.
    if cells:
        configs = []
        for spec in cells:
            g = parse_cell(spec)
            bad = incoherent(g)
            if bad:
                print(f"  SKIP incoherent cell {spec}: {bad}", flush=True)
                continue
            base = spec.split("-")[0]                      # nominal rrung, for the row; label() is the truth
            nominal = int(base[1:]) if base.startswith("R") and base[1:].isdigit() else 9
            configs.append((g.label(), nominal, g))
    else:
        configs = [(f"R{rr}", rr, LADDER[rr]) for rr in rrungs]

    rows: list[dict] = []
    run_dir = _new_run_dir(models, mock)
    raw_f = (run_dir / "raw.jsonl").open("w")  # written incrementally, so a stop keeps progress
    # Reasoning effort is a treatment variable — an explicit run parameter (falling back to the
    # OPENAI_REASONING env for back-compat), recorded on every row rather than left implicit.
    main_reasoning = reasoning if reasoning is not None else os.environ.get("OPENAI_REASONING", "none")
    verifier_reasoning = os.environ.get("VERIFIER_REASONING", "low")
    for model_name in models:
        model = get_model(model_name, mock=mock, reasoning=main_reasoning)
        # The trajectory verifier (R9) runs as a careful checker at its own reasoning level,
        # independent of the main agent — a minimal-reasoning main agent must not make a
        # minimal-reasoning verifier (which false-refuses and misses). Default 'low'.
        # VERIFIER_MODEL lets the checker be a *different* model than the worker; defaults to the worker.
        verifier_used = os.environ.get("VERIFIER_MODEL") or model_name
        verifier_model = get_model(verifier_used, mock=mock, reasoning=verifier_reasoning)
        for rung in rungs:
            set_star(con, rung >= 2)
            for cfg_label, rrung, gr in configs:
                grounding = build_grounding(con, rung, guardrails=gr)
                for rep in range(repeats):
                    for q in questions:
                        t0 = time.perf_counter()
                        try:
                            ans = run_agent(q["question"], grounding, model, verifier_model=verifier_model)
                        except Exception as exc:  # noqa: BLE001 — one bad question shouldn't kill the run
                            # Record the exception TYPE so a persistent API failure (RateLimitError,
                            # APITimeoutError — after the SDK's retries are exhausted) is distinguishable
                            # from a code bug (KeyError, …) when analysing error rows.
                            ans = Answer(q["question"], rung, model_name, None,
                                         outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
                        elapsed_s = time.perf_counter() - t0   # wall-clock per run, for per-rung latency
                        g = grade(ans, q, golds[q["id"]])
                        rows.append({
                            "qid": q["id"], "tier": q["tier"], "rung": rung, "rrung": rrung,
                            "config": grounding.guardrails.label(),
                            "model": model_name, "rep": rep,
                            "question": q["question"], "gold": golds[q["id"]],
                            "answer": ans.answer, "explanation": ans.explanation,
                            "outcome": ans.outcome, "reason": ans.reason, "missing": ans.missing,
                            "correct": g["correct"], "executed": g["executed"],
                            "abstained": g["abstained"], "confident_wrong": g["confident_wrong"],
                            "fabricated": g["fabricated"], "needs_judge": g.get("needs_judge", False),
                            "bucket": g["bucket"], "expected_refuse": g["expected_refuse"],
                            "reason_match": g["reason_match"], "metric_match": g.get("metric_match"),
                            "source_metric": ans.source_metric,
                            "declared_value": ans.declared_value,
                            "verifier_verdict": ans.verifier_verdict, "score": g["score"],
                            "driver_ok": g.get("driver_ok"), "cause_ok": g.get("cause_ok"),
                            "tool_calls": ans.tool_calls, "input_tokens": ans.input_tokens,
                            "output_tokens": ans.output_tokens, "error": ans.error,
                            "elapsed_s": round(elapsed_s, 3), "steps": ans.steps,
                            "schema_version": ROW_SCHEMA_VERSION,
                            "main_reasoning": getattr(model, "reasoning", None),
                            "verifier_model": verifier_used, "verifier_reasoning": verifier_reasoning,
                        })
                        raw_f.write(json.dumps(rows[-1], default=str) + "\n")
                        raw_f.flush()
                        mark = {"refuse": "~", "clarify": "?"}.get(
                            ans.outcome, "✓" if g["correct"] else "✗")
                        print(f"  [{model_name} r{rung} {cfg_label} rep{rep} {q['tier'][:4]}] {mark} {q['id']}", flush=True)

    raw_f.close()
    report.write(rows, run_dir, mock=mock)


def regrade_run(run_dir: Path) -> None:
    """Re-grade a finished run from its stored answers (no model calls) and regenerate
    its summary. This is how a grade.py change reaches every past number — the model
    outputs are immutable; only the verdicts derived from them change."""
    from .gold import load_questions
    qmap = {q["id"]: q for q in load_questions()}
    raw = run_dir / "raw.jsonl"
    rows = [json.loads(line) for line in raw.open()]
    for r in rows:
        ans = Answer(question=r["question"], rung=r["rung"], model=r["model"],
                     answer=r["answer"], explanation=r.get("explanation", "") or "",
                     outcome=r.get("outcome", "answer"), reason=r.get("reason"),
                     missing=r.get("missing"), error=r.get("error"))
        g = grade(ans, qmap[r["qid"]], r.get("gold"))
        r.update({k: g[k] for k in ("correct", "executed", "abstained", "confident_wrong",
                                    "fabricated", "needs_judge", "bucket", "expected_refuse",
                                    "reason_match", "driver_ok", "cause_ok", "score")})
    with raw.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    report.write(rows, run_dir, mock=False)
    print(f"regraded {len(rows)} rows in {run_dir}")
