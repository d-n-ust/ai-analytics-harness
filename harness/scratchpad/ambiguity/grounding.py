#!/usr/bin/env python3
"""Common grounding-fact representation + one adapter per artifact type.

A grounding fact is anything an agent could read to ground a query on: a semantic-layer metric, a
warehouse column or view, or a documented term. All three are normalised into ONE shape so the
collision detector runs over the whole surface at once, including collisions that cross layers
(a doc's "revenue" vs a metric named `revenue` vs a column `fct_orders.revenue`).

    core   = GroundingFact
    adapt_semantic / adapt_warehouse / adapt_docs   pull each artifact up into that shape
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

import sqlglot
import yaml
from sqlglot import exp


@dataclass
class GroundingFact:
    id: str                       # unique, layer-prefixed: "sl:net_revenue", "wh:fct_orders.revenue"
    label: str                    # the bare term a reader sees / would say: "net_revenue", "revenue"
    layer: str                    # semantic | warehouse | docs
    kind: str                     # metric | dimension | segment | column | table | view | term
    entity: str | None = None     # what is counted (meaning)
    agg: str | None = None        # aggregation (meaning)
    base: str | None = None       # source table (meaning)
    measure: str | None = None    # measured column/expr (meaning)
    grain: str | None = None      # group-by level (day/week/month) — the 4th canonical slot
    additive: str | None = None   # additive | semi | non — derived from agg, never per-metric
    scope: tuple = ()             # parsed predicates (col, kind, payload) — population, segment-resolved
    text: str = ""                # source text for embedding + human review
    derived: bool = False         # a ratio/derived metric that references other metrics, not rows
    recovered: dict | None = None # for query facts: which facets sqlglot recovered from the SQL

    @property
    def meaning(self) -> dict:
        return {"entity": self.entity, "agg": self.agg, "base": self.base, "measure": self.measure}


def _norm_table(t: str | None) -> str | None:
    """Drop the schema qualifier so analytics.fct_orders and fct_orders match."""
    return t.split(".")[-1].strip().lower() if t else None


def _entity_from_base(base: str | None) -> str | None:
    """A rough entity from a table name (strip fct_/dim_/stg_ prefixes, de-pluralise). Lets the
    warehouse and welded-query adapters populate `entity`, so CONCEPT_FORK can fire on them —
    entity is the primitive sqlglot cannot parse from a query (the AE finding)."""
    if not base:
        return None
    b = re.sub(r"^(fct|dim|stg|raw|f|d)_+", "", base)
    b = re.sub(r"s$", "", b)
    return b or base


def _additivity(agg: str | None) -> str | None:
    """Derived from the aggregate, never annotated per metric (the semantic-modelling rule)."""
    if not agg:
        return None
    a = agg.lower()
    if "distinct" in a:
        return "semi"            # distinct counts do not sum over time
    if a in ("average", "avg", "ratio") or "avg(" in a or "/" in a:
        return "non"             # ratios / averages
    if a in ("min", "max"):
        return "semi"
    return "additive"           # sum, count


def _col(node) -> str | None:
    c = node.find(exp.Column)
    return c.name.lower() if c else None


def _predicate(node) -> tuple:
    """One WHERE leaf -> a canonical (column, kind, payload). Normalises booleans/3-valued logic
    (`x` / `x = true` / `x = 1` all -> {'true'}; `not x` / `x = false` / `x is not true` / `x = 0`
    all -> {'false'}) and equality/IN into per-column value-sets, so populations compare by meaning
    rather than by raw SQL string."""
    try:
        if isinstance(node, exp.Paren):
            node = node.this
        if isinstance(node, exp.In):
            col = _col(node.this) or ""
            vals = frozenset(v.sql().strip().strip("'\"").lower() for v in node.expressions)
            return (col, "set", vals)
        if isinstance(node, exp.EQ):
            col = _col(node.this) or ""
            v = node.expression.sql().strip().strip("'\"").lower()
            v = {"1": "true", "0": "false"}.get(v, v)
            return (col, "set", frozenset({v}))
        if isinstance(node, exp.Not):
            return (_col(node) or "", "set", frozenset({"false"}))
        if isinstance(node, exp.Is):
            s = node.sql().lower()
            if "not true" in s or "false" in s or "not null" not in s and "null" in s:
                return (_col(node) or "", "set", frozenset({"false"}))
            return (_col(node) or "", "set", frozenset({"true"}))
        if isinstance(node, exp.Column):
            return (node.name.lower(), "set", frozenset({"true"}))
        if isinstance(node, (exp.GTE, exp.GT, exp.LTE, exp.LT, exp.NEQ)):
            return (_col(node) or "", "cmp", node.sql().lower())
    except Exception:
        pass
    return ("", "raw", (node.sql() if hasattr(node, "sql") else str(node)).lower())


def _predicates(filter_str: str | None) -> list[tuple]:
    """Parse a filter into canonical predicate leaves, splitting on top-level AND via the parse tree
    (not a regex, which breaks on BETWEEN and function commas)."""
    if not filter_str:
        return []
    try:
        tree = sqlglot.parse_one(str(filter_str), read="postgres")
    except Exception:
        return [("", "raw", c.strip().lower()) for c in re.split(r"\band\b", str(filter_str), flags=re.I) if c.strip()]
    leaves = []

    def walk(n):
        if isinstance(n, exp.And):
            walk(n.this)
            walk(n.expression)
        elif isinstance(n, exp.Paren):
            walk(n.this)
        else:
            leaves.append(_predicate(n))
    walk(tree)
    return leaves


def _scope(filter_str: str | None, segment: str | None = None, seg_map: dict | None = None) -> tuple:
    """Population as a set of canonical predicates. A declared `segment:` is RESOLVED to its filter
    (so a metric using segment `active` compares against the same predicates a view inlines)."""
    preds = list(_predicates(filter_str))
    if segment and segment != "all":
        if seg_map and segment in seg_map and seg_map[segment]:
            preds += _predicates(seg_map[segment])
        else:
            preds.append(("segment", "set", frozenset({segment})))
    return tuple(sorted(set(preds), key=lambda p: (p[0], p[1], str(p[2]))))


# ── semantic layer ───────────────────────────────────────────────────────────────────────────────
def adapt_semantic(path: pathlib.Path) -> list[GroundingFact]:
    doc = yaml.safe_load(path.read_text())
    seg_map = {s["name"]: s.get("filter") for s in doc.get("segments", [])}
    out = []
    for m in doc.get("metrics", []):
        name = m["name"]
        out.append(GroundingFact(
            id=f"sl:{name}", label=name, layer="semantic", kind="metric",
            entity=m.get("entity"), agg=m.get("agg"),
            base=_norm_table(m.get("base") or m.get("model")),
            measure=(m.get("measure") or m.get("expr")),
            grain=m.get("grain"), additive=_additivity(m.get("agg")),
            scope=_scope(m.get("filter"), m.get("segment"), seg_map),
            text=f"{name.replace('_', ' ')}. {m.get('description', '')}".strip(),
            derived=(m.get("agg") == "ratio"),
        ))
    for d in doc.get("dimensions", []):
        out.append(GroundingFact(
            id=f"sl:dim:{d['name']}", label=d["name"], layer="semantic", kind="dimension",
            base=_norm_table(d.get("source")), measure=d.get("column"),
            text=f"{d['name'].replace('_', ' ')}. {d.get('description', '')}".strip()))
    for s in doc.get("segments", []):
        out.append(GroundingFact(
            id=f"sl:seg:{s['name']}", label=s["name"], layer="semantic", kind="segment",
            entity=s.get("entity"), scope=_scope(s.get("filter")),
            text=f"{s['name'].replace('_', ' ')}. {s.get('description', '')}".strip()))
    return out


# ── warehouse (SQL DDL) ────────────────────────────────────────────────────────────────────────--
def adapt_warehouse(path: pathlib.Path) -> list[GroundingFact]:
    out = []
    for stmt in sqlglot.parse(path.read_text(), read="postgres"):
        if not isinstance(stmt, exp.Create):
            continue
        if stmt.kind == "TABLE":
            schema = stmt.this
            table = _norm_table(schema.this.name)
            out.append(GroundingFact(id=f"wh:{table}", label=table, layer="warehouse", kind="table",
                                     base=table, text=f"table {table}"))
            for col in schema.expressions:
                if isinstance(col, exp.ColumnDef):
                    cname = col.name.lower()
                    ctype = col.args.get("kind")
                    out.append(GroundingFact(
                        id=f"wh:{table}.{cname}", label=cname, layer="warehouse", kind="column",
                        base=table, measure=cname,
                        text=f"{table}.{cname} {ctype.sql() if ctype else ''}".strip()))
        elif stmt.kind == "VIEW":
            vname = _norm_table(stmt.this.name)
            select = stmt.expression
            base = None
            src = select.find(exp.Table) if select else None
            if src:
                base = _norm_table(src.name)
            where = select.find(exp.Where) if select else None
            scope = _scope(where.this.sql()) if where else ()
            out.append(GroundingFact(
                id=f"wh:view:{vname}", label=vname, layer="warehouse", kind="view",
                base=base, entity=_entity_from_base(base), scope=scope,
                text=f"view {vname}" + (f" over {base}" if base else "")))
    return out


# ── docs (markdown data dictionary) ──────────────────────────────────────────────────────────────
_HEAD = re.compile(r"^#{2,4}\s+(.*)$")


def _clean_heading(h: str) -> tuple[str, str | None]:
    """Return (label, base_table). Handles `table.column`, `` `x` ``, and prose headings."""
    h = h.strip().strip("`").strip()
    h = re.sub(r"\s*[—-].*$", "", h)                 # drop "— Finance default" style suffixes
    h = re.sub(r"\s*\(.*?\)\s*", " ", h).strip()      # drop parentheticals
    base = None
    if "." in h and " " not in h:                     # table.column
        base, h = _norm_table(h.split(".")[0]), h.split(".")[-1]
    return h.strip().lower(), base


def adapt_docs(path: pathlib.Path) -> list[GroundingFact]:
    out, cur, buf = [], None, []
    lines = path.read_text().splitlines()

    def flush():
        if cur is None:
            return
        label, base = _clean_heading(cur)
        if not label or len(label) > 60:
            return
        slug = re.sub(r"[^a-z0-9]+", "_", label).strip("_")
        out.append(GroundingFact(
            id=f"doc:{slug}:{len(out)}", label=label, layer="docs",
            kind="column" if base else "term", base=base, measure=label if base else None,
            text=(cur + " — " + " ".join(buf)).strip()[:400]))

    for ln in lines:
        m = _HEAD.match(ln)
        if m:
            flush()
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(ln.strip())
    flush()
    return out


# ── no-semantic-layer team: saved BI queries with scope WELDED into WHERE ─────────────────────────
def adapt_queries(path: pathlib.Path) -> list[GroundingFact]:
    """Each `-- name: X` block is one saved metric-query. Recover agg/measure/base/scope from the
    SQL (the Test-3 question: is welded scope recoverable from a real query? sqlglot says how often)."""
    text = path.read_text()
    blocks = re.split(r"(?m)^--\s*name:\s*", text)
    out = []
    for blk in blocks[1:]:
        nl = blk.find("\n")
        name = blk[:nl].strip() if nl >= 0 else blk.strip()
        sql = blk[nl + 1:] if nl >= 0 else ""
        agg = measure = base = grain = None
        scope: tuple = ()
        recovered = {"agg": False, "base": False, "scope": False, "entity": False}
        try:
            tree = sqlglot.parse_one(sql, read="postgres")
            sel = tree.find(exp.Select) if tree else None
            if sel is not None:
                af = sel.find(exp.AggFunc)
                if af is not None:
                    agg = af.key.lower()
                    measure = af.this.sql().lower() if af.this else None
                    recovered["agg"] = True
                frm = sel.find(exp.Table)
                if frm is not None:
                    base = _norm_table(frm.name)
                    recovered["base"] = True
                where = sel.find(exp.Where)
                if where is not None:
                    scope = _scope(where.this.sql())
                    recovered["scope"] = True
                grp = sel.find(exp.Group)
                if grp is not None and grp.expressions:
                    grain = ", ".join(g.sql().lower() for g in grp.expressions)
        except Exception:
            pass
        f = GroundingFact(
            id=f"q:{name}", label=name.lower(), layer="queries", kind="query",
            agg=agg, base=base, measure=measure, grain=grain,
            entity=_entity_from_base(base), additive=_additivity(agg), scope=scope,
            text=f"{name}. {sql.strip()[:200]}")
        recovered["entity"] = base is not None    # entity DERIVED from base (sqlglot can't parse it)
        f.recovered = recovered
        out.append(f)
    return out


def load_env(env_dir: pathlib.Path) -> list[GroundingFact]:
    facts = []
    facts += adapt_semantic(env_dir / "semantic/semantic_layer.yml")
    facts += adapt_warehouse(env_dir / "warehouse/schema.sql")
    facts += adapt_docs(env_dir / "docs/data_dictionary.md")
    return facts


if __name__ == "__main__":
    ENV = pathlib.Path(__file__).parent / "env_sales"
    facts = load_env(ENV)
    from collections import Counter
    by = Counter((f.layer, f.kind) for f in facts)
    print(f"total grounding facts: {len(facts)}")
    for (layer, kind), n in sorted(by.items()):
        print(f"  {layer:10} {kind:10} {n}")
    print("\nsample metric facts (semantic):")
    for f in facts:
        if f.layer == "semantic" and f.kind == "metric" and f.label in ("net_revenue", "revenue", "completed_orders"):
            print(f"  {f.id:24} base={f.base} measure={f.measure} scope={f.scope}")
    print("\nsample warehouse views (welded scope):")
    for f in facts:
        if f.kind == "view":
            print(f"  {f.id:28} base={f.base} scope={f.scope}")
