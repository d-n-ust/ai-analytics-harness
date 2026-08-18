"""Adapter for dbt's semantic layer (MetricFlow): `semantic_models:` + `metrics:` YAML.

A dbt MetricFlow project defines `measures` inside `semantic_models` and `metrics` that reference
them (by name), often split across many YAML files. This adapter merges those files, resolves each
metric back to the measure it aggregates, and normalises both metrics and (unwrapped) measures into
GroundingFacts so the detector compares the whole surface.

Two MetricFlow-specific translations happen here:
  - `model: ref('fct_orders')`  ->  base table `fct_orders`.
  - a metric `filter` written in Jinja, `{{ Dimension('order__status') }} = 'completed'`, is
    de-templated to `status = 'completed'` and parsed into scope predicates via scope.build_scope.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .adapters import additivity, gate_text
from .model import GroundingFact
from .scope import build_scope

_REF = re.compile(r"(?:ref|source)\(\s*(?:['\"][^'\"]+['\"]\s*,\s*)?['\"]([^'\"]+)['\"]")
_JINJA = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_QUOTED = re.compile(r"['\"]([^'\"]+)['\"]")


def _table(model: str | None) -> str | None:
    """`ref('fct_orders')` / `source('raw','orders')` / a bare name -> the table name."""
    if not model:
        return None
    m = _REF.search(model)
    return (m.group(1) if m else model.strip()).split(".")[-1].lower() or None


def _primary_entity(sm: dict) -> str | None:
    for e in sm.get("entities", []) or []:
        if e.get("type") == "primary":
            return e.get("name")
    return sm.get("name")


def _dimension_name(jinja_call: str) -> str:
    """`Dimension('order__status')` -> `status` (drop the entity prefix MetricFlow prepends)."""
    q = _QUOTED.search(jinja_call)
    ref = q.group(1) if q else jinja_call
    return ref.split("__")[-1]


def _parse_filter(filt) -> tuple:
    """MetricFlow metric `filter` (a Jinja string, or a list of them) -> scope predicates. Each
    `{{ Dimension('x__y') }}` / `{{ TimeDimension(...) }}` / `{{ Entity(...) }}` is replaced by the
    referenced name's last segment, leaving a plain SQL predicate that scope.build_scope parses."""
    if not filt:
        return ()
    parts = filt if isinstance(filt, list) else [filt]
    clauses = []
    for part in parts:
        sql = _JINJA.sub(lambda m: _dimension_name(m.group(1)), str(part)).strip()
        if sql:
            clauses.append(f"({sql})")
    return build_scope(" and ".join(clauses)) if clauses else ()


def _measure_ref(ref) -> str | None:
    return ref.get("name") if isinstance(ref, dict) else ref


def facts_from_metricflow(semantic_models: list[dict], metrics: list[dict]) -> list[GroundingFact]:
    """Resolve metrics through their measures and normalise both into GroundingFacts.

    Measure names are unique across a MetricFlow project, so a single global index resolves any
    metric's measure. A measure wrapped 1:1 by a no-filter simple metric is not emitted separately
    (the metric already represents it); other measures are emitted so measure-level collisions
    surface."""
    index: dict[str, dict] = {}
    for sm in semantic_models:
        base, entity = _table(sm.get("model")), _primary_entity(sm)
        for meas in sm.get("measures", []) or []:
            index[meas["name"]] = {"agg": meas.get("agg"), "expr": meas.get("expr") or meas["name"],
                                   "base": base, "entity": entity, "model": sm.get("name")}

    # A measure is not a user-selectable grounding in MetricFlow — end users query METRICS. So a
    # measure referenced by any metric is represented by that metric (its public face), even when the
    # metric filters it; only a truly orphan measure (no metric wraps it) is emitted, so measure-level
    # modelling gaps still surface without every filtered metric colliding with its own raw measure.
    referenced: set[str | None] = set()   # a metric may reference no measure; None is harmless here
    for m in metrics:
        tp = m.get("type_params", {}) or {}
        mtype = (m.get("type") or "simple").lower()
        if mtype == "simple":
            referenced.add(_measure_ref(tp.get("measure")))
        elif mtype == "ratio":
            referenced.add(_measure_ref(tp.get("numerator")))
            referenced.add(_measure_ref(tp.get("denominator")))

    facts: list[GroundingFact] = []
    for m in metrics:
        name, mtype = m["name"], (m.get("type") or "simple").lower()
        tp = m.get("type_params", {}) or {}
        scope = _parse_filter(m.get("filter"))
        text = gate_text(name, m.get("description", ""))
        if mtype == "simple":
            mi = index.get(_measure_ref(tp.get("measure")) or "", {})
            facts.append(GroundingFact(
                id=f"mf:{name}", label=name, layer="semantic", kind="metric",
                agg=mi.get("agg"), measure=mi.get("expr"), base=mi.get("base"), entity=mi.get("entity"),
                additive=additivity(mi.get("agg")), scope=scope, text=text))
        elif mtype == "ratio":
            num, den = _measure_ref(tp.get("numerator")), _measure_ref(tp.get("denominator"))
            mi = index.get(num or "", {})
            facts.append(GroundingFact(
                id=f"mf:{name}", label=name, layer="semantic", kind="metric",
                agg="ratio", measure=f"{num}/{den}", base=mi.get("base"), entity=mi.get("entity"),
                derived=True, scope=scope, text=text))
        else:                                   # derived | cumulative
            facts.append(GroundingFact(
                id=f"mf:{name}", label=name, layer="semantic", kind="metric",
                measure=tp.get("expr"), derived=True, scope=scope, text=text))

    for sm in semantic_models:
        base, entity = _table(sm.get("model")), _primary_entity(sm)
        for meas in sm.get("measures", []) or []:
            if meas["name"] in referenced:
                continue
            # kind="metric" so measures enter the comparison pool alongside metrics
            facts.append(GroundingFact(
                id=f"mf:measure:{sm.get('name')}.{meas['name']}", label=meas["name"],
                layer="semantic", kind="metric", agg=meas.get("agg"),
                measure=meas.get("expr") or meas["name"], base=base, entity=entity,
                additive=additivity(meas.get("agg")),
                text=gate_text(meas["name"], meas.get("description", ""))))
    return facts


def load_metricflow(path: str | Path) -> list[GroundingFact]:
    """Load a MetricFlow surface from a file or a directory (all *.yml/*.yaml merged — definitions
    routinely span files, and a metric references a measure defined elsewhere).

    Handles both MetricFlow YAML conventions: the dbt *project* form, where one document carries
    `semantic_models:` and `metrics:` as lists; and the standalone *multi-document* form the
    MetricFlow parser itself reads, where each `---`-separated document is a single `semantic_model:`
    or `metric:`. A directory can mix the two."""
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("*.yml")) + sorted(p.rglob("*.yaml"))
    semantic_models: list[dict] = []
    metrics: list[dict] = []
    for f in files:
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except (OSError, yaml.YAMLError):
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            semantic_models += doc.get("semantic_models") or []
            metrics += doc.get("metrics") or []
            if "semantic_model" in doc:        # standalone multi-document form (singular)
                semantic_models.append(doc["semantic_model"])
            if "metric" in doc:
                metrics.append(doc["metric"])
    return facts_from_metricflow(semantic_models, metrics)
