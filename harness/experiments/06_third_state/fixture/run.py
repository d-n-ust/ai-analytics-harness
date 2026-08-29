#!/usr/bin/env python3
"""Ask the contested question and show what the agent actually did.

This is the demonstration runner, not the experiment runner. It asks ONE question a few times and
prints the whole path: the tools the agent was offered, the catalogue it read, every call it made,
the terminal action it chose, and how that action grades. The point is to see the failure rather
than to read a rate — with one question and a handful of reps there is no rate worth reading.

The agent is grounded at rung 3 on the MetricFlow layer under `layer/`, holding both
`query_metric` and `run_sql`, which is the shape a real project has: it reaches for a governed
metric when one fits and writes SQL when none does.

    python run.py --mock                       # no API key, no cost — check the plumbing
    python run.py --model gpt-5-mini --reps 5  # the real thing
    python run.py --model gpt-5-mini --reps 5 --json out.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import yaml
from agent.grounding import build_grounding
from agent.guardrails import parse_cell
from agent.loop import Answer, run_agent
from agent.providers import get_model
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.matrix import render as render_matrix
from evals.selective import selective
from warehouse.warehouse import cursor as scoped_cursor
from warehouse.warehouse import open_warehouse

import build as fixture_build

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE / "layer"

# TWO WAREHOUSES OVER THE SAME RAW DATA. `base` is the one every number in this experiment was
# measured against and it does not change: a rebuilt fixture is not a comparison. `kimball` models
# the balances as balances — see kimball/README.md — and exists to separate the definitional
# conflicts that are organisational from the ones that were modelling debt.
WAREHOUSES = {"base":    (None,                  "wh_06",  HERE / "layer"),
              "kimball": (HERE / "kimball/models", "wh_06k", HERE / "kimball/layer")}
RUNG = 3          # star + governed semantic layer, raw SQL still on the table

# The three shapes a question can have, as the grader names them. Kept here so the runner's own
# labels cannot drift from `selective.py`'s piles.
_PILE = {"metric_answer": "A", "refuse": "B", "contested": "C"}


def load_cases(name: str = "cases.yml", warehouse: str = "base") -> list[dict]:
    """The suite to run. `heldout.yml` exists because every guardrail here was chosen after watching
    `cases.yml` fail, so that file measures fit rather than generalisation.

    A case may carry `overrides: {<warehouse>: <expect>}`, and the whole `expect` block is REPLACED
    rather than merged. Most questions mean the same thing on both warehouses and carry no override;
    the ones that do are the subscription metrics, where the corrected model changes what a question
    is asking — and a merge would leave `candidates` behind when `type` changes from `contested` to
    `metric_answer`, which is exactly the case that needs the override.
    """
    cases = yaml.safe_load((HERE / name).read_text())["cases"]
    out = []
    for case in cases:
        override = (case.pop("overrides", None) or {}).get(warehouse)
        if override:
            case = {**case, "expect": override}
        _validate(case, f"{name} [{warehouse}]")
        out.append(case)
    return out


def _render_step(step: dict) -> str:
    """One tool call, on one line. Results are truncated: what matters here is which call was made
    and whether anything stopped it, not the payload."""
    args = {k: v for k, v in (step.get("args") or {}).items() if v not in (None, "", [], {})}
    shown = ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:4])
    outcome = "blocked" if step.get("blocked_by") else ("error" if step.get("error") else "ok")
    result = str(step.get("result") or "")[:90].replace("\n", " ")
    return f"    {step.get('tool'):16} {shown[:88]:88} [{outcome}]  {result}"


def demonstrate(answer: Answer, case: dict, gold, graded: dict) -> None:
    print(f"\n  tool calls ({len(answer.steps)}):")
    for step in answer.steps:
        print(_render_step(step))
    print(f"\n  terminal action : {answer.outcome}")
    if answer.outcome == "answer":
        print(f"  served          : {answer.declared_value}  "
              f"(source_metric={answer.source_metric!r})")
        print(f"  text            : {(answer.answer or '')[:400]}")
        print(f"  explanation     : {(answer.explanation or '')[:400]}")
    else:
        print(f"  reason          : {answer.reason}")
        if answer.outcome == "clarify":
            named = list(getattr(answer, "candidates", ()) or ())
            print(f"  candidates      : {named or '(none named — the bare tool cannot carry them)'}")
        print(f"  text            : {(answer.explanation or '')[:200]}")
    served = graded.get("served_candidate")
    div = graded.get("divergence")
    print(f"\n  GRADED          : correct={graded['correct']}  bucket={graded['bucket']}  "
          f"silent_error={bool(graded['confident_wrong'])}")
    if served:
        print(f"  served reading  : {served}   {div * 100:.2f}% from the one it was chosen over")
    elif answer.outcome == "answer":
        print("  served reading  : matched neither governed definition")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--mock", action="store_true", help="scripted model: no API key, no cost")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--cell", default=None,
                    help="guardrail cell, e.g. R1 or R9. Default: the loop's own default set.")
    ap.add_argument("--variant", default=None,
                    help="a generated layer variant (see variants.py). Default: the shipped layer.")
    ap.add_argument("--catalogue", default="full", choices=("full", "compact"),
                    help="how the metric list is laid out. `compact` puts every name and "
                         "description contiguous and the dimension detail in a second block — "
                         "same facts, different adjacency.")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="threads over (rep, question) tasks. Safe because nothing writes: models "
                         "are built before the pool starts and each worker takes its own cursor.")
    ap.add_argument("--warehouse", default="base", choices=sorted(WAREHOUSES),
                    help="which warehouse and layer to run against (see kimball/README.md)")
    ap.add_argument("--cases", default="cases.yml",
                    help="which suite to run: cases.yml (the original, now partly a training set) "
                         "or heldout.yml (authored after the mechanisms were frozen)")
    ap.add_argument("--only", default=None, help="comma-separated case ids, to probe one question")
    ap.add_argument("--json", dest="out", default=None, help="write the graded rows here")
    args = ap.parse_args()

    models_root, schema, layer = WAREHOUSES[args.warehouse]
    if args.variant:
        if args.warehouse != "base":
            sys.exit("--variant varies the BASE layer's presentation; it has no counterpart here")
        layer = HERE / "variants" / args.variant
    if not layer.is_dir():
        sys.exit(f"{layer} does not exist — run `python variants.py --write` first")
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, root=models_root, schema=schema)   # so the layer has something to read
    cases = load_cases(args.cases, args.warehouse)
    golds = compute_gold(con, cases)             # resolves each candidate's own oracle
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only.split(","))]

    guardrails = parse_cell(args.cell) if args.cell else None
    model = get_model(args.model, mock=args.mock)

    for case in cases:
        pile = _PILE[case["expect"]["type"]]
        print(f"pile {pile}     : {case['question']}")
        for cand in case["expect"].get("candidates") or ():
            print(f"    {cand['metric']:18} = {cand['value']:>10,.0f}   owner {cand['owner']:10} "
                  f"→ {cand['consumer']}")
    print(f"\nmodel      : {model.spec.name}   rung {RUNG}   "
          f"guardrails {args.cell or 'loop default'}   layer {args.variant or 'shipped'}   "
          f"catalogue {args.catalogue}   reps {args.reps}   warehouse {args.warehouse}")

    # CONCURRENCY IS THREADS, NOT PROCESSES, and the distinction is the whole reason it is safe.
    # Two PROCESSES cannot write one DuckDB file, but nothing here writes: the models are built once
    # above, before the pool starts, and the time spine the MetricFlow engine needs is created under
    # its own lock. What each worker needs is its own CURSOR — a shared connection object is not
    # thread-safe — taken under a lock, which is the pattern evals/runner.py and experiment 05
    # already use. The provider SDK clients are thread-safe, so one model object serves every worker.
    # A single named case at a single rep is a DIAGNOSIS, not a measurement, and the one-line-per-run
    # summary is the wrong output for it. Nothing to ask for: the request already said which.
    trace = bool(args.only) and len(cases) == 1 and args.reps == 1

    cursor_lock = threading.Lock()
    print_lock = threading.Lock()
    shown: set = set()

    def one(task):
        rep, idx, case = task
        with cursor_lock:
            cur = scoped_cursor(con)
        try:
            grounding = build_grounding(cur, rung=RUNG, spec_path=layer, engine="metricflow",
                                        semantic_layer=True, guardrails=guardrails)
            grounding.semantic.catalogue = args.catalogue
            with print_lock:
                if not shown:
                    shown.add(True)
                    offered = [s["name"] for s in grounding.toolbox.specs()]
                    print(f"\ntools offered ({len(offered)}): {', '.join(offered)}")
                    print("metrics in the catalogue: "
                          f"{', '.join(sorted(grounding.toolbox.semantic.metrics))}\n")
            try:
                answer = run_agent(case["question"], grounding, model)
            except Exception as exc:                                       # noqa: BLE001
                answer = Answer(case["question"], RUNG, model.spec.name, None,
                                outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
        finally:
            cur.close()
        graded = grade(answer, case, golds[case["id"]])
        if trace:                       # one named case, one rep: show the whole run, not a line
            with print_lock:
                demonstrate(answer, case, golds[case["id"]], graded)
        pile = _PILE[case["expect"]["type"]]
        with print_lock:
            mark = "OK  " if graded["correct"] else "MISS"
            served = "" if answer.declared_value is None else f"{answer.declared_value:,.1f}"
            print(f"  rep {rep + 1}  pile {pile}  {case['id']:40} {answer.outcome:8} {mark} {served}"
                  + (f"  {answer.error}" if answer.error else ""))
        # Recorded because the score alone cannot separate "the mechanism worked" from "the model
        # had a good day": a fix aimed at tool errors is measured by tool errors, which vary far
        # less than the graded outcome does.
        return rep, idx, {**graded, "outcome": answer.outcome, "id": case["id"],
                          # Header fields cli/trace.py needs to render a stored row without the
                          # run that produced it. A trace you can only see live is a trace you
                          # cannot go back to when a number looks wrong.
                          # The exception text, because a row that says outcome=error and nothing
                          # else cannot be diagnosed without re-running, and re-running is a
                          # different sample.
                          "error": answer.error,
                          "question": case["question"], "rung": RUNG, "model": model.spec.name,
                          "config": args.cell or "loop default",
                          "rep": rep, "declared": answer.declared_value,
                          "source_metric": answer.source_metric,
                          "tool_calls": len(answer.steps),
                          "tool_errors": sum(1 for s in answer.steps if s.get("error")),
                          "handbacks": len(answer.repairs),
                          "acts": [a.get("guardrail") for a in (answer.acts or [])],
                          # The served TEXT, because several checks are about what the reader
                          # receives and cannot be evaluated from a graded row without it.
                          "answer_text": answer.answer, "explanation": answer.explanation,
                          # A compact trace on the row, so a failure can be diagnosed from stored
                          # results instead of re-run. Re-running gives a DIFFERENT sample, which
                          # is the wrong thing to diagnose when the question is why THIS run failed.
                          "steps": [{"tool": s.get("tool"), "args": s.get("args"),
                                     "error": bool(s.get("error")),
                                     "blocked": bool(s.get("blocked_by")),
                                     "result": str(s.get("result") or s.get("error") or "")[:300]}
                                    for s in answer.steps]}

    tasks = [(rep, i, c) for rep in range(args.reps) for i, c in enumerate(cases)]
    if args.concurrency <= 1:
        results = [one(task) for task in tasks]
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(one, tasks))
    # Sorted, so the stored rows do not depend on which worker finished first.
    rows = [row for _, _, row in sorted(results, key=lambda t: (t[0], t[1]))]

    score = selective(rows).as_dict()
    print(f"\n{'═' * 100}\nover {len(rows)} attempt(s) across {len(cases)} question(s)")
    print(f"  pile A  answerable   n={score['answerable_n']:<3} right={score['answerable_right']:<3} "
          f"wrong={score['answerable_wrong']:<3} did-not-attempt={score['answerable_over_refused']:<3} "
          f"(of which asked: {score['over_clarification_rate']:.0%})")
    print(f"  pile B  unanswerable n={score['unanswerable_n']:<3} refused={score['unanswerable_refused']:<3} "
          f"served={score['unanswerable_served']}")
    print(f"  pile C  contested    n={score['contested_n']:<3} clarified={score['contested_clarified']:<3} "
          f"served={score['contested_served']:<3} refused={score['contested_refused']}")
    print(f"\n  coverage {score['coverage']}   silent_error {score['silent_error']}   "
          f"balanced_accuracy {score['balanced_accuracy']}")
    # The grid, with the answered column split: an action-only 3x3 puts a right number and a
    # plausible wrong one in the same cell, and then reports a diagonal nobody should trust.
    print()
    print(render_matrix(rows))
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2, default=str))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
