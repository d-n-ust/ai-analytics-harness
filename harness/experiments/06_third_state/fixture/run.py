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
from agent.runtime.grounding import build_grounding
from agent.guardrails import parse_cell
from agent.runtime.loop import Answer, run_agent
from agent.runtime.providers import get_model, get_verifier
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.matrix import render as render_matrix
from evals.selective import selective
from warehouse.warehouse import cursor as _shared_cursor


MARTS = "wh_06"

# The schema explanation for the `normalised` catalogue arm. The normalised catalogue lists each
# metric with the ENTITY it counts and each entity's dimensions ONCE; this teaches the shape so the
# agent can compose a filter from the structure rather than from a value repeated under every
# metric. Added to the system prompt only for that arm — the other arms render the data denormalised
# and need no schema note.
def _schema_explanation(where: str) -> str:
    # The schema note shared by the `normalised` and `hybrid` arms. Only the sentence saying WHERE a
    # dimension's allowed values sit differs between them: normalised lists every entity's dimensions
    # once in the shared block; hybrid lists a metric's own dimensions inline and only joined ones in
    # the shared block. Everything else — a metric counts one entity, filter by entity__dimension,
    # apply the segment rather than the unfiltered total — is identical.
    return (
        "HOW THIS SEMANTIC LAYER IS SHAPED (read once; it applies to every metric):\n"
        "- Each governed metric COUNTS ONE ENTITY — active_users counts `activity`, mrr counts "
        "`subscription`, marketing_spend counts `spend_row`. The catalogue names each metric's entity.\n"
        "- A metric can be FILTERED or GROUPED by any dimension OF THE ENTITY IT COUNTS. " + where + "\n"
        "- To filter, pass filters={'entity__dimension': value} to query_metric — e.g. "
        "{'activity__platform': 'ios'} for iOS, {'subscription__plan': 'monthly'} for the monthly plan, "
        "{'spend_row__channel': 'content_seo'} for content-and-SEO spend. To break down, pass "
        "group_by=['entity__dimension'].\n"
        "- When a question names a SEGMENT — a platform, a plan, a channel, a region — find that "
        "dimension under the metric's entity and apply it as a filter. Do NOT report the unfiltered "
        "total as if it were the segment.")


SCHEMA_EXPLANATION = _schema_explanation(
    "Each entity's dimensions are listed ONCE, under 'Entities and their dimensions', with their "
    "allowed values.")
HYBRID_SCHEMA_EXPLANATION = _schema_explanation(
    "A metric's own dimensions are listed beneath it with their allowed values; dimensions reached "
    "through a join are listed once under 'Entities and their dimensions'.")


# The `ontology_tool` arm. The lean metric list moves into the system prompt (so list_metrics costs
# no turn) and a `show_metric_ontology(metric)` tool returns the full per-metric contract on demand.
# The directive points the agent at the tool; the schema note tells it where a dimension's values are.
ONTOLOGY_DIRECTIVE = (
    "The governed metrics are listed below with a one-line description each. Before you query a "
    "metric you have not inspected, call show_metric_ontology(metric) to get its full definition: "
    "the arguments it accepts, its dimensions and their governed values, a usage example, and which "
    "segments it can isolate. A list entry is only a summary; a value the ontology does not list is "
    "not in the data, so refuse rather than approximate.")
ONTOLOGY_SCHEMA_EXPLANATION = _schema_explanation(
    "Call show_metric_ontology(metric) to see that metric's dimensions and their allowed values.")


# The transparent-governance contract, injected when `transparent_compute` is on. It tells the agent
# it MAY compute a measure that has no governed metric, provided it discloses the definition — the
# behaviour the answerability_gate then enforces.
TRANSPARENT_PROTOCOL = (
    "GOVERNANCE POLICY (transparent): a question may ask for a measure that has NO governed metric. "
    "First prefer a governed metric. If none fits but the DATA can compute the measure (via run_sql), "
    "you MAY compute it — but you MUST state the definition you used and how you computed it, and note "
    "the margin when a leading value is close to the next; or `clarify` which definition is wanted if "
    "the choice changes the answer. If the data does not capture the measure at all, `refuse` with "
    "reason `uninstrumented`. Never serve a computed figure for a non-governed measure without its "
    "definition.")

# Paired with `answer_spec` (which adds the typed `direction` slot). The steer that makes a loaded
# question USEFUL rather than merely correct: a bare refuse of a false premise is defensible but
# unhelpful — the useful reply corrects it AND gives the number.
FALSE_PREMISE_POLICY = (
    "USEFULNESS ON A FALSE PREMISE: if a question presumes a trend your data contradict — it asks "
    "'by how much did X fall' and X actually rose — do NOT refuse. A refuse is correct but not "
    "useful. ANSWER, correcting the premise: state the true direction and the governed change value "
    "(e.g. 'active users did not fall last week; they rose by 50'), and set the typed `direction` to "
    "what YOUR OWN numbers show, not what the question presumed. Refuse `false_premise` only when the "
    "true value genuinely cannot be recovered.")


def scoped_cursor(con):
    """The handle the agent's tools get: search_path is the MARTS schema alone. `_source`, `_star`
    and the `_stg` staging schema are all absent, so an unqualified reference to anything but a
    documented mart fails rather than silently returning uncleaned or undocumented data. The same
    rule `warehouse.Environment.cursor` uses for per-arm environments."""
    cur = con.cursor()
    cur.execute(f"SET search_path='{MARTS}'")
    return cur
from warehouse.warehouse import open_warehouse

import build as fixture_build

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE / "layer"

RUNG = 3          # star + governed semantic layer, raw SQL still on the table

# The three shapes a question can have, as the grader names them. Kept here so the runner's own
# labels cannot drift from `selective.py`'s piles.
_PILE = {"metric_answer": "A", "refuse": "B", "contested": "C"}


def load_cases(name: str = "cases.yml") -> list[dict]:
    """The suite to run. `heldout.yml` exists because every guardrail here was chosen after watching
    `cases.yml` fail, so that file measures fit rather than generalisation."""
    cases = yaml.safe_load((HERE / name).read_text())["cases"]
    for case in cases:
        _validate(case, name)
    return cases


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
    ap.add_argument("--catalogue", default="normalised", choices=("full", "compact", "inline", "values", "minimal", "normalised", "hybrid"),
                    help="how the metric list is laid out. `compact` puts every name and "
                         "description contiguous and the dimension detail in a second block — "
                         "same facts, different adjacency.")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="threads over (rep, question) tasks. Safe because nothing writes: models "
                         "are built before the pool starts and each worker takes its own cursor.")
    ap.add_argument("--cases", default="cases.yml",
                    help="which suite to run: cases.yml (the original, now partly a training set) "
                         "or heldout.yml (authored after the mechanisms were frozen)")
    ap.add_argument("--only", default=None, help="comma-separated case ids, to probe one question")
    ap.add_argument("--json", dest="out", default=None, help="write the graded rows here")
    args = ap.parse_args()

    layer = (HERE / "variants" / args.variant) if args.variant else LAYER
    if not layer.is_dir():
        sys.exit(f"{layer} does not exist — run `python variants.py --write` first")
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)           # so the layer has something to read; drop clears
                                                  # any stale view a renamed model left behind
    cases = load_cases(args.cases)
    golds = compute_gold(con, cases)             # resolves each candidate's own oracle
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only.split(","))]

    guardrails = parse_cell(args.cell) if args.cell else None

    # A study that starts against a broken layer measures the layer, not the treatment. One query
    # per metric, about a second, before any model call is paid for.
    probe = build_grounding(scoped_cursor(con), rung=RUNG, spec_path=layer, engine="metricflow",
                            semantic_layer=True, guardrails=guardrails, schema=MARTS)
    broken = getattr(probe.semantic, "self_test", lambda: {})()
    if broken:
        for name, err in broken.items():
            print(f"  BROKEN  {name:24} {err}")
        sys.exit(f"{len(broken)} metric(s) in {layer} do not run. Fix the layer before measuring.")

    model = get_model(args.model, mock=args.mock)
    # The verifier resolution (used by the aptness challenger) — the eval runner already
    # builds one; the fixture ran the challenger on the author until this line.
    verifier = get_verifier(args.model, mock=args.mock)

    for case in cases:
        pile = _PILE[case["expect"]["type"]]
        print(f"pile {pile}     : {case['question']}")
        for cand in case["expect"].get("candidates") or ():
            print(f"    {cand['metric']:18} = {cand['value']:>10,.0f}   owner {cand['owner']:10} "
                  f"→ {cand['consumer']}")
    print(f"\nmodel      : {model.spec.name}   rung {RUNG}   "
          f"guardrails {args.cell or 'loop default'}   layer {args.variant or 'shipped'}   "
          f"catalogue {args.catalogue}   reps {args.reps}")

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
            # schema=MARTS: run_sql reads and is bounded to the documented marts, the same
            # warehouse the semantic layer uses — not staging, the raw source, or the shared star.
            grounding = build_grounding(cur, rung=RUNG, spec_path=layer, engine="metricflow",
                                        semantic_layer=True, guardrails=guardrails, schema=MARTS)
            grounding.semantic.catalogue = args.catalogue
            grounding.refresh_catalogue()   # the preloaded copy must show the chosen rendering
            if args.catalogue == "normalised":
                grounding.system += "\n\n" + SCHEMA_EXPLANATION
            elif args.catalogue == "hybrid":
                grounding.system += "\n\n" + HYBRID_SCHEMA_EXPLANATION
            # The ontology arm carries the lean list IN the prompt (no list_metrics turn) plus the
            # directive to pull a metric's full contract on demand. Pair with `--catalogue minimal`
            # so the in-prompt list and the list_metrics fallback render the same lean text.
            if getattr(grounding.guardrails, "ontology_tool", False):
                grounding.system += ("\n\n" + ONTOLOGY_DIRECTIVE + "\n\n"
                                     + grounding.semantic.list_metrics_text()
                                     + "\n\n" + ONTOLOGY_SCHEMA_EXPLANATION)
            if getattr(grounding.guardrails, "transparent_compute", False):
                grounding.system += "\n\n" + TRANSPARENT_PROTOCOL
            if getattr(grounding.guardrails, "answer_spec", False):
                grounding.system += "\n\n" + FALSE_PREMISE_POLICY
            with print_lock:
                if not shown:
                    shown.add(True)
                    offered = [s["name"] for s in grounding.toolbox.specs()]
                    print(f"\ntools offered ({len(offered)}): {', '.join(offered)}")
                    print("metrics in the catalogue: "
                          f"{', '.join(sorted(grounding.toolbox.semantic.metrics))}\n")
            try:
                answer = run_agent(case["question"], grounding, model, verifier_model=verifier)
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
                          # The coded reason/missing a decline carried, so a refusal's CODE is
                          # visible in the stored row (grade.py already grades on answer.reason;
                          # this makes it inspectable without re-running).
                          "reason": answer.reason, "missing": answer.missing,
                          # The clarify options, with their groundings under grounded_candidates.
                          # Without this the trace cannot show what the model offered — the gap
                          # that made a laundered clarify look reason-less until it was stored.
                          "candidates": list(getattr(answer, "candidates", ()) or ()),
                          "source_metric": answer.source_metric,
                          # The typed direction slot, so direction_vs_evidence's effect is
                          # inspectable in the stored row (the grader reads it off the Answer).
                          "direction": getattr(answer, "direction", None),
                          "tool_calls": len(answer.steps), "model_calls": answer.model_calls,
                          "tool_errors": sum(1 for s in answer.steps if s.get("error")),
                          # hand_backs = corrections that cost a round trip; repairs_total
                          # keeps the old key's meaning (constructions included)
                          "handbacks": answer.hand_backs,
                          "scope_shadow": answer.scope_shadow,
                          "repairs_total": len(answer.repairs),
                          "acts": list(answer.acts or []),
                          # The served TEXT, because several checks are about what the reader
                          # receives and cannot be evaluated from a graded row without it.
                          "answer_text": answer.answer, "explanation": answer.explanation,
                          # A compact trace on the row, so a failure can be diagnosed from stored
                          # results instead of re-run. Re-running gives a DIFFERENT sample, which
                          # is the wrong thing to diagnose when the question is why THIS run failed.
                          "steps": [{"tool": s.get("tool"), "args": s.get("args"),
                                     "error": bool(s.get("error")),
                                     "blocked": bool(s.get("blocked_by")),
                                     # the typed records gates decide on (answerability_gate reads
                                     # kind=raw here); a row without them cannot explain the gate
                                     "evidence": s.get("evidence") or None,
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
          f"disclosed={score['contested_disclosed']:<3} served={score['contested_served']:<3} "
          f"refused={score['contested_refused']}")
    print(f"\n  coverage {score['coverage']}   silent_error {score['silent_error']}   "
          f"balanced_accuracy {score['balanced_accuracy']}")
    # Summing-occurrence counter: the semi-additive roll-up (a run_sql that SUMs alongside a
    # distinct-count metric), measured DIRECTLY rather than via the score. A fix aimed at the
    # summing is measured by the summing, which varies far less than the graded outcome — the
    # interface fix (weekly means weekly) should drive this toward zero.
    semi_additive = {"active_users", "active_accounts", "paying_users"}

    def _summed(r) -> bool:
        steps = r.get("steps") or []
        sql_sum = any(s.get("tool") == "run_sql" and "sum(" in str(s.get("args") or {}).lower()
                      for s in steps)
        distinct = any(s.get("tool") == "query_metric"
                       and (s.get("args") or {}).get("metric") in semi_additive for s in steps)
        return sql_sum and distinct

    summed = sorted({r["id"] for r in rows if _summed(r)})
    if summed:
        print(f"  semi-additive SUMs (run_sql sum + a distinct-count metric): "
              f"{sum(1 for r in rows if _summed(r))}  {', '.join(summed)}")
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
