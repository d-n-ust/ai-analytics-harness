"""The marts ontology graph: a complete, closed-world model of what the warehouse captures.

Two halves, kept apart on purpose:

  the GRAPH (this module, deterministic)   — every entity, attribute, measure and relationship the
                                             warehouse holds, generated and verified against
                                             information_schema. It answers one question: does this
                                             node EXIST? Closure is a stance (the graph is complete),
                                             never an enumerated list of what is absent.
  the SEAM (this module, deterministic)    — given a measure the model has decomposed into
                                             ingredients, verify() confirms those ingredients exist
                                             and returns instrumented / computable / uninstrumented.
  the MODEL (elsewhere, in the agent)       — decomposes a natural-language measure into ingredients
                                             by meaning. The graph never interprets language; the
                                             model never invents a node.

Absence is DERIVED from a complete present under the closed-world assumption, not stated: a concept
not in the graph does not exist. So there is no negative knowledge for a human to keep true — the
only guarantee needed is that the present is complete, which generating from information_schema gives
by construction, and which fingerprint() protects against schema drift.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MartsOntology:
    """A closed-world graph over the marts. Build it with `build`; the model resolves a question
    against `render()`, and `verify()` decides the verdict from the graph."""

    entities: dict           # entity -> {"table": str, "attributes": [str], "measures": [str]}
    relationships: tuple     # (from_entity, to_entity, note)
    metrics: dict            # metric name -> one-line description
    measure_semantics: dict  # measure column -> what it IS (positive description)
    nodes: frozenset         # every valid node reference: "entity.column" and "metric.<name>"

    # ── build ────────────────────────────────────────────────────────────────────────────────
    @classmethod
    def build(cls, cursor, schema: str, entity_tables: dict, metrics: dict,
              relationships=(), measure_semantics=None) -> "MartsOntology":
        """Generate the complete present-graph.

        `entity_tables` maps a conceptual entity to its (table, [measure columns]); the ATTRIBUTES
        are generated as every other column of that table, read from information_schema, so the graph
        is complete by construction and cannot claim a column the warehouse lacks. In production the
        entity/measure mapping and the relationships come from the semantic-layer manifest; here they
        are passed in so this module stays warehouse-agnostic.
        """
        measure_semantics = dict(measure_semantics or {})
        nodes, entities = set(), {}
        for ent, (table, meas) in entity_tables.items():
            cols = [r[0] for r in cursor.execute(
                "select column_name from information_schema.columns "
                "where table_schema = ? and table_name = ? order by ordinal_position",
                [schema, table]).fetchall()]
            missing = [m for m in meas if m not in cols]
            if missing:
                raise ValueError(f"{ent}: {table} has no column(s) {missing} declared as measures")
            attrs = [c for c in cols if c not in meas]
            for col in cols:
                nodes.add(f"{ent}.{col}")
            entities[ent] = {"table": table, "attributes": attrs, "measures": list(meas)}
        for m in metrics:
            nodes.add(f"metric.{m}")
        return cls(entities=entities, relationships=tuple(relationships),
                   metrics={m: " ".join((d or "").split()) for m, d in metrics.items()},
                   measure_semantics=measure_semantics, nodes=frozenset(nodes))

    # ── the model's view ───────────────────────────────────────────────────────────────────────
    def render(self, metric_desc_chars: int = 120) -> str:
        """The text the model resolves a question against. Asserts the closed-world stance once;
        lists the complete present; describes each measure positively so a count is not mistaken for
        a duration."""
        out = [
            "MARTS ONTOLOGY.", "",
            "CLOSED WORLD: this graph lists EVERYTHING the warehouse captures — every entity, every "
            "attribute, every measure. It is COMPLETE. If a concept a question needs is not "
            "represented here, the warehouse does NOT capture it; assume nothing beyond this graph "
            "exists.", "",
            "Governed metrics (a direct answer, alone or combined as a ratio, if one fits):",
        ]
        for m in sorted(self.metrics):
            out.append(f"  metric.{m}: {self.metrics[m][:metric_desc_chars]}")
        out += ["", "Entities, their attributes, and the measures they support "
                "(a node is entity.attribute or entity.measure):"]
        for ent, d in self.entities.items():
            out.append(f"  {ent} ({d['table']}):")
            out.append(f"      attributes: {', '.join(d['attributes']) or '(none)'}")
            meas = ", ".join(f"{m} [{self.measure_semantics.get(m, 'a measure')}]"
                             for m in d["measures"]) or "(none)"
            out.append(f"      measures:   {meas}")
        if self.relationships:
            out += ["", "Relationships:"]
            for a, b, note in self.relationships:
                out.append(f"  {a} -> {b}: {note}")
        return "\n".join(out)

    # ── the seam ───────────────────────────────────────────────────────────────────────────────
    def verify(self, kind: str, metric: str = "", ingredients=()) -> tuple[str, str]:
        """Turn the model's decomposition into a verdict, deciding EXISTENCE deterministically.

        Returns (verdict, detail) where verdict is 'instrumented', 'computable', or 'uninstrumented'.
        The model proposes; the graph decides: a `governed` claim whose metric is not a real node,
        or a `computable` claim naming an ingredient that is not a real node, is not upheld. Join
        keys (columns ending in _id) are relationships the graph already carries, so they are not
        required to appear as ingredient nodes.
        """
        if kind == "governed":
            name = metric.replace("metric.", "").strip()
            if f"metric.{name}" in self.nodes:
                return "instrumented", f"governed metric `{name}`"
            return "uninstrumented", f"claimed governed metric `{name}` is not in the graph"
        if kind == "computable":
            needed = [str(i).strip() for i in ingredients if not str(i).strip().endswith("_id")]
            absent = [i for i in needed if i not in self.nodes]
            if absent:
                return "uninstrumented", f"required ingredient(s) absent from the graph: {absent}"
            return "computable", f"all ingredients exist: {needed}"
        return "uninstrumented", "measure needs an ingredient absent from the complete graph"

    # ── staleness ────────────────────────────────────────────────────────────────────────────
    def fingerprint(self) -> str:
        """A digest of the graph's structure. Changes iff the entities, columns, measures, or
        relationships change — so a schema change forces a regenerate and stale closure cannot lie."""
        surface = json.dumps({"entities": self.entities,
                              "relationships": [list(r) for r in self.relationships],
                              "metrics": sorted(self.metrics)}, sort_keys=True)
        return "sha256:" + hashlib.sha256(surface.encode()).hexdigest()[:16]
