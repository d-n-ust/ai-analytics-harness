"""Adapters: pull each artifact type up into the common GroundingFact shape.

Each artifact has two functions: a pure `facts_from_*(content)` that does the parsing (a dict, an
SQL string, or markdown text in; facts out), and a thin `adapt_*(path)` that only reads the file and
delegates. Keeping I/O at the edge is what makes the parsers testable with an inline literal and no
temp files.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .model import GroundingFact, Recovered, Source
from .scope import build_scope


# ── source provenance ────────────────────────────────────────────────────────────────────────────
def _line_of(text: str, pattern: str) -> int | None:
    """1-based line of the first `pattern` match in `text`, or None. The building block for citing a
    fact whose parser abstracts position away (YAML, or a table/view name in SQL)."""
    m = re.search(pattern, text)
    return text.count("\n", 0, m.start()) + 1 if m else None


def line_of_definition(text: str, label: str) -> int | None:
    """The line where `label` is defined in a YAML semantic file. Matches the list form
    (`name: label`) and the dict-keyed form (`label:`); definitions are unique by label, so the
    first match is the definition. Exposed so callers with their own YAML shape can cite the source
    the same way the built-in adapter does."""
    esc = re.escape(label)
    # 1) `name: label` in block OR flow style ({name: label, ...}); 2) `label:` as a dict key.
    for pat in (rf'(?im)\bname:\s*["\']?{esc}["\']?(?=[\s,}}]|$)',
                rf'(?im)^\s*["\']?{esc}["\']?\s*:'):
        if (ln := _line_of(text, pat)) is not None:
            return ln
    return None


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


def gate_text(name: str, description: str = "") -> str:
    """The text the confusability gate reads for a fact: the name in words, then its description. One
    definition so the gate sees the same shape for a metric, a measure, a dimension, or a segment."""
    return f"{name.replace('_', ' ')}. {description}".strip()


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
            text=gate_text(name, m.get("description", "")),
            derived=(m.get("agg") == "ratio"),
        ))
    for d in doc.get("dimensions", []):
        out.append(GroundingFact(
            id=f"sl:dim:{d['name']}", label=d["name"], layer="semantic", kind="dimension",
            base=_norm_table(d.get("source")), measure=d.get("column"),
            text=gate_text(d["name"], d.get("description", ""))))
    for s in doc.get("segments", []):
        out.append(GroundingFact(
            id=f"sl:seg:{s['name']}", label=s["name"], layer="semantic", kind="segment",
            entity=s.get("entity"), scope=build_scope(s.get("filter")),
            text=gate_text(s["name"], s.get("description", ""))))
    return out


def with_yaml_sources(facts: list[GroundingFact], text: str, path: str) -> list[GroundingFact]:
    """Attach a Source to each fact by locating its `name:`/`label:` line in the raw YAML. Kept
    separate from the parser so the pure `facts_from_semantic(dict)` stays position-free, and so a
    caller with a differently-shaped YAML can reuse it."""
    return [replace(f, source=Source(path, ln)) if (ln := line_of_definition(text, f.label)) else f
            for f in facts]


def adapt_semantic(path: str | Path) -> list[GroundingFact]:
    text = Path(path).read_text()
    return with_yaml_sources(facts_from_semantic(yaml.safe_load(text)), text, str(path))


# ── warehouse (SQL DDL) ────────────────────────────────────────────────────────────────────────--
def _create_line(sql: str, kind: str, name: str) -> int | None:
    """Line of `CREATE TABLE|VIEW ... <name>`, tolerating a schema qualifier before the name."""
    return _line_of(sql, rf'(?i)create\s+{kind}\b[^\n(]*\b{re.escape(name)}\b')


def facts_from_warehouse(sql: str, path: str = "") -> list[GroundingFact]:
    out: list[GroundingFact] = []
    for stmt in sqlglot.parse(sql, read="postgres"):
        if not isinstance(stmt, exp.Create):
            continue
        if stmt.kind == "TABLE":
            schema = stmt.this
            table = _norm_table(schema.this.name)
            if table is None:                          # a CREATE TABLE with no parseable name
                continue
            tsrc = Source(path, ln) if (ln := _create_line(sql, "table", table)) else None
            out.append(GroundingFact(id=f"wh:{table}", label=table, layer="warehouse", kind="table",
                                     base=table, text=f"table {table}", source=tsrc))
            for col in schema.expressions:
                if isinstance(col, exp.ColumnDef):
                    cname = col.name.lower()
                    ctype = col.args.get("kind")
                    cln = col.this.meta.get("line")  # exact per-column line, so overloaded names cite right
                    out.append(GroundingFact(
                        id=f"wh:{table}.{cname}", label=cname, layer="warehouse", kind="column",
                        base=table, measure=cname,
                        text=f"{table}.{cname} {ctype.sql() if ctype else ''}".strip(),
                        source=Source(path, cln) if cln else None))
        elif stmt.kind == "VIEW":
            vname = _norm_table(stmt.this.name)
            if vname is None:                          # a CREATE VIEW with no parseable name
                continue
            select = stmt.expression
            src = select.find(exp.Table) if select else None
            base = _norm_table(src.name) if src else None
            where = select.find(exp.Where) if select else None
            scope = build_scope(where.this.sql()) if where else ()
            vsrc = Source(path, ln) if (ln := _create_line(sql, "view", vname)) else None
            out.append(GroundingFact(
                id=f"wh:view:{vname}", label=vname, layer="warehouse", kind="view",
                base=base, entity=entity_from_base(base), scope=scope,
                text=f"view {vname}" + (f" over {base}" if base else ""), source=vsrc))
    return out


def adapt_warehouse(path: str | Path) -> list[GroundingFact]:
    return facts_from_warehouse(Path(path).read_text(), str(path))


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


def facts_from_docs(markdown: str, path: str = "") -> list[GroundingFact]:
    out: list[GroundingFact] = []
    cur: str | None = None
    cur_line = 0
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
            text=(cur + " — " + " ".join(buf)).strip()[:400],
            source=Source(path, cur_line) if cur_line else None))

    for i, ln in enumerate(markdown.splitlines(), start=1):
        m = _HEAD.match(ln)
        if m:
            flush()
            cur, cur_line, buf = m.group(1), i, []
        elif cur is not None:
            buf.append(ln.strip())
    flush()
    return out


def adapt_docs(path: str | Path) -> list[GroundingFact]:
    return facts_from_docs(Path(path).read_text(), str(path))


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
        except (SqlglotError, AttributeError, TypeError, ValueError):
            pass                                  # unrecoverable query -> emit the fact with what we got
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
    """Load the conventional environment layout: semantic layer + warehouse DDL + docs. Each artifact
    is optional — a layer that is absent is simply skipped, so the tool runs on a semantic-only repo
    (cross-layer collisions just need more than one layer present to appear)."""
    env = Path(env_dir)
    artifacts = ((adapt_semantic, "semantic/semantic_layer.yml"),
                 (adapt_warehouse, "warehouse/schema.sql"),
                 (adapt_docs, "docs/data_dictionary.md"))
    facts: list[GroundingFact] = []
    for adapt, rel in artifacts:
        path = env / rel
        if path.exists():
            facts += adapt(path)
    return facts
