#!/usr/bin/env python3
"""Stage 3 of the readiness audit: for each question in scope, what settled each slot of its query.

Reads one stored run; calls no model. For every slot of the governed query a question needs (the
metric, each filter, the period, the breakdown, the grain, the metric's own filter) it records the
value the system used, what settled it, and what the system did with it:

    settled by   the question (read by the decision model, with its confidence) · a declared word
                 (code) · a governance rule (code) · the metric's definition (code) · the agent alone
    outcome      proceed · disclose · ask · refuse

A slot the agent filled while the reading left it open, or set against a governed rule, is the
finding this stage exists for. (q_002's monthly grain is the governed one: weekly buckets would cross
the edges of 2026-H1, which starts on a Thursday.)

    python trace.py <run dir>        # writes trace.md beside this file
"""
from __future__ import annotations

import json
import pathlib
import sys

import yaml
from agent.guardrails.parameters import _trend_grain

HERE = pathlib.Path(__file__).resolve().parent
SETTLED = {"question": "the question (decision model)", "governed_principle": "a governance rule (code)",
           "governed_declaration": "the metric's definition (code)", "none": "nothing"}


def _outcome(decision: dict) -> str:
    return {"refuse": "refuse", "ungrounded": "ask"}.get(decision["state"],
                                                          "disclose" if decision.get("disclose") else "proceed")


def trace(row: dict, case: dict) -> list[dict]:
    readings = row.get("readings") or {}
    asked = readings.get("_question") or {}
    metric = case["expect"].get("metric")
    reading = readings.get(metric) or next((r for k, r in readings.items() if not k.startswith("_")), None)
    ran = [q for s in row["steps"] if s.get("tool") == "query_metric" and not s.get("blocked_by")
           for q in (s.get("grounded_queries") or [s["args"]])]
    rows = [{"slot": "metric", "value": ", ".join(sorted({q.get("metric") for q in ran})) or "-",
             "settled_by": (f"a declared word '{asked['term']}' (code)" if asked.get("term_known") and asked.get("term")
                            else "the agent alone"),
             "outcome": "proceed"}]
    if reading is None:
        return rows + [{"slot": "(no reading)", "value": "-", "settled_by": "-", "outcome": row["outcome"]}]
    answers = reading.get("answers") or {}
    for d in reading["decisions"]:
        slot = d["parameter"] if d["parameter"] != "filter" else f"filter {str(d['value']).split(' = ')[0].split('__')[-1]}"
        conf = d.get("confidence")
        if d["basis"] == "question" and conf is None and d["parameter"] == "period":
            conf = max((v.get("noul", 0) for k, v in answers.items() if k.startswith("period:")), default=None)
        rows.append({"slot": slot, "value": str(d["value"]),
                     "settled_by": SETTLED.get(d["basis"], d["basis"]) + (f", {conf:.2f}" if conf else ""),
                     "outcome": _outcome(d)})
    # The grain: the governed rule's grain for the period, against the grain the agent's call set.
    grains = {q.get("time_grain") for q in ran if q.get("time_grain")}
    if any("metric_time" in (q.get("group_by") or []) for q in ran):
        rule = reading.get("rule") or {}
        governed = _trend_grain(rule, reading["periods"][0])[0] if rule and reading["periods"] else None
        same = bool(grains) and grains == {governed}
        rows.append({"slot": "time grain", "value": ", ".join(sorted(grains)) or governed or "-",
                     "settled_by": (f"the agent; the governed rule gives {governed}" if grains else
                                    "a governance rule (code)"),
                     "outcome": "proceed" + ("" if same or not grains else " (differs from the governed grain)")})
    return rows


def main() -> None:
    run_dir = pathlib.Path(sys.argv[1]).resolve()
    scope = yaml.safe_load((HERE / "scope.yml").read_text())
    suites = HERE.parent / "01_parameter_grounding"
    cases = {c["id"]: c for q in scope["questions"]
             for c in yaml.safe_load((suites / q["suite"]).read_text())["cases"]}
    rows = {r["qid"]: r for r in (json.loads(line) for line in (run_dir / "raw.jsonl").open())}
    out = [f"# Trace (stage 3)", "", f"Run `{run_dir.name}`. One row per slot of each question's query.", ""]
    for q in scope["questions"]:
        row, case = rows[q["id"]], cases[q["id"]]
        out += [f"## {q['id']}", "", f"\"{case['question']}\" — {row['outcome']}, "
                f"{'correct' if row['correct'] else 'not correct'}", "",
                "| slot | value | settled by | outcome |", "|---|---|---|---|"]
        out += [f"| {t['slot']} | {t['value']} | {t['settled_by']} | {t['outcome']} |" for t in trace(row, case)]
        out.append("")
    (HERE / "trace.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
