"""What the two structural holes cost the stored runs. No model calls.

Two guardrails turned out to be mounted where the failure mode isn't:

  the coverage check saw only `filters`, and only their raw text — so the same scope spelled as a
  governed synonym ("asia pacific"), as a country synonym ("philippines"), or as a
  `group_by` breakdown reached the warehouse ungated;

  the OUTPUT CHECKS (R7-R9) run only when the model fills the optional `value` field —
  so an answer that states a number in prose and leaves `value` unset skips all three.

This scores both from stored rows, so the re-run scope is a measurement rather than a
guess. For the coverage check it separates two very different things:

    EXPOSURE   the trajectory pulled a row the coverage check would have blocked as a direct query.
               The model saw an out-of-coverage number.
    DEPENDENCE the number the run SERVED is one of those rows. Only these can move a
               graded outcome; the rest are near-misses.

Dependence is decided by recompiling the call and reading LABELLED rows back out of the
warehouse — for a breakdown, only the out-of-coverage member's own row counts, not the
whole result set.

    uv run python evals/components/coverage_audit.py                    # every stored run
    uv run python evals/components/coverage_audit.py --run runs/latest --json out.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import harness_paths
from agent.guardrails import parse_cell
from agent.guardrails.after import step_values
from agent.numbers import bare_number, parse_numbers
from evidence import num_match
from semantic.semantic import COVERAGE_DIMS, SemanticError, SemanticLayer
from warehouse.warehouse import QueryError, open_warehouse, run_query

RESULTS = harness_paths.RUNS


def _escapes_coverage(args: dict, sl: SemanticLayer) -> list[tuple]:
    """The governed members this call reports on that sit outside coverage.

    This started as its own implementation, written before the coverage check had one, and now defers
    to the layer's. Keeping the audit on the same answer as the coverage check is the point: a number
    that measures the hole with different logic from the code that closes it can drift out of
    agreement without either side being obviously wrong."""
    return sl.coverage_violations(filters=args.get("filters"), group_by=args.get("group_by"),
                                  start=args.get("start"), end=args.get("end"),
                                  period=args.get("period"))


def _uncovered_values(step: dict, escaped: list[tuple], sl: SemanticLayer) -> list[float] | None:
    """The numbers that exist in this call's result ONLY because out-of-coverage rows were
    included. For a filtered call that is every value it returned; for a breakdown it is the
    escaping members' own rows, read back with their labels. None means we could not
    recompute it, and the caller falls back to the whole result (conservative)."""
    args = step.get("args") or {}
    group_by = args.get("group_by") if isinstance(args.get("group_by"), list) else []
    dims = [d for d in group_by if d in COVERAGE_DIMS]
    if not dims:
        return step_values(step)
    try:
        sql = sl.compile(args["metric"], group_by=group_by, filters=args.get("filters"),
                         time_grain=args.get("time_grain"), start=args.get("start"),
                         end=args.get("end"), period=args.get("period"),
                         segment=args.get("segment"))
        cols, rows = run_query(sl.con, sql)
    except (SemanticError, QueryError, KeyError):
        return None
    bad = {member for _dim, member, _why in escaped if member is not None}
    idx = {c: i for i, c in enumerate(cols)}
    out = []
    for row in rows:
        if any(str(row[idx[d]]) in bad for d in dims if d in idx):
            out += [float(c) for c in row
                    if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return out


def _served_number(row: dict):
    """The number the run actually served: the model's typed claim when it made one, else
    the single number in the answer text. None when the answer is prose or a list."""
    if row.get("declared_value") is not None:
        return float(row["declared_value"])
    nums = parse_numbers(row.get("answer"))
    return nums[0] if len(nums) == 1 else None


def audit_coverage(rows: list[dict], sl: SemanticLayer) -> dict:
    exposure: Counter = Counter()
    dependence: Counter = Counter()
    cases: list[dict] = []
    for row in rows:
        cfg = row.get("config") or f"R{row.get('rrung')}"
        hits = []
        for step in row.get("steps") or []:
            if step.get("tool") != "query_metric" or step.get("error"):
                continue
            escaped = _escapes_coverage(step.get("args") or {}, sl)
            if escaped:
                hits.append((step, escaped))
        if not hits:
            continue
        exposure[cfg] += 1
        served = _served_number(row) if row.get("outcome") == "answer" else None
        if served is None:
            continue
        for step, escaped in hits:
            vals = _uncovered_values(step, escaped, sl)
            if vals is None:
                vals = step_values(step)          # could not recompute: assume the worst
            if any(num_match(served, v) for v in vals):
                dependence[cfg] += 1
                cases.append({"qid": row.get("qid"), "config": cfg, "model": row.get("model"),
                              "rung": row.get("rung"), "served": served,
                              "args": step.get("args"), "outcome_was": row.get("outcome"),
                              "graded_correct": row.get("correct"),
                              "graded_fabricated": row.get("fabricated"),
                              "expected_refuse": row.get("expected_refuse")})
                break
    return {"exposure": exposure, "dependence": dependence, "cases": cases}


def _guardrails(cfg: str):
    """The GuardrailSet a stored row's config label denotes. `label()` is built to round-trip
    through parse_cell; anything older or hand-written returns None."""
    try:
        return parse_cell(cfg)
    except (ValueError, AttributeError):
        return None


def audit_optout(rows: list[dict]) -> dict:
    """Answers at a check-bearing cell that never reached a check, split by WHY — two
    different defects that look identical in the rows:

      INERT   the cell runs output_validation without governed_numbers, so `value` and
              `source_metric` are not in the answer schema at all (tools.py `_answer_spec`
              adds them only under governed_numbers). verify_answer early-returns on every
              answer, so the guardrail cannot fire. Its measured contribution is zero by
              construction, not by evidence.
      OPTOUT  the field WAS offered and the model left it unset while giving an answer that
              IS a number, so it skipped checks that were live for its neighbours. Measured
              with the same detector the recovery uses, not "the text contains a digit" — a
              prose answer quoting a figure was never in scope for the numeric checks, and
              counting it inflates the hole.
    """
    inert: Counter = Counter()
    optout: Counter = Counter()
    eligible: Counter = Counter()
    cases: list[dict] = []
    for row in rows:
        cfg = row.get("config") or ""
        g = _guardrails(cfg)
        if g is None or row.get("outcome") != "answer":
            continue
        if not (g.output_validation or g.governed_numbers or g.trajectory_verify):
            continue
        eligible[cfg] += 1
        if not g.governed_numbers:                   # the schema never offered `value`
            inert[cfg] += 1
        elif row.get("declared_value") is None and bare_number(row.get("answer")) is not None:
            optout[cfg] += 1
            cases.append({"qid": row.get("qid"), "config": cfg, "model": row.get("model"),
                          "answer": str(row.get("answer"))[:60],
                          "graded_correct": row.get("correct")})
    return {"inert": inert, "optout": optout, "eligible": eligible, "cases": cases}


def load_rows(run: str | None) -> list[dict]:
    runs = [Path(run)] if run else sorted((RESULTS / "runs").glob("*"))
    rows = []
    for d in runs:
        raw = d / "raw.jsonl"
        if not raw.exists():
            continue
        for line in raw.open():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            r["_run"] = d.name
            rows.append(r)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(prog="coverage_audit.py")
    p.add_argument("--run", default=None, help="one run dir (default: every run in runs/)")
    p.add_argument("--json", default=None, help="also write the full record here")
    args = p.parse_args()

    rows = load_rows(args.run)
    sl = SemanticLayer(open_warehouse(create_star_views=True))
    coverage = audit_coverage(rows, sl)
    opt = audit_optout(rows)

    print(f"{len(rows)} stored rows\n")
    print("COVERAGE CHECK — trajectories that pulled an out-of-coverage governed row")
    print(f"  exposure  : {sum(coverage['exposure'].values())} runs saw one")
    print(f"  DEPENDENCE: {sum(coverage['dependence'].values())} runs SERVED one\n")
    for cfg in sorted(coverage["exposure"], key=lambda c: -coverage["exposure"][c]):
        dep = coverage["dependence"].get(cfg, 0)
        print(f"    {cfg:<28} exposure {coverage['exposure'][cfg]:>4}   served {dep:>4}")

    # Only a cell that HAS a coverage check can be said to have leaked; below it the same call is
    # expected behaviour, and counting it would flatter the coverage's measured contribution.
    gated = [c for c in coverage["cases"] if (_guardrails(c["config"]) or None) and _guardrails(c["config"]).coverage_check]
    refusals_owed = [c for c in gated if c["expected_refuse"]]
    print(f"\n  served at a cell WITH the coverage check on: {len(gated)}")
    print(f"    of those, on questions whose gold demands a refusal: {len(refusals_owed)}")
    print("    (the rest served a number computed partly from out-of-coverage rows on a "
          "question that expects an answer — wrong figure, grade may not notice)")
    for c in sorted(gated, key=lambda c: (c["qid"], c["config"]))[:10]:
        print(f"    {c['qid']:<28} {c['config'][:24]:<26} {c['model']:<18} served={c['served']}")

    print("\nOUTPUT CHECKS — answers at a check-bearing cell that never reached a check")
    rows_by = sorted(opt["eligible"], key=lambda c: -opt["eligible"][c])
    for cfg in rows_by[:12]:
        n_i, n_o, d = opt["inert"][cfg], opt["optout"][cfg], opt["eligible"][cfg]
        kind = "INERT (no `value` in schema)" if n_i else f"opt-out {n_o}/{d} ({n_o / d:.0%})"
        print(f"    {cfg[:56]:<58} {d:>4} answers   {kind}")
    tot_i, tot_o, tot_e = (sum(opt["inert"].values()), sum(opt["optout"].values()),
                           sum(opt["eligible"].values()))
    print(f"  INERT  : {tot_i} of {tot_e} answers sat in a cell whose schema omits `value` — "
          "output_validation without governed_numbers cannot fire at all")
    print(f"  OPT-OUT: {tot_o} answers had the field and left it unset while stating a number")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"rows": len(rows),
             "coverage_check": {"exposure": dict(coverage["exposure"]), "dependence": dict(coverage["dependence"]),
                      "cases": coverage["cases"]},
             "optout": {"inert": dict(opt["inert"]), "optout": dict(opt["optout"]),
                        "eligible": dict(opt["eligible"]), "cases": opt["cases"]}},
            indent=2, default=str))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
