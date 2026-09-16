"""A finished run, projected onto an observability backend. PROTOTYPE.

WHAT THIS IS AND IS NOT. `raw.jsonl` and `summary.json` are the system of record. This reads them
and emits the same facts in a second shape so a run can be browsed, compared against another run,
and watched for drift. It never writes back, and nothing in `engine/` imports it. `make eval` runs
with no backend configured and loses nothing but the browsing.

WHY REPLAY RATHER THAN LIVE INSTRUMENTATION. Four reasons, and they compound:

  a second write path can disagree with the first; a projection cannot
  the row already stores the whole trace — `turns` is one entry per model call with its latency,
    `steps` every tool call with args and result, `acts` what each guardrail did — so replaying
    loses nothing
  every historical run back-fills, including ones recorded before this file existed
  `regrade_run` recomputes verdicts from immutable model outputs, so a regrade republishes
    corrected scores for free. That is the harness's existing epistemics rather than a new one

WHAT THE BACKEND DOES NOT GET TO OWN. Two things, and both would be downgrades:

  THE PRICE. `ModelSpec.cost` discounts cached input and flags an unconfirmed price. A backend's
    own model table would silently disagree with every published figure, so cost travels as a
    score we computed.
  THE METRICS. Coverage, silent error and balanced accuracy are set-level with pile-aware
    denominators — balanced accuracy averages the piles that HAVE questions. A backend that
    aggregates scores by mean cannot express that, so the run-level numbers are computed here and
    pushed as facts, never recomputed there.

PROTOTYPE STATUS: `render` builds the payload and is exercised by tests. `emit` is not written
yet; the mapping below is the thing worth reviewing before any dependency is added.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["render"]

# What a row's fields become on the backend. Written out rather than inferred, because a mapping
# that lives only in code drifts from what a reader of the dashboard thinks they are looking at.
SCORES = {
    "correct": "boolean — the grader's verdict",
    "silent_error": "boolean — a number served that the reader cannot tell is false",
    "expected_action": "categorical — which pile: answer | refuse | clarify",
    "bucket": "categorical — right | wrong | idk | other | error",
    "cost_usd": "numeric — ours, never the backend's price table",
    "round_trips": "numeric — what a clarification cost the reader",
    "divergence": "numeric — contested only: how far the served reading sat from its rival",
}


def _spans(row: dict) -> list[dict]:
    """The row's stored trace as a span tree.

    Three kinds, and the nesting is the point: a flat list of runs is a searchable table, while a
    tree of the actual model and tool calls in order is what makes a failure legible.
    """
    spans: list[dict] = []
    for i, turn in enumerate(row.get("turns") or []):
        spans.append({"type": "generation", "name": f"model call {i + 1}",
                      "model": row.get("model"), "usage": {
                          "input": turn.get("input_tokens"), "output": turn.get("output_tokens")},
                      "latency_ms": turn.get("ms")})
    for step in row.get("steps") or []:
        spans.append({"type": "tool", "name": step.get("tool"), "input": step.get("args"),
                      "output": str(step.get("result") or step.get("error") or "")[:2000],
                      "level": "ERROR" if step.get("error") else
                               "WARNING" if step.get("blocked_by") else "DEFAULT"})
    for act in row.get("acts") or []:
        spans.append({"type": "event", "name": f"guardrail: {act}"})
    return spans


def render(run_dir: Path) -> dict:
    """The payload a backend would receive for one run. Pure: reads files, returns a dict.

    Kept separate from sending so the mapping can be inspected, diffed and tested without a
    server, a network call or a dependency.
    """
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in (run_dir / "raw.jsonl").open()]
    summary = json.loads((run_dir / "summary.json").read_text())
    meta = summary["meta"]

    # One dataset per question suite, identified by the hash the suite already carries, so a run
    # against an edited suite lands in a different dataset instead of polluting the old one.
    suites = {r.get("suite") for r in rows if r.get("suite")}
    dataset = f"suite-{suites.pop()}" if len(suites) == 1 else "suite-mixed"

    # One dataset RUN per cell. A cell is the thing the experiment varied, so this is the unit a
    # reader compares — arm against arm, rung against rung.
    by_cell: dict = {}
    for r in rows:
        by_cell.setdefault(r.get("config") or r.get("arm") or "default", []).append(r)

    return {
        "dataset": dataset,
        "items": [{"id": r["qid"], "input": r["question"], "expected": r.get("gold"),
                   "metadata": {"tier": r.get("tier"), "pile": r.get("expected_action")}}
                  for r in rows],
        "runs": [{
            "name": cell,
            "metadata": {"model": meta.get("models"), "reps": meta.get("reps"),
                         "surface_fingerprint": rs[0].get("surface_fingerprint"),
                         "schema_version": rs[0].get("schema_version")},
            "traces": [{"item_id": r["qid"], "input": r["question"], "output": r.get("answer"),
                        "spans": _spans(r),
                        "scores": {k: r.get(k) for k in SCORES if r.get(k) is not None}}
                       for r in rs],
            # Computed HERE and pushed as facts. See the module docstring.
            "run_scores": _run_scores(rs, summary, cell),
        } for cell, rs in sorted(by_cell.items())],
    }


def _run_scores(rows, summary, cell) -> dict:
    """The run-level numbers, from our own metrics rather than the backend's aggregation."""
    from .selective import selective

    s = selective(rows)
    out = {"coverage": s.coverage, "silent_error": s.silent_error,
           "balanced_accuracy": s.balanced_accuracy, "n_questions": len({r["qid"] for r in rows})}
    # The interval belongs beside the point estimate or the point estimate reads as exact.
    for model in summary.get("cells", {}).values():
        u = (model.get(cell) or {}).get("uncertainty") or {}
        for name in ("coverage", "silent_error", "balanced_accuracy"):
            e = u.get(name) or {}
            if e.get("lo") is not None:
                out[f"{name}_lo"], out[f"{name}_hi"] = e["lo"], e["hi"]
    return out
