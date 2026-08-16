"""Adapters: pull each artifact type up into the common GroundingFact shape.

Each artifact has two functions: a pure `facts_from_*(content)` that does the parsing (a dict, an
SQL string, or markdown text in; facts out), and a thin `adapt_*(path)` that only reads the file and
delegates. Keeping I/O at the edge is what makes the parsers testable with an inline literal and no
temp files.
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from .model import GroundingFact, Recovered
from .scope import build_scope


# ── shared derivations ─────────────────────────────────────────────────────────────────────────--
def _norm_table(t: str | None) -> str | None:
    """Drop the schema qualifier so analytics.fct_orders and fct_orders match."""
    return t.split(".")[-1].strip().lower() if t else None


def entity_from_base(base: str | None) -> str | None:
    """A rough entity from a table name (strip fct_/dim_/stg_ prefixes, de-pluralise). Lets the
    warehouse and welded-query adapters populate `entity`, so CONCEPT_FORK can fire on them — entity
    is the primitive sqlglot cannot parse out of a query directly."""
    if not base:
        return None
    b = re.sub(r"^(fct|dim|stg|raw|f|d)_+", "", base)
    b = re.sub(r"s$", "", b)
    return b or base


def additivity(agg: str | None) -> str | None:
    """Derived from the aggregate, never annotated per metric (the semantic-modelling rule):
    distinct counts and min/max are semi-additive, ratios/averages non-additive, sum/count additive."""
    if not agg:
        return None
    a = agg.lower()
    if "distinct" in a:
        return "semi"
    if a in ("average", "avg", "ratio") or "avg(" in a or "/" in a:
        return "non"
    if a in ("min", "max"):
        return "semi"
    return "additive"


# ── semantic layer ─────────────────────────────────────────────────────────────────────────────--
def facts_from_semantic(doc: dict) -> list[GroundingFact]:
    seg_map = {s["name"]: s.get("filter") for s in doc.get("segments", [])}
    out: list[GroundingFact] = []
    for m in doc.get("metrics", []):
        name = m["name"]
        out.append(GroundingFact(
            id=f"sl:{name}", label=name, layer="semantic", kind="metric",
            entity=m.get("entity"), agg=m.get("agg"),
            base=_norm_table(m.get("base") or m.get("model")),
            measure=(m.get("measure") or m.get("expr")),
            grain=m.get("grain"), additive=additivity(m.get("agg")),
            scope=build_scope(m.get("filter"), m.get("segment"), seg_map),
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
            entity=s.get("entity"), scope=build_scope(s.get("filter")),
            text=f"{s['name'].replace('_', ' ')}. {s.get('description', '')}".strip()))
    return out


def adapt_semantic(path: str | Path) -> list[GroundingFact]:
    return facts_from_semantic(yaml.safe_load(Path(path).read_text()))


# ── warehouse (SQL DDL) ────────────────────────────────────────────────────────────────────────--
def facts_from_warehouse(sql: str) -> list[GroundingFact]:
    out: list[GroundingFact] = []
    for stmt in sqlglot.parse(sql, read="postgres"):
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
            src = select.find(exp.Table) if select else None
            base = _norm_table(src.name) if src else None
            where = select.find(exp.Where) if select else None
            scope = build_scope(where.this.sql()) if where else ()
            out.append(GroundingFact(
                id=f"wh:view:{vname}", label=vname, layer="warehouse", kind="view",
                base=base, entity=entity_from_base(base), scope=scope,
                text=f"view {vname}" + (f" over {base}" if base else "")))
    return out


def adapt_warehouse(path: str | Path) -> list[GroundingFact]:
    return facts_from_warehouse(Path(path).read_text())


# ── docs (markdown data dictionary) ──────────────────────────────────────────────────────────────
_HEAD = re.compile(r"^#{2,4}\s+(.*)$")


def _clean_heading(h: str) -> tuple[str, str | None]:
    """Return (label, base_table). Handles `table.column`, `` `x` ``, and prose headings."""
    h = h.strip().strip("`").strip()
    h = re.sub(r"\s*[—-].*$", "", h)                  # drop "— Finance default" style suffixes
    h = re.sub(r"\s*\(.*?\)\s*", " ", h).strip()       # drop parentheticals
    base = None
    if "." in h and " " not in h:                      # table.column
        base, h = _norm_table(h.split(".")[0]), h.split(".")[-1]
    return h.strip().lower(), base


def facts_from_docs(markdown: str) -> list[GroundingFact]:
    out: list[GroundingFact] = []
    cur: str | None = None
    buf: list[str] = []

    def flush() -> None:
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

    for ln in markdown.splitlines():
        m = _HEAD.match(ln)
        if m:
            flush()
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(ln.strip())
    flush()
    return out


def adapt_docs(path: str | Path) -> list[GroundingFact]:
    return facts_from_docs(Path(path).read_text())


# ── no-semantic-layer team: saved BI queries with scope WELDED into WHERE ─────────────────────────
def facts_from_queries(text: str) -> list[GroundingFact]:
    """Each `-- name: X` block is one saved metric-query. Recover agg/measure/base/scope from the SQL
    (the Test-3 question: how much of a welded query is recoverable). `recovered` records which
    facets sqlglot got."""
    out: list[GroundingFact] = []
    for blk in re.split(r"(?m)^--\s*name:\s*", text)[1:]:
        nl = blk.find("\n")
        name = blk[:nl].strip() if nl >= 0 else blk.strip()
        sql = blk[nl + 1:] if nl >= 0 else ""
        agg = measure = base = grain = None
        scope: tuple = ()
        got = {"agg": False, "base": False, "scope": False}
        try:
            tree = sqlglot.parse_one(sql, read="postgres")
            sel = tree.find(exp.Select) if tree else None
            if sel is not None:
                af = sel.find(exp.AggFunc)
                if af is not None:
                    agg = af.key.lower()
                    measure = af.this.sql().lower() if af.this else None
                    got["agg"] = True
                frm = sel.find(exp.Table)
                if frm is not None:
                    base = _norm_table(frm.name)
                    got["base"] = True
                where = sel.find(exp.Where)
                if where is not None:
                    scope = build_scope(where.this.sql())
                    got["scope"] = True
                grp = sel.find(exp.Group)
                if grp is not None and grp.expressions:
                    grain = ", ".join(g.sql().lower() for g in grp.expressions)
        except Exception:
            pass
        out.append(GroundingFact(
            id=f"q:{name}", label=name.lower(), layer="queries", kind="query",
            agg=agg, base=base, measure=measure, grain=grain,
            entity=entity_from_base(base), additive=additivity(agg), scope=scope,
            text=f"{name}. {sql.strip()[:200]}",
            recovered=Recovered(agg=got["agg"], base=got["base"], scope=got["scope"],
                                entity=base is not None)))  # entity is DERIVED from base
    return out


def adapt_queries(path: str | Path) -> list[GroundingFact]:
    return facts_from_queries(Path(path).read_text())


def load_env(env_dir: str | Path) -> list[GroundingFact]:
    """Load the conventional environment layout: semantic layer + warehouse DDL + docs."""
    env = Path(env_dir)
    return (adapt_semantic(env / "semantic/semantic_layer.yml")
            + adapt_warehouse(env / "warehouse/schema.sql")
            + adapt_docs(env / "docs/data_dictionary.md"))
