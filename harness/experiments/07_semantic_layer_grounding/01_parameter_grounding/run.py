#!/usr/bin/env python3
"""Study 01 · parameter grounding: run the suite across the three arms and record every row.

    R4                        the agent at rung 3 on this experiment's MetricFlow layer, with raw SQL
                              withdrawn (tool_restriction): every number comes from a governed metric
    R4+disclose_assumptions   R4 plus one instruction to state every assumption and default
    R4+parameter_grounding    R4 plus the grounding step (agent/guardrails/parameters.py)
    R4+decision_grounding     R4 plus grounding by a decision model (agent/guardrails/decisions.py)
    R4+decision_grounding+reading_first
                              the same, with the decision model's reading of the question shown to the
                              agent before its first call instead of discovered one blocked call at a time

Raw SQL is off in every arm because the experiment measures how a governed call's parameters are
chosen. With run_sql available, the agent can go around the governed layer (t_004 grouped app opens
by an unrelated column renamed `device_model`), and that failure belongs to a different experiment.
Runs before 2026-10-04 used R3 cells, with raw SQL available.

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
    python run.py --arms R4+decision_grounding --protocols none,claims    # with and without claims
    python run.py --regrade <run dir>    # re-grade stored answers: no model calls, seconds

The summary's second table is the governed calls behind the answers (evals/calls.py): which calls
the answer used, the spend on the ones it did not, whether the used calls' parameters match the
labels, and, with the claims protocol, how many claims state a figure their cited call did not return.
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
from agent.core.protocol import Protocol
from agent.guardrails import parse_cell
from agent.runtime.grounding import build_grounding
from agent.runtime.loop import Answer, run_agent
from agent.runtime.providers import get_model, get_verifier
from evals import report
from evals.gold import _validate, compute_gold, stamp_suite
from evals.row import measured_row
from evals.runner import regrade_run
from agent.guardrails.parameters import rules_text
from evals.second_turn import follow_up
from evals.calls import call_use
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
ARMS = ("R4", "R4+disclose_assumptions", "R4+parameter_grounding", "R4+decision_grounding")

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


def load_cases(name: str = "cases.yml") -> list[dict]:
    cases = yaml.safe_load((HERE / name).read_text())["cases"]
    for case in cases:
        _validate(case, name)
    stamp_suite(cases)
    return cases


def check_params(cases: list, con) -> None:
    """Every labelled value is a real member of its dimension, `ask`, or a list of those, except in
    a refuse or refuse-or-ask case, where naming something the layer lacks is the point. A typo in a label (`andriod`)
    would otherwise grade every arm against a value no query can produce."""
    from ontology import parameters as surface
    layer = (LAYER / "semantic_models.yml").read_text()
    for case in cases:
        e = case["expect"]
        metric = e.get("metric") or (e.get("candidates") or [{}])[0].get("metric")
        if not metric:
            continue
        members = {d["column"]: {str(m).lower() for m in d["members"] or ()}
                   for d in surface.build(con, layer, metric)["parameters"]["filters"]["dimensions"]}
        for key, value in (e.get("params") or {}).items():
            if key not in members or not members[key] or e["type"] in ("refuse", "ambiguous"):
                continue
            bad = [v for v in (value if isinstance(value, list) else [value])
                   if v.lower() not in members[key] | {"none", "ask"}]
            if bad:
                sys.exit(f"{case['id']}: params.{key} = {bad} is not a member of {key} "
                         f"({sorted(members[key])})")


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


_HALVES = {"H1": range(1, 7), "H2": range(7, 13)}


def _months(period) -> set | None:
    """The calendar months a period names: '2026-06', '2026-Q2', '2026-H1', '2026'. None for a
    form this grader does not read (a relative period, explicit dates)."""
    m = re.fullmatch(r"(\d{4})(?:-(\d{2})|-Q([1-4])|-(H[12]))?", str(period or ""))
    if not m:
        return None
    year, month, quarter, half = m.groups()
    months = ([int(month)] if month else range(3 * int(quarter) - 2, 3 * int(quarter) + 1)
              if quarter else _HALVES[half] if half else range(1, 13))
    return {(int(year), x) for x in months}


def _dim(key: str) -> str:
    return str(key).split("__")[-1].lower()


def _built_in(metric: str) -> dict:
    """The filters a metric applies by definition, e.g. {'is_internal': 'false'}. They count as set
    on every call to that metric: the reader's number excludes staff whether or not the call says so."""
    from ontology import parameters as surface
    _, metrics = surface.load_layer((LAYER / "semantic_models.yml").read_text())
    text = surface.metric_filter(metrics, metric) or ""
    own = {_dim(k): v.lower() for k, v in re.findall(r"([\w.]+)\s*=\s*'?(\w+)'?", text)}
    # A ratio applies a filter when both its numerator and its denominator apply it.
    parts = metrics[metric].get("type_params") or {}
    if "numerator" in parts and "denominator" in parts:
        num, den = (_built_in(parts[p]["name"]) for p in ("numerator", "denominator"))
        own |= {k: v for k, v in num.items() if den.get(k) == v}
    return own


def used_call_errors(row: dict, case: dict) -> list | None:
    """Grade the parameters of the governed calls the answer rests on, one labelled decision at a
    time. None when there is nothing to grade: the row did not answer, or the case has no params.

    Calls the answer did not use are exploration and are not graded here (evals/calls.py). The
    check is per decision, not per call shape, so routes that reach the same numbers grade the
    same: six monthly calls cover a half-year trend at month grain exactly as one call grouped by
    metric_time does. A list label means every listed value must be covered, by separate calls or
    by grouping on that dimension, except `time_grain`: a series has one grain, so a list there
    names the acceptable grains."""
    want, metric = case["expect"].get("params"), case["expect"].get("metric")
    if row["outcome"] != "answer" or not want or not metric:
        return None
    steps = row["steps"]
    queries = [q for i in call_use(row)["used"]
               for q in (steps[i].get("grounded_queries") or [steps[i]["args"]])]
    if not queries:
        return ["the answer rests on no governed call"]
    errors = []
    called = {q.get("metric") for q in queries}
    if called != {metric}:
        errors.append(f"metric {sorted(map(str, called))} instead of {metric}")
    built_in = _built_in(metric) if metric in called else {}
    grouped = {_dim(g) for q in queries for g in q.get("group_by") or []}
    periods = [_months(q.get("period")) for q in queries]
    # Several calls that differ only in period form one series over the periods they cover.
    split = len({json.dumps({k: v for k, v in q.items() if k != "period"}, sort_keys=True)
                 for q in queries}) == 1 and len(queries) > 1
    if split:
        grouped.add("metric_time")
    # Grouping one month by month (or a call per month) is one figure per period, not a split the
    # question did not ask for.
    one_bucket = "metric_time" not in {_dim(g) for g in want.get("group_by") or []} and all(
        len(_months(q.get("period")) or ()) == 1 and q.get("time_grain") in (None, "month") for q in queries)
    if one_bucket:
        grouped.discard("metric_time")
    # A list filter value (one IN filter) counts as each of its members.
    filters = [{**{k: [v] for k, v in built_in.items()},
                **{_dim(k): [str(x).lower() for x in (v if isinstance(v, list) else [v])]
                   for k, v in (q.get("filters") or {}).items()}} for q in queries]
    for key, value in want.items():
        if value == "ask" or key in ("group_by", "time_grain", "period"):
            continue
        need = {str(v).lower() for v in (value if isinstance(value, list) else [value])}
        got = {x for f in filters for x in f.get(key, ["none"])}
        if not (got == need or (key in grouped and len(need) > 1)):
            errors.append(f"{key} {sorted(got)} instead of {sorted(need)}")
    unasked = {k for f in filters for k in f} - set(want) - set(built_in)
    if unasked:
        errors.append(f"filters on {sorted(unasked)}, which the question does not ask for")
    # The requested breakdown must be covered, and at least one call must answer at that breakdown
    # or a part of it. A supplementary call (the quarter's figure plus a monthly view) is not an
    # error; a call that splits by a dimension nobody asked for, with nothing else, is.
    # Grouping by a dimension whose label lists several values is one way to show all of them.
    want_gb = {_dim(g) for g in want.get("group_by") or []}
    allowed = want_gb | {k for k, v in want.items() if isinstance(v, list) and k != "time_grain"}
    own = [({_dim(g) for g in q.get("group_by") or []} | ({"metric_time"} if split else set()))
           - ({"metric_time"} if one_bucket else set()) for q in queries]
    if not want_gb <= grouped or not any(g <= allowed for g in own):
        errors.append(f"group_by {sorted(grouped)} instead of {sorted(want_gb)}")
    if "time_grain" in want and "metric_time" in grouped:
        grains = {"month" if split and all(p and len(p) == 1 for p in periods) else q.get("time_grain")
                  for q in queries}
        if not grains <= set(want["time_grain"]):
            errors.append(f"time_grain {sorted(map(str, grains))} instead of one of {want['time_grain']}")
    if want.get("period") not in (None, "ask"):
        need = set().union(*[_months(p) or set() for p in
                             (want["period"] if isinstance(want["period"], list) else [want["period"]])])
        got = set().union(*[p or set() for p in periods])
        if None in periods or got != need:
            errors.append(f"period {sorted({str(q.get('period')) for q in queries})} "
                          f"instead of {want['period']}")
    return errors



def summarise(rows: list, arms: list, cases: list) -> None:
    print(f"\n{'arm':30} {'n':>3} {'coverage':>9} {'silent_err':>11} {'bal_acc':>8} "
          f"{'undisclosed':>12} {'usd':>8}")
    for arm in arms:
        sub = [r for r in rows if r["config"] == arm]
        s = selective(sub).as_dict()
        due = [r for r in sub if r["disclosure_due"]]
        undisclosed = sum(1 for r in due if r["disclosure_missed"])
        # Decision-model requests are billed per request, so they are added from the steps (a call's
        # grounding) and the turns (a reading made at the final action).
        usd = sum((r["cost_usd"] or 0) + sum(x.get("grounding_cost_usd") or 0 for x in r["steps"] + r["turns"])
                  for r in sub)
        print(f"{arm:30} {len(sub):>3} {s['coverage']!s:>9} {s['silent_error']!s:>11} "
              f"{s['balanced_accuracy']!s:>8} {f'{undisclosed}/{len(due)}':>12} {usd:>8.4f}")
    calls_table(rows, arms, cases)


def calls_table(rows: list, arms: list, cases: list) -> None:
    """The governed calls behind the answers. A used call is graded on its parameters; an unused
    one is exploration, counted only as spend. `basis` says how use was decided (evals/calls.py).
    Spend is the cost of the turns that issued the calls, not the whole run's cost."""
    by_id = {c["id"]: c for c in cases}
    print(f"\n{'arm':30} {'basis':>7} {'answers':>8} {'calls/ans':>9} {'used':>5} {'unused':>7} "
          f"{'unused usd':>11} {'params right':>13} {'unbound claims':>15}")
    for arm in arms:
        # Answered rows only: calls made before a refusal or a question are what led to it.
        sub = [r for r in rows if r["config"] == arm and r["qid"] in by_id and r["outcome"] == "answer"]
        uses = [call_use(r) for r in sub]
        graded = [e for r in sub if (e := used_call_errors(r, by_id[r["qid"]])) is not None]
        spent = sum(u["used_usd"] + u["unused_usd"] for u in uses)
        bases = "/".join(sorted({u["basis"] for u in uses}))
        # A claim that cites a call but states a figure the call did not return (claim audit).
        audits = [r["claim_audit"] for r in sub if r.get("claim_audit")]
        unbound = (f"{sum(a['n'] - a['bound'] for a in audits)}/{sum(a['n'] for a in audits)}"
                   if audits else "-")
        print(f"{arm:30} {bases:>7} {len(sub):>8} {sum(len(u['used']) + len(u['unused']) for u in uses) / max(len(sub), 1):>9.2f} "
              f"{sum(len(u['used']) for u in uses):>5} {sum(len(u['unused']) for u in uses):>7} "
              f"{sum(u['unused_usd'] for u in uses):>6.4f}/{spent:.4f} "
              f"{f'{sum(not e for e in graded)}/{len(graded)}':>8} {unbound:>15}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--mock", action="store_true", help="scripted model: no API key, no cost")
    ap.add_argument("--arms", default=",".join(ARMS), help="comma-separated guardrail cells")
    ap.add_argument("--protocols", default="none",
                    help="comma-separated declaration protocols crossed with every arm: none, claims "
                         "(typed claims citing each call, which the governed-calls table reads)")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--only", default=None, help="comma-separated case ids")
    ap.add_argument("--cases", default="cases.yml",
                    help="the suite file in this folder: cases.yml (the measured suite) or a probe set")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="threads over tasks; keep it low (E-20: a rate limiter is not a result)")
    ap.add_argument("--regrade", default=None, metavar="RUN_DIR",
                    help="re-grade a stored run against the current cases and grader; no model calls")
    args = ap.parse_args()

    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    cases = load_cases(args.cases)
    check_params(cases, con)
    golds = compute_gold(con, cases)
    if args.regrade:
        run_dir = pathlib.Path(args.regrade).resolve()
        regrade_run(run_dir, cases, extra=disclosure_fields)
        rows = [json.loads(line) for line in (run_dir / "raw.jsonl").open()]
        summarise(rows, list(dict.fromkeys(r["config"] for r in rows)), cases)
        return
    if args.only:
        wanted = args.only.split(",")
        cases = [c for c in cases if c["id"] in wanted]
        missing = set(wanted) - {c["id"] for c in cases}
        if missing:
            sys.exit(f"unknown case id(s): {sorted(missing)}")
    cells = {arm: parse_cell(arm) for arm in args.arms.split(",")}
    # A config is a guardrail cell crossed with a protocol, labelled as the shared runner labels it.
    configs = [(arm, Protocol.parse(p)) for arm in cells for p in args.protocols.split(",")]
    labels = [cells[arm].label() + proto.label() for arm, proto in configs]

    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{stamp}-{HERE.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"model {model.spec.name}  rung {RUNG}  configs {', '.join(labels)}  "
          f"questions {len(cases)}  reps {args.reps}\n-> {run_dir}\n")

    cursor_lock, print_lock = threading.Lock(), threading.Lock()

    def one(task):
        (arm, proto), rep, idx, case = task
        with cursor_lock:
            cur = scoped_cursor(con)
        try:
            grounding = build_grounding(cur, rung=RUNG, spec_path=LAYER, engine="metricflow",
                                        semantic_layer=True, guardrails=cells[arm], schema=MARTS,
                                        protocol=proto)
            grounding.semantic.catalogue = CATALOGUE
            grounding.refresh_catalogue()
            grounding.system += "\n\n" + SCHEMA_EXPLANATION
            if cells[arm].parameter_grounding or cells[arm].decision_grounding or cells[arm].decision_plan:
                # Runtime governance is part of the grounding arms: the agent reads the rules first.
                grounding.system += "\n\n" + rules_text(GOVERNANCE)
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
                           rung=RUNG, config=labels[configs.index((arm, proto))], rep=rep,
                           protocol=proto.label().lstrip("/") or "none",
                           second_turn=follow, resolution=(follow or {}).get("resolution"),
                           **disclosure_fields(answer, case))
        missed, due = row["disclosure_missed"], row["disclosure_due"]
        with print_lock:
            mark = "OK  " if row["correct"] else ("SILENT" if row["confident_wrong"] else "MISS")
            print(f"  {labels[configs.index((arm, proto))]:30} rep {rep + 1}  {case['id']:42} {answer.outcome:8} {mark:6} "
                  f"undisclosed {len(missed)}/{len(due)}" + (f"  {answer.error}" if answer.error else ""))
        return (configs.index((arm, proto)), rep, idx), row

    tasks = [(cfg, rep, i, c) for cfg in configs for rep in range(args.reps) for i, c in enumerate(cases)]
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

    summarise(rows, labels, cases)
    print(f"\nwrote {run_dir / 'raw.jsonl'} and summary.md")


if __name__ == "__main__":
    main()
