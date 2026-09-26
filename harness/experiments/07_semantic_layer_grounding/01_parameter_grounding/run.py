#!/usr/bin/env python3
"""Study 01 · parameter grounding: run the suite across the three arms and record every row.

    R3                        the agent at rung 3 on this experiment's MetricFlow layer
    R3+disclose_assumptions   R3 plus one instruction to state every assumption and default
    R3+parameter_grounding    R3 plus the grounding step (agent/guardrails/parameters.py)

Every row is built by `evals.row.measured_row`, so it carries the shared grade, tokens, cost and
latency, and `bench report` / `bench publish` read the run directory like any other. Two fields are
added per row for the secondary measure (milestoneA.md, "Measures"):

    disclosure_due      the case's decisions marked must_disclose
    disclosure_missed   those whose `disclose_words` appear nowhere in what the reader receives
                        (answer, explanation and, for a decline, its stated reason)

Both are prose-graded: a word list matched in free text. They are reported beside the headline
measures and never folded into them.

    python run.py --mock --only q_001_android_opens_june                 # plumbing, no cost
    python run.py --model gpt-5-mini --reps 3 --concurrency 2            # the full suite
    python run.py --model gpt-5-mini --only q_001_android_opens_june,t_003_tiktok_opens_q2
    python run.py --regrade <run dir>    # re-grade stored answers: no model calls, seconds
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from agent.guardrails import parse_cell
from agent.runtime.grounding import build_grounding
from agent.runtime.loop import Answer, run_agent
from agent.runtime.providers import get_model, get_verifier
from evals import report
from evals.gold import _validate, compute_gold, stamp_suite
from evals.row import measured_row
from evals.runner import regrade_run
from evals.second_turn import follow_up
from evals.selective import selective
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
sys.path.insert(0, str(EXPERIMENT / "fixture"))
import build as fixture_build  # noqa: E402

LAYER = EXPERIMENT / "fixture" / "layer"
GOVERNANCE = yaml.safe_load((EXPERIMENT / "fixture" / "governance.yml").read_text())
RUNS = EXPERIMENT.parents[2] / "runs" / "experiments" / EXPERIMENT.name
MARTS = "wh_06"
RUNG = 3
ARMS = ("R3", "R3+disclose_assumptions", "R3+parameter_grounding")

# The catalogue layout and schema note experiment 06 settled on, copied so this experiment runs
# without 06's folder. Identical in every arm: only the guardrail cell varies.
CATALOGUE = "normalised"
SCHEMA_EXPLANATION = (
    "HOW THIS SEMANTIC LAYER IS SHAPED (read once; it applies to every metric):\n"
    "- Each governed metric COUNTS ONE ENTITY — active_users counts `activity`, mrr counts "
    "`subscription`, marketing_spend counts `spend_row`. The catalogue names each metric's entity.\n"
    "- A metric can be FILTERED or GROUPED by any dimension OF THE ENTITY IT COUNTS. Each entity's "
    "dimensions are listed ONCE, under 'Entities and their dimensions', with their allowed values.\n"
    "- To filter, pass filters={'entity__dimension': value} to query_metric — e.g. "
    "{'activity__platform': 'ios'} for iOS, {'subscription__plan': 'monthly'} for the monthly plan, "
    "{'spend_row__channel': 'content_seo'} for content-and-SEO spend. To break down, pass "
    "group_by=['entity__dimension'].\n"
    "- When a question names a SEGMENT — a platform, a plan, a channel, a region — find that "
    "dimension under the metric's entity and apply it as a filter. Do NOT report the unfiltered "
    "total as if it were the segment.")


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for case in cases:
        _validate(case, "cases.yml")
    stamp_suite(cases)
    return cases


def scoped_cursor(con):
    """The agent's handle: search_path is the marts alone, so raw and staging tables are absent."""
    cur = con.cursor()
    cur.execute(f"SET search_path='{MARTS}'")
    return cur


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", str(text or "").lower()))


def disclosure(answer: Answer, case: dict) -> tuple[list, list]:
    """(due, missed): the decisions the case says must be disclosed, and those whose words the
    reader never receives. Word-level and case-insensitive, so "Staff" matches "staff"."""
    seen = f" {_words(' '.join(str(x or '') for x in (answer.answer, answer.explanation, answer.reason)))} "
    due = [d for d in case.get("decisions") or () if d.get("must_disclose")]
    missed = [d for d in due
              if not any(f" {_words(w)} " in seen for w in d.get("disclose_words") or ())]
    return ([f"{d['parameter']}: {d['value']}" for d in due],
            [f"{d['parameter']}: {d['value']}" for d in missed])


def disclosure_fields(answer: Answer, case: dict) -> dict:
    due, missed = disclosure(answer, case)
    return {"disclosure_due": due, "disclosure_missed": missed, "disclosure_graded_by": "prose"}


def summarise(rows: list, arms: list) -> None:
    print(f"\n{'arm':26} {'n':>3} {'coverage':>9} {'silent_err':>11} {'bal_acc':>8} "
          f"{'undisclosed':>12} {'usd':>8}")
    for arm in arms:
        sub = [r for r in rows if r["config"] == arm]
        s = selective(sub).as_dict()
        due = [r for r in sub if r["disclosure_due"]]
        undisclosed = sum(1 for r in due if r["disclosure_missed"])
        usd = sum(r["cost_usd"] or 0 for r in sub)
        print(f"{arm:26} {len(sub):>3} {s['coverage']!s:>9} {s['silent_error']!s:>11} "
              f"{s['balanced_accuracy']!s:>8} {f'{undisclosed}/{len(due)}':>12} {usd:>8.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--mock", action="store_true", help="scripted model: no API key, no cost")
    ap.add_argument("--arms", default=",".join(ARMS), help="comma-separated guardrail cells")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--only", default=None, help="comma-separated case ids")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="threads over tasks; keep it low (E-20: a rate limiter is not a result)")
    ap.add_argument("--regrade", default=None, metavar="RUN_DIR",
                    help="re-grade a stored run against the current cases and grader; no model calls")
    args = ap.parse_args()

    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    cases = load_cases()
    golds = compute_gold(con, cases)
    if args.regrade:
        run_dir = pathlib.Path(args.regrade).resolve()
        regrade_run(run_dir, cases, extra=disclosure_fields)
        rows = [json.loads(line) for line in (run_dir / "raw.jsonl").open()]
        summarise(rows, list(dict.fromkeys(r["config"] for r in rows)))
        return
    if args.only:
        wanted = args.only.split(",")
        cases = [c for c in cases if c["id"] in wanted]
        missing = set(wanted) - {c["id"] for c in cases}
        if missing:
            sys.exit(f"unknown case id(s): {sorted(missing)}")
    arms = args.arms.split(",")
    cells = {arm: parse_cell(arm) for arm in arms}

    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{stamp}-{HERE.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"model {model.spec.name}  rung {RUNG}  arms {', '.join(arms)}  "
          f"questions {len(cases)}  reps {args.reps}\n-> {run_dir}\n")

    cursor_lock, print_lock = threading.Lock(), threading.Lock()

    def one(task):
        arm, rep, idx, case = task
        with cursor_lock:
            cur = scoped_cursor(con)
        try:
            grounding = build_grounding(cur, rung=RUNG, spec_path=LAYER, engine="metricflow",
                                        semantic_layer=True, guardrails=cells[arm], schema=MARTS)
            grounding.semantic.catalogue = CATALOGUE
            grounding.refresh_catalogue()
            grounding.system += "\n\n" + SCHEMA_EXPLANATION
            grounding.toolbox.governance = GOVERNANCE

            def ask(text, _g=grounding):
                try:
                    return run_agent(text, _g, model, verifier_model=verifier)
                except Exception as exc:                                   # noqa: BLE001
                    return Answer(text, RUNG, model.spec.name, None, outcome="error",
                                  error=f"{type(exc).__name__}: {exc}"[:200])

            t0 = time.perf_counter()
            answer = ask(case["question"])
            elapsed_s = time.perf_counter() - t0
            t1 = time.perf_counter()
            follow = follow_up(answer, case, ask)
            if follow is not None:
                follow["elapsed_s"] = round(time.perf_counter() - t1, 3)
        finally:
            cur.close()
        row = measured_row(answer, case, golds[case["id"]], elapsed_s=elapsed_s,
                           rung=RUNG, config=cells[arm].label(), rep=rep,
                           second_turn=follow, resolution=(follow or {}).get("resolution"),
                           **disclosure_fields(answer, case))
        missed, due = row["disclosure_missed"], row["disclosure_due"]
        with print_lock:
            mark = "OK  " if row["correct"] else ("SILENT" if row["confident_wrong"] else "MISS")
            print(f"  {arm:24} rep {rep + 1}  {case['id']:42} {answer.outcome:8} {mark:6} "
                  f"undisclosed {len(missed)}/{len(due)}" + (f"  {answer.error}" if answer.error else ""))
        return (arms.index(arm), rep, idx), row

    tasks = [(arm, rep, i, c) for arm in arms for rep in range(args.reps) for i, c in enumerate(cases)]
    if args.concurrency <= 1:
        results = [one(t) for t in tasks]
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(one, tasks))
    rows = [row for _, row in sorted(results, key=lambda t: t[0])]

    with (run_dir / "raw.jsonl").open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    report.write(rows, run_dir, mock=args.mock)

    summarise(rows, [cells[a].label() for a in arms])
    print(f"\nwrote {run_dir / 'raw.jsonl'} and summary.md")


if __name__ == "__main__":
    main()
