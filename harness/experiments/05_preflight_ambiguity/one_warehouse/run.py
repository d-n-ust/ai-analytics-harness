#!/usr/bin/env python3
"""The experiment: one warehouse, two arms, one agent that has both tools.

The agent is grounded on a dbt-shaped project — models AND a metrics layer over those models — and
may either call a governed metric or write SQL, which is what an agent does in a real project. So
one run measures both floors at once: a wrong METRIC where the layer governs the concept, and a
wrong TABLE or COLUMN where it does not.

    python run.py --model gpt-5-mini --reps 1                    # a full pass
    python run.py --model gpt-5-mini --reps 1 --case <id> ...    # probe one question, no overwrite
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import warehouses
import yaml
from agent.runtime.grounding import build_grounding
from agent.runtime.loop import Answer, run_agent
from agent.runtime.providers import get_model, get_verifier
from agent.core.rungs import capabilities
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.selective import selective
from warehouse.warehouse import open_warehouse, set_star
from warehouse.warehouse import cursor as scoped_cursor

HERE = pathlib.Path(__file__).resolve().parent
ARMS = [("before", warehouses.BEFORE), ("after", warehouses.AFTER)]
RUNG = 3  # star + governed semantic layer, and raw SQL still available: the real project's shape

# A pick of a same-valued governed duplicate is a CORRECT selection: the duplicate returns the same
# number by construction, so it is sprawl noise rather than a wrong number.
SELECTION_EQUIVALENT = {"mrr": {"monthly_recurring_revenue"}, "value_moments": {"total_moments"}}


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for c in cases:
        _validate(c, "cases.yml")
    return cases


def _marks(marker: str, sql: str) -> bool:
    """A grounding marker is a substring, or a regex when written `re:<pattern>`. The regex form
    exists because a table name can be a prefix of its twin: `dim_users` must match `from dim_users;`
    and never `dim_users_v2`."""
    return bool(re.search(marker[3:], sql)) if marker.startswith("re:") else marker.lower() in sql


def _sql_of(ans) -> str:
    return " ".join(s.get("args", {}).get("query", "") for s in (getattr(ans, "steps", []) or [])
                    if s.get("tool") == "run_sql").lower()


def _queried_calls(ans) -> list[dict]:
    calls = []
    for s in getattr(ans, "steps", []) or []:
        if s.get("tool") == "query_metric" and isinstance(s.get("args"), dict):
            a = s["args"]
            calls.append({k: a[k] for k in ("metric", "period", "start", "end", "time_grain", "filters")
                          if a.get(k) is not None})
    return calls


def _metric_behind_value(ans) -> str | None:
    """The metric whose returned value IS the declared answer, or None.

    Strict on purpose: an agent that explores a metric and then answers from SQL did not ground on
    that metric, and attributing the answer to it turns a correct SQL answer into a false wrong
    selection."""
    declared = getattr(ans, "declared_value", None)
    if declared is None:
        return None
    for s in reversed(getattr(ans, "steps", []) or []):
        if s.get("tool") != "query_metric" or not isinstance(s.get("args"), dict):
            continue
        for tok in re.findall(r"-?\d+(?:\.\d+)?", str(s.get("result", ""))):
            try:
                if abs(float(tok) - float(declared)) <= 1e-6 * max(1.0, abs(float(declared))):
                    return s["args"].get("metric")
            except ValueError:
                continue
    return None


def _picked_metric(ans) -> str | None:
    """The metric the answer came from, falling back to the last one queried when no result matches
    the declared value (the model may round, or state the number only in prose)."""
    metrics = [c["metric"] for c in _queried_calls(ans) if c.get("metric")]
    return _metric_behind_value(ans) or (metrics[-1] if metrics else None)


def _wrong_grounding(case: dict, ans, arm: str) -> bool:
    """Did the answer ground on the wrong thing? Two routes, because the agent has two tools.

    A metric question is judged by the metric the answer came from. A question the layer does not
    cover is judged from the SQL, where a wrong marker counts only when no right marker is present
    (an agent that peeks at the leftover table and answers from the current one grounded correctly).

    SQL markers apply to the BEFORE arm only. They name decoys, and the decoys are what the repair
    removes: after it, `dim_users` is not the stale twin of anything, it is the one users table.
    Carrying the marker across would score the fixed warehouse against a table that no longer
    exists.
    """
    expected = case["expect"].get("metric")
    picked = _picked_metric(ans)
    if expected and picked:
        return picked != expected and picked not in SELECTION_EQUIVALENT.get(expected, set())
    # The layer governs no metric for this question, so answering FROM one is grounding on
    # something that does not mean what was asked — the same defect as picking the wrong metric,
    # and it happens: asked for subscription starts, the agent reached for `subscribers`.
    if case["expect"].get("no_governed_metric"):
        return _metric_behind_value(ans) is not None or (
            arm == "before" and _wrong_by_sql(case, _sql_of(ans)))
    return arm == "before" and _wrong_by_sql(case, _sql_of(ans))


def _wrong_by_sql(case: dict, sql: str) -> bool:
    """A wrong marker counts only when no right marker is present: an agent that peeks at the
    leftover table and answers from the current one grounded correctly."""
    wrong = any(_marks(w, sql) for w in (case.get("wrong_grounding") or []))
    right = any(_marks(r, sql) for r in (case.get("right_grounding") or []))
    return wrong and not right


def run_arm(con, arm: str, schema: str, cases, golds, model, verifier, reps: int,
            concurrency: int) -> list[dict]:
    spec = HERE / "layers" / arm
    cursor_lock, print_lock = threading.Lock(), threading.Lock()

    def one(task):
        rep, idx, case = task
        with cursor_lock:
            cur = scoped_cursor(con)
        try:
            cur.execute(f"SET search_path = '{schema}'")   # the agent sees ONLY this arm
            g = build_grounding(cur, rung=RUNG, spec_path=spec, engine="metricflow",
                                semantic_layer=True, schema=schema)
            try:
                ans = run_agent(case["question"], g, model, verifier_model=verifier)
            except Exception as exc:  # noqa: BLE001 — one failed call must not kill the arm
                ans = Answer(case["question"], RUNG, model.spec.name, None,
                             outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
        finally:
            cur.close()
        row = {**grade(ans, case, golds.get(case["id"])),
               "outcome": ans.outcome, "id": case["id"], "tier": case["tier"],
               "family": case.get("family"), "rep": rep,
               "picked": _picked_metric(ans), "calls": _queried_calls(ans),
               "sql": _sql_of(ans), "wrong_grounding": _wrong_grounding(case, ans, arm),
               "expected_metric": case["expect"].get("metric"),
               "declared": getattr(ans, "declared_value", None)}
        with print_lock:
            print(f"  [{arm} rep{rep}] {'OK ' if row.get('correct') else 'x  '} {case['id']}", flush=True)
        return rep, idx, row

    tasks = [(rep, i, c) for rep in range(reps) for i, c in enumerate(cases)]
    if concurrency <= 1:
        results = [one(t) for t in tasks]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(pool.map(one, tasks))
    return [r for _, _, r in sorted(results, key=lambda t: (t[0], t[1]))]


def metrics(rows: list[dict]) -> dict:
    s = selective(rows)
    ans = [r for r in rows if r["outcome"] == "answer"]
    wsel = sum(1 for r in ans if r.get("wrong_grounding"))
    wcon = sum(1 for r in ans if not r.get("wrong_grounding") and not r.get("correct"))
    return {"n": s.n, "coverage": s.coverage, "silent_error": s.silent_error,
            "correct": (sum(1 for r in rows if r.get("correct")) / len(rows)) if rows else float("nan"),
            "wrong_selection_rate": (wsel / len(ans)) if ans else float("nan"),
            "wrong_construction_rate": (wcon / len(ans)) if ans else float("nan")}


def _f(x) -> str:
    return " n/a " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:5.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--case", nargs="*", help="run only these case ids (probe mode, own result file)")
    ap.add_argument("--arm", nargs="*", choices=("before", "after"))
    args = ap.parse_args()

    cases = load_cases()
    probe = bool(args.case or args.arm)
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"unknown case id(s): {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in args.case]

    con = open_warehouse(create_star_views=True)
    set_star(con, capabilities(RUNG).star)
    from benefit import ensure_mf_views          # the snapshot views both arms read
    ensure_mf_views(con)
    warehouses.build(con)
    golds = compute_gold(con, cases)             # gold resolves against the clean star
    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)

    arms = [(n, s) for n, s in ARMS if not args.arm or n in args.arm]
    report: dict = {"model": ("mock" if args.mock else args.model), "reps": args.reps, "arms": {}}
    out = HERE / (f"result__probe__{args.model}.json" if probe else f"result__{args.model}.json")
    for name, schema in arms:
        rows = run_arm(con, name, schema, cases, golds, model, verifier, args.reps, args.concurrency)
        report["arms"][name] = {"overall": metrics(rows),
                                "flagged": metrics([r for r in rows if r["tier"] == "flagged"]),
                                "clean": metrics([r for r in rows if r["tier"] == "clean"]),
                                "rows": rows}
        out.write_text(json.dumps(report, indent=2, default=str))
        if probe:
            for r in rows:
                calls = "; ".join(f"{c.get('metric')}({c.get('period') or 'no period'})" for c in r["calls"])
                print(f"    [{name}] {r['id']} rep{r['rep']} correct={r.get('correct')} "
                      f"picked={r.get('picked')} wrong_ground={r.get('wrong_grounding')} "
                      f"declared={r.get('declared')} gold={golds.get(r['id'])}")
                if calls:
                    print(f"      metrics: [{calls}]")
                if r["sql"]:
                    print(f"      sql: {' '.join(r['sql'].split())[:260]}")

    print(f"\n  ONE WAREHOUSE — before/after  ({report['model']}, reps={args.reps})")
    print("  " + "-" * 92)
    print(f"  {'arm':8} {'set':8} {'n':>3} {'correct':>8} {'SER':>6} {'coverage':>9}  |  "
          f"{'w-SELECT':>9} {'w-CONSTR':>9}")
    print("  " + "-" * 92)
    for name, _ in arms:
        for label in ("overall", "flagged", "clean"):
            m = report["arms"][name][label]
            if m["n"] == 0:
                continue
            print(f"  {name if label == 'overall' else '':8} {label:8} {m['n']:>3} {_f(m['correct']):>8} "
                  f"{_f(m['silent_error']):>6} {_f(m['coverage']):>9}  |  "
                  f"{_f(m['wrong_selection_rate']):>9} {_f(m['wrong_construction_rate']):>9}")
        print("  " + "·" * 92)
    print(f"\n  wrote {out.name}")


if __name__ == "__main__":
    main()
