#!/usr/bin/env python3
"""Generate the spine over the exp06 fixture.

The spine has two halves, and only one is written by hand.

  BASE     everything the MetricFlow layer, the dbt models and the warehouse already state:
           entities, the join graph, measures and their source fact, the time role each is
           anchored on, the raw scope filter each carries, the categorical attributes, and — read
           straight from DuckDB — the coverage window of every fact and the member set of every
           attribute. This half is DERIVED. It cannot drift from the layer it describes because it
           is recomputed from it.

  OVERLAY  the governance facts NO source declares: the vocabulary (a word maps to a CANDIDATE
           SET, never one object), the relations between definitions (contested / alias /
           supersedes, with owner, evidence tier, status and policy), per-dimension additivity,
           the human name and meaning of each scope filter, owner and status per measure, and which
           raw column a normalised attribute was collapsed from. `overlay.yaml` is the whole of it,
           and its size is a finding: it is exactly what the semantic layer cannot express.

`spine.yaml` is BASE merged with OVERLAY, every node tagged `_from: generated | overlay` so a reader
can see which half a fact came from. Coverage and members are never hand-written (the harness rule);
the overlay never restates a fact the base already carries.

    python generate.py                       # writes spine.yaml beside this file
    python generate.py --db ../../../../runs/warehouse.duckdb
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import duckdb
import yaml

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE.parent / "fixture" / "layer" / "semantic_models.yml"
OVERLAY = HERE / "overlay.yaml"
OUT = HERE / "spine.yaml"
# The warehouse the fixture was materialised into. Coverage and member sets are read from here.
DEFAULT_DB = HERE.parents[3] / "runs" / "warehouse.duckdb"
MART_SCHEMA = "wh_06"


# ────────────────────────────── parse the MetricFlow layer ──────────────────────────────
def load_layer(path: pathlib.Path) -> tuple[dict, dict]:
    """Return (semantic_models, metrics) keyed by name. The file is MetricFlow's own multi-document
    YAML: one `semantic_model:` or `metric:` per document."""
    models, metrics = {}, {}
    for doc in yaml.safe_load_all(path.read_text()):
        if not doc:
            continue
        if "semantic_model" in doc:
            m = doc["semantic_model"]
            models[m["name"]] = m
        elif "metric" in doc:
            m = doc["metric"]
            metrics[m["name"]] = m
    return models, metrics


def primary_entity(model: dict) -> str | None:
    for e in model.get("entities", []):
        if e["type"] == "primary":
            return e["name"]
    return None


def entity_owner(models: dict) -> dict[str, str]:
    """The semantic model whose PRIMARY entity is e — the table a row of e lives in. Used to place
    an attribute on its entity and to resolve joins."""
    return {primary_entity(m): name for name, m in models.items() if primary_entity(m)}


# A MetricFlow metric filter is a Jinja `{{ Dimension('entity__dim') }} = value`. We keep the raw
# string (it is what the engine applies) and pull the (dimension, op, value) out for the base. The
# `.*?` skips the closing `}}` that sits between the Dimension call and the operator.
_FILTER = re.compile(r"Dimension\(\s*['\"](\w+)__(\w+)['\"]\s*\).*?(=|!=)\s*'?([\w-]+)'?")


def parse_filter(expr: str | None):
    if not expr:
        return None
    m = _FILTER.search(expr)
    if not m:
        return {"raw": expr.strip(), "dimension": None}
    ent, dim, op, val = m.groups()
    return {"raw": expr.strip(), "entity": ent, "dimension": dim, "op": op, "value": val}


# ────────────────────────────── read the warehouse ──────────────────────────────
def fact_of(model: dict) -> str:
    return model["node_relation"]["alias"]


def time_dimension(model: dict) -> str | None:
    return (model.get("defaults") or {}).get("agg_time_dimension")


def coverage(con, fact: str, time_col: str) -> dict | None:
    """The [min, max] of a fact's aggregation time dimension. This is what a coverage window IS, and
    the layer declares none — so it is computed, never written."""
    try:
        lo, hi = con.execute(
            f"select min({time_col}), max({time_col}) from {MART_SCHEMA}.{fact}"
        ).fetchone()
    except duckdb.Error:
        return None
    if lo is None:
        return None
    return {"from": lo, "to": hi, "_computed_from": f"{MART_SCHEMA}.{fact}.{time_col}"}


def members(con, fact: str, col: str) -> list | None:
    try:
        rows = con.execute(
            f"select distinct {col} from {MART_SCHEMA}.{fact} where {col} is not null order by 1"
        ).fetchall()
    except duckdb.Error:
        return None
    return [r[0] for r in rows]


def raw_members(con, ref: str) -> list | None:
    """DISTINCT of a raw source column, e.g. `_source.u.plat`. This is what staging collapses; the
    gap between this and the mart member set is the member-normalisation the layer does not declare.
    """
    schema, table, col = ref.replace('"', "").split(".")
    try:
        rows = con.execute(
            f'select distinct {col} from "{schema}".{table} order by 1'
        ).fetchall()
    except duckdb.Error:
        return None
    return [("<null>" if r[0] is None else r[0]) for r in rows]


# ────────────────────────────── build the base ──────────────────────────────
def build_base(models: dict, metrics: dict, con, overlay: dict) -> dict:
    owner = entity_owner(models)
    tag = lambda d: {**d, "_from": "generated"}

    # entities and the join graph. A foreign entity on a model is a many_to_one edge to the model
    # that owns that entity as primary — the shape MetricFlow's `entities` already encodes.
    entities, joins = {}, []
    for name, m in models.items():
        pe = primary_entity(m)
        if pe:
            entities.setdefault(pe, tag({"row_of": fact_of(m)}))
        for e in m.get("entities", []):
            if e["type"] == "foreign" and e["name"] in owner:
                joins.append(tag({"from": pe, "to": e["name"], "cardinality": "many_to_one"}))
    for e in owner:
        entities.setdefault(e, tag({}))

    # coverage per fact (computed)
    cov = {}
    for name, m in models.items():
        td = time_dimension(m)
        if td:
            c = coverage(con, fact_of(m), td)
            if c:
                cov[fact_of(m)] = tag(c)

    # attributes: every categorical dimension, placed on its model's primary entity, with its
    # member set read from the warehouse. raw member sets are filled where the overlay says which
    # raw column the attribute was normalised from.
    member_source = overlay.get("member_source", {})
    attributes = {}
    for name, m in models.items():
        pe = primary_entity(m)
        for d in m.get("dimensions", []):
            if d.get("type") == "categorical":
                a = tag({
                    "entity": pe,
                    "column": f"{MART_SCHEMA}.{fact_of(m)}.{d['name']}",
                    "values": members(con, fact_of(m), d["name"]),
                })
                if d["name"] in member_source:
                    ref = member_source[d["name"]]["raw"]
                    a["raw_values"] = raw_members(con, ref)
                    a["raw_column"] = ref
                attributes.setdefault(d["name"], a)

    # time roles: the aggregation time dimension of each model, named entity.dimension
    time_roles = {}
    for name, m in models.items():
        td, pe = time_dimension(m), primary_entity(m)
        if td:
            time_roles.setdefault(f"{pe}.{td}", tag({"entity": pe, "column": td}))

    # measures: the governed metrics the agent selects. We flatten metric -> its measure so a node
    # carries source fact, time role, the raw scope filter, and grain (what it counts).
    measures = {}
    for name, metric in metrics.items():
        node = tag({"type": metric.get("type", "simple")})
        tp = metric.get("type_params", {})
        base_measure = tp.get("measure")
        if base_measure:
            sm = next((mm for mm in models.values()
                       if any(x["name"] == base_measure for x in mm.get("measures", []))), None)
            if sm:
                spec = next(x for x in sm["measures"] if x["name"] == base_measure)
                node["source"] = fact_of(sm)
                node["measure"] = base_measure
                node["agg"] = spec["agg"]
                node["counts"] = _counts(spec, sm)
                td = time_dimension(sm)
                if td:
                    node["time_role"] = f"{primary_entity(sm)}.{td}"
        node["additivity"] = _additivity(node.get("agg"))  # derived from agg, not hand-written
        f = parse_filter(metric.get("filter"))
        if f:
            node["scope_filter"] = f  # the raw filter; the overlay names the population it is
        if metric.get("type") in ("derived", "ratio"):
            node["composes"] = tp  # keep the composition for the record
        measures[name] = node

    return {"entities": entities, "joins": joins, "coverage": cov,
            "attributes": attributes, "time_roles": time_roles, "measures": measures}


def _additivity(agg: str | None) -> dict:
    """Additivity is a property of the AGGREGATE, not a per-metric annotation. It falls out of `agg`
    by one rule, proven once here rather than written by hand for every metric (where it could drift
    from the aggregate it is supposed to describe).

      sum / count      additive       — sums over any dimension, including time
      count_distinct   semi-additive  — NOT additive over time: an entity active across several
                                        periods counts once, so a whole-period figure is not the
                                        sum of its sub-periods
      ratio / derived  non-additive   — the layer must compute it at the query grain
    """
    if agg in ("sum", "count"):
        return {"over_time": True, "kind": "additive"}
    if agg == "count_distinct":
        return {"over_time": False, "kind": "semi_additive",
                "note": "Distinct count: an entity active across several periods counts once, so a "
                        "whole-period figure is not the sum of its sub-periods."}
    return {"over_time": None, "kind": "non_additive",
            "note": "A ratio or derived metric is not additive; the layer computes it at the query grain."}


def _counts(measure_spec: dict, model: dict) -> str:
    """What one unit of a measure IS. A distinct count over an entity key counts that entity; a sum
    counts rows of the fact (its primary entity). This is the grain, and it decides which filters
    can be applied without multiplying rows."""
    if measure_spec["agg"] == "count_distinct":
        expr = measure_spec.get("expr", "")
        for e in model.get("entities", []):
            if e.get("expr") == expr or e["name"] == expr:
                return e["name"]
    return primary_entity(model)


# ────────────────────────────── merge ──────────────────────────────
def merge(base: dict, overlay: dict) -> dict:
    """BASE first, then OVERLAY sections that add what no source declares. The overlay never
    overwrites a generated fact; it adds sibling keys (owner, status, additivity, population name)
    and whole sections the base has no way to produce (vocabulary, relationships, populations)."""
    spine = dict(base)

    # per-measure governance annotations (owner, status, additivity, named population, validity)
    for name, ann in (overlay.get("measures") or {}).items():
        if name in spine["measures"]:
            for k, v in ann.items():
                spine["measures"][name][k] = v
                spine["measures"][name].setdefault("_from", "generated")
            spine["measures"][name]["_annotated_by"] = "overlay"

    # whole sections the base cannot produce
    for section in ("populations", "vocabulary", "relationships", "closure", "computable",
                    "not_captured", "parameter_phrasings", "methodological_rules", "structural_safety"):
        block = overlay.get(section)
        if block is None:
            continue
        if isinstance(block, list):
            spine[section] = [{**r, "_from": "overlay"} for r in block]
        elif all(isinstance(v, dict) for v in block.values()):
            spine[section] = {k: {**v, "_from": "overlay"} for k, v in block.items()}
        else:
            spine[section] = block  # a flat scalar block (e.g. closure flags), kept as-is

    # per-attribute governance (status, the human meaning of members)
    for name, ann in (overlay.get("attributes") or {}).items():
        if name in spine["attributes"]:
            spine["attributes"][name].update(ann)
            spine["attributes"][name]["_annotated_by"] = "overlay"

    return spine


_POP_FILTER = re.compile(r"\s*(\w+)\s*(=|!=)\s*'?([\w-]+)'?\s*$")


def check_drift(spine: dict) -> list[str]:
    """The overlay is hand-kept, so it can drift from the layer the base is generated from. A named
    segment declares the filter it stands for; the metric that references it carries the real one.
    If they disagree, the overlay is lying, so regeneration must stop rather than emit a spine whose
    governance annotations no longer describe the metrics."""
    drift = []
    segments = spine.get("populations", {})
    for name, m in spine["measures"].items():
        pop, sf = m.get("population"), m.get("scope_filter")
        declared = segments.get(pop, {}).get("filter") if pop else None
        if declared in (None, "none"):
            if declared == "none" and sf:
                drift.append(f"{name}: segment '{pop}' declares NO filter, but the metric carries "
                             f"[{sf.get('raw')}]")
            continue
        want = _POP_FILTER.match(declared)
        got = (sf.get("dimension"), sf.get("op"), str(sf.get("value")).lower()) if sf else None
        if not sf:
            drift.append(f"{name}: segment '{pop}' declares [{declared}], but the metric carries no filter")
        elif want and (want.group(1), want.group(2), want.group(3).lower()) != got:
            drift.append(f"{name}: segment '{pop}' declares [{declared}], but the metric filter is "
                         f"[{sf.get('raw')}]")
    return drift


def summarise(base: dict, overlay: dict) -> str:
    gen = sum(len(base[k]) for k in ("entities", "coverage", "attributes", "time_roles", "measures"))
    gen += len(base["joins"])
    over = (len(overlay.get("vocabulary", {})) + len(overlay.get("relationships", []))
            + len(overlay.get("populations", {}))
            + sum(len(v) for v in (overlay.get("measures") or {}).values())
            + sum(len(v) for v in (overlay.get("attributes") or {}).values()))
    return (f"generated nodes: {gen}  (entities/joins/coverage/attributes/time_roles/measures + "
            f"additivity, all recomputed from layer+warehouse)\n"
            f"overlay facts:   {over}  (vocabulary terms, relations, segments, and per-node "
            f"owner/status the layer cannot state)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    models, metrics = load_layer(LAYER)
    overlay = yaml.safe_load(OVERLAY.read_text()) if OVERLAY.exists() else {}
    con = duckdb.connect(args.db, read_only=True)
    base = build_base(models, metrics, con, overlay)
    spine = merge(base, overlay)

    drift = check_drift(spine)
    if drift:
        for d in drift:
            print(f"  DRIFT  {d}")
        sys.exit(f"{len(drift)} overlay segment(s) no longer match the metric filter. Fix the overlay "
                 f"before regenerating.")

    header = ("# GENERATED — do not edit by hand. `python spine/generate.py` rewrites this file from\n"
              "# the MetricFlow layer, the dbt models and the warehouse (coverage and members), then\n"
              "# merges spine/overlay.yaml. Every node is tagged `_from: generated | overlay`.\n")
    pathlib.Path(args.out).write_text(
        header + yaml.safe_dump(spine, sort_keys=False, default_flow_style=False, allow_unicode=True)
    )
    print(f"wrote {args.out}")
    print(summarise(base, overlay))


if __name__ == "__main__":
    main()
