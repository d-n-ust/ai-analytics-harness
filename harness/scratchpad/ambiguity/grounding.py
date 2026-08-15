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
    scope: tuple = ()             # which-rows clauses (filters, segment) — the scope facet
    text: str = ""                # source text for embedding + human review
    derived: bool = False         # a ratio/derived metric that references other metrics, not rows
    recovered: dict | None = None # for query facts: which facets sqlglot recovered from the SQL

    @property
    def meaning(self) -> dict:
        return {"entity": self.entity, "agg": self.agg, "base": self.base, "measure": self.measure}


def _norm_table(t: str | None) -> str | None:
    """Drop the schema qualifier so analytics.fct_orders and fct_orders match."""
    return t.split(".")[-1].strip().lower() if t else None


def _scope_clauses(filter_str: str | None, segment: str | None = None) -> tuple:
    clauses = set()
    if filter_str:
        for c in re.split(r"\band\b", str(filter_str), flags=re.I):
            c = c.strip().strip("()").strip().lower()
            if c:
                clauses.add(c)
    if segment and segment != "all":
        clauses.add(f"segment={segment}")
    return tuple(sorted(clauses))


# ── semantic layer ───────────────────────────────────────────────────────────────────────────────
def adapt_semantic(path: pathlib.Path) -> list[GroundingFact]:
    doc = yaml.safe_load(path.read_text())
    out = []
    for m in doc.get("metrics", []):
        name = m["name"]
        out.append(GroundingFact(
            id=f"sl:{name}", label=name, layer="semantic", kind="metric",
            entity=m.get("entity"), agg=m.get("agg"),
            base=_norm_table(m.get("base") or m.get("model")),
            measure=(m.get("measure") or m.get("expr")),
            scope=_scope_clauses(m.get("filter"), m.get("segment")),
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
            entity=s.get("entity"), scope=_scope_clauses(s.get("filter")),
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
            clauses = ()
            if where:
                conds = [where.this.sql().lower()]
                # split top-level AND
                conds = [c.strip() for c in re.split(r"\band\b", where.this.sql(), flags=re.I)]
                clauses = tuple(sorted(c.strip().lower() for c in conds if c.strip()))
            out.append(GroundingFact(
                id=f"wh:view:{vname}", label=vname, layer="warehouse", kind="view",
                base=base, scope=clauses,
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
        agg = measure = base = None
        scope: tuple = ()
        recovered = {"agg": False, "base": False, "scope": False}
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
                    scope = tuple(sorted(c.strip().lower()
                                         for c in re.split(r"\band\b", where.this.sql(), flags=re.I)
                                         if c.strip()))
                    recovered["scope"] = True
        except Exception:
            pass
        f = GroundingFact(
            id=f"q:{name}", label=name.lower(), layer="queries", kind="query",
            agg=agg, base=base, measure=measure, scope=scope,
            text=f"{name}. {sql.strip()[:200]}")
        f.recovered = recovered            # attach recovery flags for the Test-3 tally
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
