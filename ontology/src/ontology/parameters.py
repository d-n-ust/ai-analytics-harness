"""The parameter surface of one metric: which query parameters exist, and which values are legal.

Once a metric is chosen, a query is the metric plus a set of parameter decisions: filters, group-by
dimensions, time grain and period. This module lists the legal choices for each, so that EXISTENCE
is a lookup rather than a judgement (is `region` a dimension of this metric? is `android` a member of
`platform`?). It also carries each dimension's description, which is what the model reads to map a
phrase such as "by market" onto a real dimension. There are no phrase tables here: the model does
the open mapping against descriptions, and this module supplies the closed set it is checked against.

A metric can be filtered and grouped by the categorical dimensions of the semantic model its measure
lives on, and by those of every model whose primary entity is a foreign entity of that model. That
is MetricFlow's join rule. Omitting the join-reachable dimensions would make the surface incomplete,
and an incomplete closed set rejects legal values.

Additivity is not decided here. The surface reports the measure's aggregation (`agg`), and the agent
classifies it (`agent.core.measure`), because the dependency runs agent -> ontology and the rule must
live in one place.

Design, as in `graph.py`: a pure core and an imperative shell.

  PURE    load_layer(text) -> (models, metrics)          parse MetricFlow's multi-document YAML
          reachable_dimensions(models, metrics, metric)  the dimensions a metric may use
          parameter_surface(models, metrics, metric, members) -> dict
  SHELL   build(cursor, layer_text, metric)              read member sets, then parameter_surface
"""
from __future__ import annotations

import re

import yaml

__all__ = ["TIME_GRAINS", "PERIOD_GRAMMAR", "load_layer", "metric_filter", "reachable_dimensions",
           "parameter_surface", "build"]

# The same tuple as warehouse.config.TIME_GRAINS, which this package cannot import (it depends on
# nothing project-internal); harness/tests/test_parameter_grounding.py fails when the two differ.
TIME_GRAINS = ("day", "week", "month", "quarter", "year")
PERIOD_GRAMMAR = ("YYYY-MM", "YYYY-Qn", "YYYY-Hn", "last_week", "last_month", "last_quarter",
                  "ytd", "all")

# A member set longer than this is treated as open (free text): listing it would not help the model,
# and a closed-set check over a truncated list would reject real values.
MAX_MEMBERS = 50


def load_layer(text: str) -> tuple[dict, dict]:
    """PURE. (semantic_models, metrics), each keyed by name, from MetricFlow's multi-document YAML:
    one `semantic_model:` or `metric:` per document."""
    models, metrics = {}, {}
    for doc in yaml.safe_load_all(text):
        if not doc:
            continue
        if "semantic_model" in doc:
            models[doc["semantic_model"]["name"]] = doc["semantic_model"]
        elif "metric" in doc:
            metrics[doc["metric"]["name"]] = doc["metric"]
    return models, metrics


def _entities(model: dict, kind: str) -> list[str]:
    return [e["name"] for e in model.get("entities", []) if str(e["type"]).endswith(kind)]


def _measure_home(models: dict, metrics: dict, metric: str) -> tuple[dict, dict]:
    """The semantic model the metric's measure lives on, and the measure itself. A derived or ratio
    metric is followed to the first base metric that resolves to a measure."""
    seen, stack = set(), [metric]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        params = metrics[name].get("type_params", {})
        base = params.get("measure")
        if base:
            for model in models.values():
                for measure in model.get("measures", []):
                    if measure["name"] == base:
                        return model, measure
        refs = list(params.get("metrics") or [])
        if "numerator" in params:
            refs += [params["numerator"], params["denominator"]]
        stack.extend(r["name"] if isinstance(r, dict) else r for r in refs)
    raise ValueError(f"metric {metric!r} resolves to no measure in the layer")


# A MetricFlow metric filter is Jinja: `{{ Dimension('activity__is_internal') }} = false`. The raw
# string is what the engine applies; the readable form is what a reader is told.
_JINJA_DIM = re.compile(r"\{\{\s*Dimension\(\s*['\"]([\w]+)['\"]\s*\)\s*\}\}")


def metric_filter(metrics: dict, metric: str) -> str | None:
    """PURE. The filter the metric applies by definition, in readable form, or None. The agent
    cannot change it, and it is exactly the decision a reader does not see unless told."""
    raw = metrics[metric].get("filter")
    return _JINJA_DIM.sub(r"\1", " ".join(str(raw).split())) if raw else None


def reachable_dimensions(models: dict, metrics: dict, metric: str) -> list[dict]:
    """PURE. The categorical dimensions the metric may filter or group by: its own model's, then
    those of every model whose primary entity is a foreign entity of its own model."""
    own, _ = _measure_home(models, metrics, metric)
    foreign = set(_entities(own, "foreign"))
    homes = [own] + [m for m in models.values() if m is not own and _entities(m, "primary")
                     and _entities(m, "primary")[0] in foreign]
    out = []
    for model in homes:
        entity = _entities(model, "primary")[0]
        for d in model.get("dimensions", []):
            if d.get("type") == "categorical":
                rel = model["node_relation"]
                table = f"{rel['schema_name']}.{rel['alias']}" if rel.get("schema_name") else rel["alias"]
                out.append({"name": f"{entity}__{d['name']}", "entity": entity,
                            "table": table, "column": d["name"],
                            # A dimension may be an expression over the table (cohort_month is
                            # strftime(started_date, ...)); its members are read through it.
                            "expr": d.get("expr") or d["name"],
                            "description": " ".join((d.get("description") or "").split()),
                            # What a value means when its name does not say it ("unknown"), and
                            # what to say whenever a figure is restricted by the dimension.
                            "meanings": ((d.get("config") or {}).get("meta") or {}).get("values") or {},
                            "disclose": ((d.get("config") or {}).get("meta") or {}).get("disclose") or "",
                            # The owner declares the list complete: an unlisted value is not in the data.
                            "complete": bool(((d.get("config") or {}).get("meta") or {}).get("complete")),
                            "joined": model is not own})
    return out


def parameter_surface(models: dict, metrics: dict, metric: str, members: dict,
                      determines: dict | None = None) -> dict:
    """PURE. The whole parameter surface of `metric`. `members` maps (table, column) to that
    column's member list, or to None where the set is open; a missing key is an open set.
    `determines` maps a dimension name to the dimensions it determines, each with the value map
    {its value: their value} (see `build`)."""
    _, measure = _measure_home(models, metrics, metric)
    dims = [{**d, "members": members.get((d["table"], d["column"]))}
            for d in reachable_dimensions(models, metrics, metric)]
    return {
        "metric": metric,
        # Every entity's name and declared label ("user", "account"): the words for the rows counted.
        "entities": sorted({w for m in models.values() for e in m.get("entities", [])
                            for w in (e["name"], e.get("label")) if w}),
        "description": " ".join((metrics[metric].get("description") or "").split()),
        "agg": measure.get("agg"),
        "filter": metric_filter(metrics, metric),
        "parameters": {
            "filters": {"how": "equality on any dimension below", "dimensions": dims,
                        "determines": dict(determines or {})},
            "group_by": {"how": "any dimension below, or metric_time for a time series",
                         "dimensions": [d["name"] for d in dims] + ["metric_time"]},
            "time_grain": {"how": "bucket a time series", "legal_values": list(TIME_GRAINS)},
            "period": {"how": "the time window", "grammar": list(PERIOD_GRAMMAR)},
        },
    }


def _members(cursor, table: str, column: str) -> list | None:
    rows = cursor.execute(f"SELECT DISTINCT {column} FROM {table} "
                          f"WHERE {column} IS NOT NULL ORDER BY 1 LIMIT {MAX_MEMBERS + 1}").fetchall()
    return None if len(rows) > MAX_MEMBERS else [r[0] for r in rows]


def _determines(cursor, table: str, a: str, b: str) -> dict | None:
    """{value of a: value of b} when each value of `a` comes with exactly one value of `b` in the data
    (country -> region), else None. Read from the rows, not from a description, so it holds for the
    warehouse as it is. The map lets a reader see that two filters keep the same rows ("platform in
    android, ios" and "device_type = mobile")."""
    rows = cursor.execute(f"SELECT {a}, min({b}), count(DISTINCT {b}) FROM {table} "
                          f"WHERE {a} IS NOT NULL GROUP BY {a}").fetchall()
    return {va: vb for va, vb, _n in rows} if rows and all(n == 1 for *_v, n in rows) else None


def build(cursor, layer_text: str, metric: str) -> dict:
    """The imperative shell: read each reachable dimension's member set from the table the layer
    names (`node_relation`), and which closed dimensions determine which within a table, then hand
    everything to the pure `parameter_surface`."""
    models, metrics = load_layer(layer_text)
    dims = reachable_dimensions(models, metrics, metric)
    members = {(d["table"], d["column"]): _members(cursor, d["table"], d["expr"]) for d in dims}
    closed = [d for d in dims if members.get((d["table"], d["column"]))]
    size = lambda d: len(members[(d["table"], d["column"])])            # noqa: E731
    determines: dict = {}
    # A pair with as many values on each side (country and country_name) determines both ways; it is
    # recorded once, from the first in layer order, so that neither reads as implied by the other.
    for i, a in enumerate(closed):
        for j, b in enumerate(closed):
            if (a is not b and a["table"] == b["table"]
                    and (size(a) > size(b) or size(a) == size(b) and i < j)):
                values = _determines(cursor, a["table"], a["expr"], b["expr"])
                if values is not None:
                    determines.setdefault(a["name"], {})[b["name"]] = values
    return parameter_surface(models, metrics, metric, members, determines)
