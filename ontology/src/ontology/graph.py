"""The marts ontology graph: a complete, closed-world model of what the warehouse captures.

Design: a functional core with an imperative shell.

  PURE CORE (no I/O — a function of plain data, so it tests without a database):
    from_source(source, columns_by_table) -> MartsOntology   assemble the graph
    island_source(manifest_source, all_tables) -> source     extend to the complete present (islands)
    joinable(edges, entities) -> bool                         can these entities be joined
    ontology.render() -> str                                  the text the model reads
    ontology.verify(kind, ...) -> (verdict, detail)           decide existence AND joinability
    ontology.fingerprint() -> str                             digest of everything the model reads
  IMPERATIVE SHELL (the only side effect is reading information_schema):
    build(cursor, schema, source) -> MartsOntology           fetch columns, then from_source
    build_marts(cursor, schema, manifest_source)             scan all tables, then build (complete graph)

Two halves are kept apart on purpose. The GRAPH (this module, deterministic) holds every entity —
with its grain — every attribute, measure and RELATIONSHIP the warehouse captures, generated from a
`source` read off the semantic-layer manifest and verified against information_schema. The MODEL
(elsewhere, in the agent) decomposes a natural-language measure into ingredients by meaning. The
graph never interprets language; the model never invents a node.

Absence is DERIVED from a complete present under the closed-world assumption, not enumerated: a
concept not in the graph does not exist. So there is no negative knowledge for a human to keep true —
the only property needed is that the present is complete, which generating from information_schema
gives by construction, and which fingerprint() (over the whole rendered surface) protects from drift.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# A node reference is `entity.column` (or `metric.<name>`). The model may wrap it in a description or
# a parenthetical restatement ("user.signup_date (the signup date)"); existence is a property of the
# REFERENCE, not of the model's surface formatting, so the token is extracted before it is checked.
# Matching the raw string would refuse a real node over an added space — the brittleness this avoids.
_NODE_REF = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")


def _node_ref(text: str) -> str:
    """The canonical `entity.column` (or `metric.<name>`) token the model intended, or '' if none."""
    m = _NODE_REF.search(text or "")
    return m.group(0) if m else ""

# The verdict vocabulary, defined once. The agent maps these to its reason codes; keeping the
# strings here (not spread across call sites) means the mapping has one place to read them from.
INSTRUMENTED = "instrumented"      # a governed metric answers directly
COMPUTABLE = "computable"          # no governed metric, but derivable from nodes that join
UNINSTRUMENTED = "uninstrumented"  # needs something absent from the complete graph


def joinable(edges: frozenset, entities) -> bool:
    """PURE. Are all `entities` in one relationship-connected component of `edges`? A measure derived
    from attributes on several entities is only computable if those entities can actually be joined —
    the edge check a node-existence check alone cannot make. Fewer than two entities is trivially
    joinable; an entity in no edge forms its own component and fails against any other.
    """
    entities = set(entities)
    if len(entities) <= 1:
        return True
    seen, frontier = set(), {next(iter(entities))}
    while frontier:
        node = frontier.pop()
        seen.add(node)
        for edge in edges:
            if node in edge:
                frontier |= (edge - seen)
    return entities <= seen


def _entity_name(table: str, taken) -> str:
    """A readable entity name for an unmodeled table: drop a `dim_`/`fct_` prefix, unless the result
    is empty or already taken, in which case keep the raw table name. Deterministic, not a heuristic —
    it only renames for the model's reading; the table it points at is unchanged."""
    stripped = table.split("_", 1)[1] if table.startswith(("dim_", "fct_")) else table
    return stripped if stripped and stripped not in taken else table


def island_source(manifest_source: dict, all_tables) -> dict:
    """PURE. Extend a manifest-read source to the COMPLETE present: every marts table becomes an
    entity, so absence is derivable over the whole warehouse. A table the manifest already models
    passes through unchanged (its curated grain, measures and relationships kept); a table it does
    NOT model becomes an ISLAND — its columns will be nodes, but it has no relationships, so it cannot
    be joined until one is curated in the manifest. This is why an incomplete graph can only
    under-claim a join, never invent one.
    """
    entities = dict(manifest_source["entities"])
    modeled = {spec["table"] for spec in entities.values()}
    taken = set(entities)
    for table in all_tables:
        if table in modeled:
            continue
        name = _entity_name(table, taken)
        taken.add(name)
        entities[name] = {"table": table, "grain": f"one row per {name}",
                          "measures": (), "relationships": ()}
    return {**manifest_source, "entities": entities}


@dataclass(frozen=True)
class MartsOntology:
    """A closed-world graph over the marts, as an immutable value. Assemble it with `build` (from a
    cursor) or `from_source` (from plain data); the model resolves a question against `render()`, and
    `verify()` decides the verdict from the graph — existence AND joinability."""

    entities: dict           # entity -> {"table", "grain", "attributes": tuple, "measures": tuple}
    edges: frozenset         # frozenset({entity_a, entity_b}) — undirected, traversable relationships
    edge_notes: tuple        # (from, to, note) for the model's reading
    metrics: dict            # metric name -> one-line description
    metric_dims: dict        # metric name -> {"entity", "dims"}: what it measures and filters by
    measure_semantics: dict  # measure column -> what it IS (positive description)
    nodes: frozenset         # every valid node reference: "entity.column" and "metric.<name>"

    # ── construction: pure core, then the impure shell ─────────────────────────────────────────
    @classmethod
    def from_source(cls, source: dict, columns_by_table: dict, measure_semantics=None) -> "MartsOntology":
        """PURE. Assemble the complete present-graph from a `source` (each entity's table, grain,
        measures and relationships, read from the manifest by the caller) and the columns of each
        table. ATTRIBUTES are every non-measure column, so the graph is complete and cannot claim a
        column the warehouse lacks; a declared measure that is not a column raises. No database here —
        this is the whole of the assembly logic, testable with dicts.
        """
        nodes, entities, edges, edge_notes = set(), {}, set(), []
        for ent, spec in source["entities"].items():
            table, meas = spec["table"], tuple(spec.get("measures", ()))
            cols = tuple(columns_by_table[table])
            missing = [m for m in meas if m not in cols]
            if missing:
                raise ValueError(f"{ent}: {table} has no column(s) {missing} declared as measures")
            nodes.update(f"{ent}.{col}" for col in cols)
            entities[ent] = {"table": table, "grain": " ".join((spec.get("grain") or "").split()),
                             "attributes": tuple(c for c in cols if c not in meas), "measures": meas}
            for to_ent, note in spec.get("relationships", ()):
                edges.add(frozenset((ent, to_ent)))
                edge_notes.append((ent, to_ent, note))
        nodes.update(f"metric.{m}" for m in source["metrics"])
        sem = {**(source.get("measure_semantics") or {}), **(measure_semantics or {})}
        return cls(entities=entities, edges=frozenset(edges), edge_notes=tuple(edge_notes),
                   metrics={m: " ".join((d or "").split()) for m, d in source["metrics"].items()},
                   metric_dims=dict(source.get("metric_dims") or {}),
                   measure_semantics=sem, nodes=frozenset(nodes))

    @classmethod
    def build(cls, cursor, schema: str, source: dict, measure_semantics=None) -> "MartsOntology":
        """The imperative shell: read each entity table's columns from information_schema, then hand
        them to the pure `from_source`. The only side effect in the module lives here."""
        tables = {spec["table"] for spec in source["entities"].values()}
        columns_by_table = {t: _fetch_columns(cursor, schema, t) for t in tables}
        return cls.from_source(source, columns_by_table, measure_semantics)

    @classmethod
    def build_marts(cls, cursor, schema: str, manifest_source: dict, measure_semantics=None) -> "MartsOntology":
        """Build the COMPLETE marts graph under hybrid completeness: scan EVERY table in the schema so
        the present is complete (absence is derivable), but keep relationships only where the manifest
        curates them — an unmodeled table is an island. This is the graph the agent makes authoritative
        on `uninstrumented`: it can under-claim a join (a not-yet-curated island reads as unjoinable),
        never invent one. `manifest_source` is what the semantic layer's ontology_source() returns."""
        full = island_source(manifest_source, _scan_tables(cursor, schema))
        return cls.build(cursor, schema, full, measure_semantics)

    # ── the model's view: pure ─────────────────────────────────────────────────────────────────
    def render(self, metric_desc_chars: int = 120) -> str:
        """The text the model resolves a question against, and the whole surface fingerprint() hashes.
        Asserts the closed-world stance once; states each entity's GRAIN; describes measures positively
        so a count is not mistaken for a duration."""
        out = [
            "MARTS ONTOLOGY.", "",
            "CLOSED WORLD: this graph lists EVERYTHING the warehouse captures — every entity, every "
            "attribute, every measure. It is COMPLETE. If a concept a question needs is not represented "
            "here, the warehouse does NOT capture it; assume nothing beyond this graph exists.", "",
            "Governed metrics (a direct answer, alone or combined as a ratio, if one fits):",
        ]
        for m in sorted(self.metrics):
            anchor = ""
            d = self.metric_dims.get(m)
            if d and d.get("dims"):
                # Anchor the metric to what it measures and the dimensions it is FILTERED by, so a
                # governed metric restricted to a segment/period/cohort grounds as governed rather
                # than being decomposed into raw columns.
                anchor = f" (measures {d['entity']}; filter by: {', '.join(d['dims'])})"
            out.append(f"  metric.{m}{anchor}: {self.metrics[m][:metric_desc_chars]}")
        out += ["", "Entities (a node is entity.attribute or entity.measure):"]
        for ent, d in self.entities.items():
            out.append(f"  {ent} ({d['table']}) — grain: {d['grain'] or 'one row per ' + ent}")
            out.append(f"      attributes: {', '.join(d['attributes']) or '(none)'}")
            meas = ", ".join(f"{m} [{self.measure_semantics.get(m, 'a measure')}]"
                             for m in d["measures"]) or "(none)"
            out.append(f"      measures:   {meas}")
        if self.edge_notes:
            out += ["", "Relationships (which entities can be joined):"]
            for a, b, note in self.edge_notes:
                out.append(f"  {a} <-> {b}: {note}")
        return "\n".join(out)

    # ── the seam: pure ─────────────────────────────────────────────────────────────────────────
    def verify(self, kind: str, metric: str = "", ingredients=()) -> tuple[str, str]:
        """Turn the model's decomposition into a verdict, deciding EXISTENCE and JOINABILITY.

        Returns (verdict, detail) where verdict is INSTRUMENTED, COMPUTABLE or UNINSTRUMENTED. The
        model proposes; the graph decides: a `governed` claim whose metric is not a node, a
        `computable` claim citing no ingredients, one naming an ingredient that is not a node, or one
        whose ingredients span entities that cannot be joined, is not upheld. Existence closes the
        absence gap; joinability closes the fan/chasm gap a node-only check would miss.
        """
        if kind == "governed":
            name = (_node_ref(metric) or metric).replace("metric.", "").strip()
            if f"metric.{name}" in self.nodes:
                return INSTRUMENTED, f"governed metric `{name}`"
            return UNINSTRUMENTED, f"claimed governed metric `{name}` is not in the graph"
        if kind == "computable":
            needed = [r for r in (_node_ref(i) for i in ingredients) if r]
            if not needed:
                return UNINSTRUMENTED, "computable claim cited no graph ingredients"
            absent = [r for r in needed if r not in self.nodes]
            if absent:
                return UNINSTRUMENTED, f"required ingredient(s) absent from the graph: {absent}"
            touched = {r.split(".", 1)[0] for r in needed}
            if not joinable(self.edges, touched):
                return UNINSTRUMENTED, f"entities {sorted(touched)} are not related — cannot be joined"
            return COMPUTABLE, f"ingredients exist and join: {needed}"
        return UNINSTRUMENTED, "measure needs an ingredient absent from the complete graph"

    # ── staleness: pure ────────────────────────────────────────────────────────────────────────
    def fingerprint(self) -> str:
        """A digest of EVERYTHING the model reads — the rendered surface. Changes iff any of it
        changes (entities, columns, grain, measures and their semantics, metrics, relationships), so a
        schema or manifest change forces a regenerate and a stale graph cannot lie."""
        return "sha256:" + hashlib.sha256(self.render().encode()).hexdigest()[:16]


def _fetch_columns(cursor, schema: str, table: str) -> tuple:
    """I/O: the ordered column names of one marts table."""
    rows = cursor.execute(
        "select column_name from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position",
        [schema, table]).fetchall()
    return tuple(r[0] for r in rows)


def _scan_tables(cursor, schema: str) -> tuple:
    """I/O: every table name in the marts schema, so completeness can be taken over the real present."""
    rows = cursor.execute(
        "select table_name from information_schema.tables "
        "where table_schema = ? order by table_name", [schema]).fetchall()
    return tuple(r[0] for r in rows)
