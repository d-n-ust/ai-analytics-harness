#!/usr/bin/env python3
"""Experiment 05 benefit runner — the before/after measurement.

Run the analytics agent on each of the four semantic layers over the pre-registered question set
(`cases.yml`) and report the harness's own indicators — silent-error rate, balanced accuracy, and
coverage — overall and split flagged vs clean.

Everything is held constant across the four runs except the semantic layer the agent is shown: the
same warehouse, the same questions, the same independent gold. So a difference in the agent's silent
errors is caused by the layer's ambiguity — the runtime harm preflight predicts statically. The
dose-response is small (governed, 1 finding) -> high (sprawled, 18); the fix is the `_after` layer.

    python benefit.py --mock                     # validate the wiring end to end, no API key
    python benefit.py                            # a real run (needs ANTHROPIC_API_KEY; default haiku)
    python benefit.py --model claude-sonnet-5    # a real run on the larger model
    python benefit.py --only small_before high_before   # a subset of layers

Gold, questions, and scoring all run offline; only a non-mock agent needs a key.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import threading
from concurrent.futures import ThreadPoolExecutor

import yaml

from agent.grounding import build_grounding
from agent.loop import Answer, run_agent
from agent.providers import get_model, get_verifier
from agent.rungs import capabilities
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.selective import selective
from warehouse.warehouse import STAR_SCHEMA, open_warehouse, set_star
from warehouse.warehouse import cursor as scoped_cursor

HERE = pathlib.Path(__file__).resolve().parent
LAYERS = HERE / "layers"
ORDER = ["small_before", "small_after", "high_before", "high_after", "high_after2", "high_after3"]
# high_after2 = high_after plus exactly three stated-default sentences on the metrics whose
# after-arm answers still failed (new_signups scope, active_users default window, active_habits
# stock semantics). It tests whether the construction residual is agent skill or missing spec.
RUNG = 3  # star + governed semantic layer — the rung where metric selection is the agent's job


def load_cases(cases_path: pathlib.Path) -> list[dict]:
    cases = yaml.safe_load(cases_path.read_text())["cases"]
    for c in cases:
        _validate(c, cases_path.name)  # same validator the frozen set uses, so expected_refuse is set right
    return cases


def ensure_mf_views(con) -> None:
    """Views the MetricFlow layers need, created over the warehouse (no rows copied). Harmless for the
    harness engine. (1) A one-row-per-day time spine, for any time-filtered query. (2) A monthly HABIT
    snapshot, so active_habits can be a proper stock (active as of each month-end) instead of a naive
    count over created_date that a stray period would shrink."""
    con.execute(f'''CREATE OR REPLACE VIEW "{STAR_SCHEMA}".mf_time_spine AS
        SELECT CAST(d AS DATE) AS ds FROM (SELECT UNNEST(generate_series(
            (SELECT min(active_date) FROM "{STAR_SCHEMA}".agg_active_days),
            (SELECT max(active_date) FROM "{STAR_SCHEMA}".agg_active_days), INTERVAL 1 DAY)) AS d)''')
    con.execute(f'''CREATE OR REPLACE VIEW "{STAR_SCHEMA}".fct_habit_months AS
        SELECT m.snapshot_month, h.habit_id, h.category
        FROM (SELECT DISTINCT date_trunc('month', active_date)::DATE AS snapshot_month
              FROM "{STAR_SCHEMA}".agg_active_days) m
        JOIN "{STAR_SCHEMA}".dim_habits h ON h.created_date < m.snapshot_month + INTERVAL 1 MONTH
            AND (h.archived_date IS NULL OR h.archived_date >= m.snapshot_month + INTERVAL 1 MONTH)''')
    # Kimball-named aliases for the high_after3 arm: the grain word is the loudest part of the name
    # (periodic snapshot vs accumulating-snapshot term table). Aliases, not renames — gold_sql and
    # every other arm keep the original names.
    con.execute(f'''CREATE OR REPLACE VIEW "{STAR_SCHEMA}".fct_subscription_month_snapshot AS
        SELECT * FROM "{STAR_SCHEMA}".fct_subscription_months''')
    con.execute(f'''CREATE OR REPLACE VIEW "{STAR_SCHEMA}".fct_habit_month_snapshot AS
        SELECT * FROM "{STAR_SCHEMA}".fct_habit_months''')
    con.execute(f'''CREATE OR REPLACE VIEW "{STAR_SCHEMA}".fct_subscription_term AS
        SELECT * FROM "{STAR_SCHEMA}".fct_subscriptions''')


def _queried_metrics(ans) -> list[str]:
    """The governed metrics the agent actually queried, read from its query_metric tool calls in the
    trace. source_metric is only DECLARED at rung 7; at rung 3 we OBSERVE the pick from what the agent
    did, so a wrong number can be attributed to a wrong metric selection rather than merely inferred."""
    out = []
    for s in getattr(ans, "steps", []) or []:
        if s.get("tool") == "query_metric" and isinstance(s.get("args"), dict):
            m = s["args"].get("metric")
            if m:
                out.append(m)
    return out


def _queried_calls(ans) -> list[dict]:
    """Every query_metric call with its time arguments, verbatim. Added after a failure whose
    period argument could only be RECONSTRUCTED by matching the declared value against candidate
    windows (553 = last_month = June, asked for April): the row must carry what was actually
    passed, so a wrong window is read from the trace, never inferred. `filters` joined the list
    after a wave-2 failure that was invisible without it: the agent queried the right metric,
    then re-queried with filters={'user__is_internal': 'False'} and served the narrowed number —
    a self-applied scope change no other recorded argument shows."""
    calls = []
    for s in getattr(ans, "steps", []) or []:
        if s.get("tool") == "query_metric" and isinstance(s.get("args"), dict):
            a = s["args"]
            calls.append({k: a[k] for k in ("metric", "period", "start", "end", "time_grain", "filters")
                          if a.get(k) is not None})
    return calls


def run_layer(con, spec_path, cases, golds, model, verifier, reps: int = 1,
              engine: str = "harness", guardrails=None, concurrency: int = 1) -> list[dict]:
    """The agent answers every question grounded on ONE semantic layer, `reps` times; each answer is
    graded into the row shape selective() consumes. Reps average out agent stochasticity. With
    concurrency > 1 the (rep, case) tasks run on a thread pool, following the evals runner's
    pattern: each worker grounds on its OWN DuckDB cursor (a shared connection object is not
    thread-safe; warehouse.cursor keeps the star search_path), and the model objects are shared
    because the provider SDK clients are thread-safe. Rows come back in (rep, case) order either
    way, so the stored result does not depend on scheduling."""
    cursor_lock = threading.Lock()   # DuckDB: create each thread's cursor under a lock
    print_lock = threading.Lock()

    def one(task):
        rep, idx, case = task
        with cursor_lock:
            cur = scoped_cursor(con)
        try:
            g = build_grounding(cur, rung=RUNG, spec_path=spec_path, engine=engine,
                                semantic_layer=True, guardrails=guardrails)
            try:
                ans = run_agent(case["question"], g, model, verifier_model=verifier)
            except Exception as exc:  # noqa: BLE001 — one failed call shouldn't kill the layer
                # Record the exception TYPE, so a persistent API failure stays distinguishable
                # from a code bug when analysing error rows.
                ans = Answer(case["question"], RUNG, model.spec.name, None,
                             outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
        finally:
            cur.close()
        queried = _queried_metrics(ans)
        row = {**grade(ans, case, golds.get(case["id"])),
               "outcome": ans.outcome, "id": case["id"], "tier": case["tier"],
               "family": case.get("family"), "rep": rep,
               # observed pick: the last metric queried (the one the answer came from),
               # plus the full sequence, so a wrong number is attributable to a metric
               "picked": queried[-1] if queried else None, "queried": queried,
               "calls": _queried_calls(ans),
               "expected_metric": case["expect"].get("metric"),
               "declared": getattr(ans, "declared_value", None)}
        with print_lock:
            mark = "✓" if row.get("correct") else ("~" if ans.outcome != "answer" else "✗")
            print(f"  [{spec_path.name} rep{rep}] {mark} {case['id']}", flush=True)
        return rep, idx, row

    tasks = [(rep, i, c) for rep in range(reps) for i, c in enumerate(cases)]
    if concurrency <= 1:
        results = [one(t) for t in tasks]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(pool.map(one, tasks))
    return [row for _, _, row in sorted(results, key=lambda t: (t[0], t[1]))]


# Selection equivalence (pre-registered 2026-08-21, with the wave-2 question expansion): picking a
# same-valued governed duplicate is a CORRECT selection. The duplicate is the same measure with no
# filter difference, so it returns the same number by construction — sprawl noise, not a wrong
# number. Verified before the rule was added: no wave-1 row in any published arm contained such a
# pick, so the rule changes nothing retroactively.
SELECTION_EQUIVALENT = {"mrr": {"monthly_recurring_revenue"},
                        "paying_users": {"subscribers"},
                        "value_moments": {"total_moments"}}


def _selected_ok(r: dict) -> bool:
    return r["picked"] == r["expected_metric"] or r["picked"] in SELECTION_EQUIVALENT.get(r["expected_metric"], ())


def metrics(rows: list[dict]) -> dict:
    s = selective(rows)
    # SER is the north star and stays root-cause-agnostic (every wrong number, all causes). The two
    # rates below DECOMPOSE it, so they explain the SER rather than clean it:
    #   wrong-selection (Mode 1 — preflight's lane): the agent grounded on the wrong confusable thing.
    #     In a governed layer that is a wrong METRIC (measured here from the query_metric call); in raw
    #     SQL (study 02) it is a wrong COLUMN/definition, recovered from the SQL.
    #   wrong-construction (Mode 2 — the validators' lane): the RIGHT grounding, built wrong (a
    #     mishandled time filter, grain, fan-trap). preflight does not address this one.
    picked = [r for r in rows if r["outcome"] == "answer" and r.get("picked") and r.get("expected_metric")]
    ws = sum(1 for r in picked if not _selected_ok(r))
    wc = sum(1 for r in picked if _selected_ok(r) and not r.get("correct"))
    return {"n": s.n, "coverage": s.coverage,
            "silent_error": s.silent_error, "balanced_accuracy": s.balanced_accuracy,
            "wrong_selection_rate": (ws / len(picked)) if picked else float("nan"),
            "wrong_construction_rate": (wc / len(picked)) if picked else float("nan")}


def _fmt(x) -> str:
    return " n/a " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:5.2f}"


def _print_scorecard(report: dict) -> None:
    print("\n  EXPERIMENT 05 — before/after benefit  (rung 3, agent selects the metric)")
    print("  north star: SER / coverage / bal_acc.  SER decomposes into wrong_selection (Mode 1, "
          "preflight) + wrong_constr (Mode 2).")
    print("  " + "-" * 98)
    print(f"  {'layer':14} {'set':8} {'n':>2}  {'coverage':>8} {'SER':>6} {'bal_acc':>8}"
          f"  |  {'wrong_select':>12} {'wrong_constr':>12}")
    print("  " + "-" * 98)
    for name in ORDER:
        if name not in report:
            continue
        for label in ("overall", "flagged", "clean"):
            m = report[name][label]
            if m["n"] == 0:
                continue
            tag = name if label == "overall" else ""
            print(f"  {tag:14} {label:8} {m['n']:>2}  {_fmt(m['coverage']):>8} "
                  f"{_fmt(m['silent_error']):>6} {_fmt(m['balanced_accuracy']):>8}  |  "
                  f"{_fmt(m.get('wrong_selection_rate')):>12} {_fmt(m.get('wrong_construction_rate')):>12}")
        print("  " + "·" * 98)


def _print_family_table(report: dict) -> None:
    """Per-trap transparency: the flagged silent-error rate for each family on each layer, so the
    reader sees WHICH traps bite rather than a single pooled number."""
    layers = [n for n in ORDER if n in report]
    fams: list[str] = []
    for name in layers:
        for r in report[name]["rows"]:
            if r["tier"] == "flagged" and r.get("family") and r["family"] not in fams:
                fams.append(r["family"])
    if not fams:
        return
    print("\n  per-family flagged silent-error rate")
    print("  " + "-" * 74)
    print(f"  {'family':20}" + "".join(f"{n.replace('_',' '):>14}" for n in layers))
    print("  " + "-" * 74)
    for fam in fams:
        cells = []
        for name in layers:
            rows = [r for r in report[name]["rows"] if r.get("family") == fam]
            cells.append(_fmt(selective(rows).silent_error) if rows else " n/a ")
        print(f"  {fam:20}" + "".join(f"{c:>14}" for c in cells))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="use the mock model (validate wiring, no key)")
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--reps", type=int, default=1, help="repetitions per question (averages stochasticity)")
    ap.add_argument("--concurrency", type=int, default=1,
                    help="parallel agent runs within a layer (per-thread DuckDB cursors; 1 = sequential)")
    ap.add_argument("--only", nargs="*", help="run only these layers")
    ap.add_argument("--study", default="study_01_governed_layer", help="which study directory to run")
    ap.add_argument("--guardrails", default=None,
                    help="guardrail cell (e.g. R7); default None = the loop's R1 (abstain only). "
                         "A non-default cell writes to its own result file, so the R1 record stays intact.")
    ap.add_argument("--engine", default="harness", choices=("harness", "metricflow"),
                    help="grounding engine: harness (bespoke YAML) or metricflow (dbt MetricFlow dir)")
    args = ap.parse_args()

    global LAYERS
    study_dir = HERE / args.study
    mf = args.engine == "metricflow"
    # MetricFlow layers are DIRECTORIES (semantic_model:/metric: docs) under mf_layers/ with their own
    # case set; the harness engine uses layers/<name>/semantic.yml and cases.yml.
    LAYERS = study_dir / ("mf_layers" if mf else "layers")
    cases = load_cases(study_dir / ("cases_mf.yml" if mf else "cases.yml"))
    con = open_warehouse(create_star_views=True)
    set_star(con, capabilities(RUNG).star)
    if mf:
        ensure_mf_views(con)
    golds = compute_gold(con, cases)
    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)

    def spec_of(name):
        return LAYERS / name if mf else LAYERS / name / "semantic.yml"

    names = [n for n in ORDER if (not args.only or n in args.only) and spec_of(n).exists()]

    from agent.guardrails import parse_cell
    gset = parse_cell(args.guardrails) if args.guardrails else None

    # Persist after EACH layer and merge into any existing result, so a long run (reps x layers) that
    # is interrupted keeps every completed layer, and layers run in separate invocations accumulate.
    # A non-default guardrail cell gets its own file: the R1 record is a published artifact and a
    # heavier cell merged over it would silently replace what the study measured.
    suffix = "_mf" if mf else ""
    cell_tag = f"_{args.guardrails.lower()}" if args.guardrails else ""
    out = study_dir / (f"benefit_result{suffix}_mock.json" if args.mock
                       else f"benefit_result{suffix}{cell_tag}__{args.model}.json")
    report: dict = json.loads(out.read_text()) if (out.exists() and not args.mock) else {}
    report.update({"model": ("mock" if args.mock else args.model), "rung": RUNG, "reps": args.reps,
                   "engine": args.engine, "guardrails": args.guardrails or "R1 (loop default)"})
    for name in names:
        rows = run_layer(con, spec_of(name), cases, golds, model, verifier, args.reps, args.engine,
                         guardrails=gset, concurrency=args.concurrency)
        report[name] = {"overall": metrics(rows),
                        "flagged": metrics([r for r in rows if r["tier"] == "flagged"]),
                        "clean": metrics([r for r in rows if r["tier"] == "clean"]),
                        "rows": rows}
        out.write_text(json.dumps(report, indent=2, default=str))

    _print_scorecard(report)
    _print_family_table(report)
    print(f"\n  wrote {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
