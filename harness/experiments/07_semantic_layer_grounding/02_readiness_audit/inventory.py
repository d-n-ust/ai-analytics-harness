#!/usr/bin/env python3
"""Stage 1 of the readiness audit: what exists for each element in scope, and where it comes from.

Reads the semantic layer, the governance file and the warehouse; calls no model. For each element in
`scope.yml` it records the facts a later stage rates, and raises a flag wherever the layer leaves
something unstated that a question can depend on:

    metric       its type, aggregation and additivity, its own filter, the time dimension a period
                 applies to, coverage, owner, declared words, and other metrics on the same measure
    dimension    every entity path that reaches it, its description, where its value set comes from,
                 the values the description does not mention, coverage per value, what it determines
    time         the period forms and the grains the runtime accepts, against MetricFlow's
    rules        the governance rules in scope, and any word the governance file uses for two things

    python inventory.py              # writes inventory.json and inventory.md beside this file
"""
from __future__ import annotations

import json
import pathlib
import sys

import yaml
from agent.guardrails import parse_cell
from agent.guardrails.forks import facts_of
from agent.guardrails.parameters import surface_for
from agent.runtime.grounding import build_grounding
from ontology.parameters import TIME_GRAINS, load_layer
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402

METRICFLOW_GRAINS = ("day", "week", "month", "quarter", "year")
ADDITIVITY = {"sum": "additive", "count": "additive", "count_distinct": "semi-additive (not over time, "
              "not over a dimension an entity can hold several values of)", "average": "non-additive"}


def _flag(out: list, element: str, what: str) -> None:
    out.append({"element": element, "flag": what})


def metric_facts(name: str, models: dict, metrics: dict, semantic, flags: list) -> dict:
    spec = metrics[name]
    measure = (spec.get("type_params") or {}).get("measure")
    home = next((m for m in models.values() for x in m.get("measures") or [] if x["name"] == measure), {})
    agg = next((x.get("agg") for x in home.get("measures") or [] if x["name"] == measure), None)
    meta = (spec.get("config") or {}).get("meta") or {}
    rivals = [m for m, s in metrics.items() if m != name and (s.get("type_params") or {}).get("measure") == measure]
    words = sorted({w for f in facts_of(semantic) if f.label == name for c in f.claims for w in c.words})
    lo, hi = semantic.coverage_window(name)
    if not meta.get("owner"):
        _flag(flags, name, "no owner")
    if not words:
        _flag(flags, name, "declares no words")
    return {"type": spec.get("type"), "measure": measure, "aggregation": agg,
            "additivity": ADDITIVITY.get(agg, "unknown"), "own_filter": spec.get("filter"),
            "time_anchor": (home.get("defaults") or {}).get("agg_time_dimension"),
            "coverage": [str(lo), str(hi)], "owner": meta.get("owner"), "declared_words": words,
            "same_measure": rivals}


def dimension_facts(short: str, metric: str, surface: dict, metric_info: dict, con, flags: list) -> dict:
    dims = [d for d in surface["parameters"]["filters"]["dimensions"] if d["column"] == short]
    if not dims:
        _flag(flags, short, f"not reachable from {metric}")
        return {"paths": []}
    own = next((d for d in dims if not d["joined"]), dims[0])
    if len(dims) > 1:
        _flag(flags, short, f"reachable by {len(dims)} entity paths: {', '.join(d['name'] for d in dims)}")
    members = own["members"] or []
    described = [m for m in members if str(m).lower() in own["description"].lower()]
    undescribed = [m for m in members if m not in described]
    if undescribed and not isinstance(members[0], bool):
        _flag(flags, short, f"values the description does not explain: {undescribed}")
    if metric_info["own_filter"] and short in metric_info["own_filter"]:
        _flag(flags, short, f"fixed by {metric}'s own filter")
    time_col = metric_info["time_anchor"]
    rows = con.execute(f"select {own['expr']} as v, count(*), min({time_col}), max({time_col}) "
                       f"from {own['table']} group by 1 order by 1").fetchall()
    # A gap a question can hit: a value with no rows in a whole calendar month the metric covers
    # ("app opens in the Philippines in October 2025" returns nothing). Days missing at the edges
    # of the data are ramp-up, not a gap.
    months = [m for (m,) in con.execute(
        f"select distinct strftime({time_col}, '%Y-%m') from {own['table']} "
        f"where {time_col} >= date_trunc('month', date '{metric_info['coverage'][0]}') + interval 1 month "
        f"and {time_col} < date_trunc('month', date '{metric_info['coverage'][1]}') order by 1").fetchall()]
    present = {(str(v), mm) for v, mm in con.execute(
        f"select distinct {own['expr']}, strftime({time_col}, '%Y-%m') from {own['table']}").fetchall()}
    gaps = {str(v): [mm for mm in months if (str(v), mm) not in present] for v in members}
    gaps = {v: g for v, g in gaps.items() if g}
    if gaps:
        _flag(flags, short, f"values with no data in a whole covered month: {gaps}")
    determines = surface["parameters"]["filters"].get("determines") or {}
    return {"paths": [d["name"] for d in dims], "description": own["description"],
            "value_set_source": "read from data at run time (SELECT DISTINCT); no value list is declared",
            "values": members, "described_values": described, "declared_aliases": [],
            "coverage_per_value": [{"value": str(v), "rows": n, "first": str(a), "last": str(b)} for v, n, a, b in rows],
            "determines": [x.split("__")[-1] for k, xs in determines.items() if k.split("__")[-1] == short for x in xs]}


def main() -> None:
    scope = yaml.safe_load((HERE / "scope.yml").read_text())
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    cur = R.scoped_cursor(con)
    semantic = build_grounding(cur, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                               guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    models, metrics = load_layer("\n---\n".join(p.read_text() for p in sorted(R.LAYER.glob("*.y*ml"))))
    flags: list = []
    metric = scope["metric"]
    m = metric_facts(metric, models, metrics, semantic, flags)
    surface = surface_for(semantic, cur, metric)
    dims = {d: dimension_facts(d, metric, surface, m, cur, flags) for d in scope["dimensions"]}
    missing_grains = [g for g in METRICFLOW_GRAINS if g not in TIME_GRAINS]
    if missing_grains:
        _flag(flags, "time_grain", f"MetricFlow grains the runtime does not accept: {missing_grains}")
    time = {"period_forms": surface["parameters"]["period"]["grammar"], "runtime_grains": list(TIME_GRAINS),
            "metricflow_grains": list(METRICFLOW_GRAINS), "coverage": m["coverage"]}
    rules = {r["id"]: r for r in R.GOVERNANCE.get("methodological_rules") or [] if r["id"] in scope["rules"]}
    if "segments" in R.GOVERNANCE and any("segment" in rid for rid in rules):
        _flag(flags, "governance", "'segment' names two things: the key `segments` (populations: "
              f"{', '.join(R.GOVERNANCE['segments'])}) and the rule `canonical_segments` (dimensions)")
    inventory = {"scope": scope, "metric": {metric: m}, "dimensions": dims, "time": time,
                 "rules": rules, "flags": flags}
    (HERE / "inventory.json").write_text(json.dumps(inventory, indent=1, default=str))
    lines = ["# Inventory (stage 1)", "", f"Metric `{metric}`: {m['type']}, `{m['aggregation']}` ({m['additivity']}); "
             f"own filter `{m['own_filter']}`; a period applies to `{m['time_anchor']}`; data {m['coverage'][0]} "
             f"to {m['coverage'][1]}; owner {m['owner']}; words {m['declared_words']}; same measure: "
             f"{m['same_measure'] or 'none'}.", "", "| dimension | paths | values | value-set source |", "|---|---|---|---|"]
    lines += [f"| {d} | {', '.join(f['paths'])} | {', '.join(map(str, f.get('values', [])))} | "
              f"{f.get('value_set_source', '')} |" for d, f in dims.items()]
    lines += ["", "## Flags", "", "| element | flag |", "|---|---|"]
    lines += [f"| {f['element']} | {f['flag']} |" for f in flags]
    (HERE / "inventory.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
