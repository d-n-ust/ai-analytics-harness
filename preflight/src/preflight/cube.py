"""Adapter for Cube semantic models — YAML (`cubes:`) and JavaScript (`cube(...)`).

A Cube measure carries `type` (sum/count/...), `sql` (the measured expression, often `${dimension}`),
and optional `filters` — which maps directly onto a GroundingFact's agg/measure/scope. YAML is parsed
with pyyaml; JavaScript is parsed with a small brace-matching scanner that respects template strings
(``${...}`` interpolations), since Cube JS is a JS object literal, not JSON. Both paths converge on
the same fact shape.
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .adapters import additivity, entity_from_base
from .model import GroundingFact
from .scope import build_scope

_CUBE_AGG = {"sum": "sum", "count": "count", "countdistinct": "count_distinct",
             "count_distinct": "count_distinct", "avg": "avg", "min": "min", "max": "max"}
_DERIVED_TYPES = ("number", "runningtotal", "running_total")


# ── shared normalisation ─────────────────────────────────────────────────────────────────────────
def _deref(sql: str) -> str:
    """`${CUBE}.status` / `{CUBE}.status` -> `status`; `${amount}` -> `amount`."""
    s = re.sub(r"\$?\{\s*CUBE\s*\}\.", "", sql)
    return re.sub(r"\$?\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}", r"\1", s).strip()


def _measure_column(sql: str | None) -> tuple[str | None, bool]:
    """(measured column, is_derived). An expression with arithmetic or referencing other measures is
    a derived measure, not a bare column."""
    if not sql:
        return (None, False)
    cleaned = _deref(sql)
    if re.search(r"[-+*/]|coalesce|\bcase\b|\bwhen\b", cleaned, re.I):
        return (cleaned[:60].lower(), True)
    return (cleaned.lower() or None, False)


def _scope(filters) -> tuple:
    clauses = []
    for f in filters or []:
        raw = f.get("sql") if isinstance(f, dict) else f
        if raw:
            clauses.append(f"({_deref(str(raw))})")
    return build_scope(" and ".join(clauses)) if clauses else ()


def _base(cube_sql: str | None, sql_table: str | None) -> str | None:
    if sql_table:
        return sql_table.split(".")[-1].strip().lower()
    if cube_sql:
        s = re.sub(r"\$?\{[^}]*\}\.", "", cube_sql)
        s = re.sub(r"\$?\{[^}]*\}", "x", s)
        try:
            tree = sqlglot.parse_one(s, read="postgres")
            tbl = tree.find(exp.Table) if tree else None
            if tbl:
                return tbl.name.lower()
        except SqlglotError:                      # unparseable sql: expr -> regex the FROM out
            m = re.search(r"from\s+([A-Za-z_][\w.]*)", s, re.I)
            if m:
                return m.group(1).split(".")[-1].lower()
    return None


def _fact(cube: str, base, entity, name, mtype, msql, filters) -> GroundingFact:
    t = (mtype or "").lower()
    agg = _CUBE_AGG.get(t)
    measure, derived = _measure_column(msql)
    derived = derived or t in _DERIVED_TYPES
    return GroundingFact(
        id=f"cube:{cube}.{name}", label=name, layer="semantic", kind="metric",
        agg=agg, measure=measure, base=base, entity=entity, additive=additivity(agg),
        scope=_scope(filters), derived=derived, text=f"{name} in cube {cube}")


# ── YAML ───────────────────────────────────────────────────────────────────────────────────────--
def facts_from_cube_yaml(doc: dict) -> list[GroundingFact]:
    out: list[GroundingFact] = []
    for cube in doc.get("cubes", []) or []:
        name = cube.get("name")
        base = _base(cube.get("sql"), cube.get("sql_table") or cube.get("sqlTable"))
        entity = entity_from_base(base) or name
        for m in cube.get("measures", []) or []:
            out.append(_fact(name, base, entity, m.get("name"), m.get("type"),
                             m.get("sql"), m.get("filters")))
    return out


# ── JavaScript ─────────────────────────────────────────────────────────────────────────────────--
def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", text)


def _match_block(text: str, open_idx: int) -> tuple[str, int]:
    """(content, end_index) of the `{...}` starting at open_idx, brace-matched but skipping backtick
    strings (whose `${...}` interpolations contain braces that must not be counted)."""
    depth, i, in_tick = 0, open_idx, False
    while i < len(text):
        c = text[i]
        if in_tick:
            if c == "`":
                in_tick = False
        elif c == "`":
            in_tick = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i], i
        i += 1
    return text[open_idx + 1:], len(text)


def _block_after(text: str, key: str) -> str:
    m = re.search(rf"\b{key}\s*:\s*\{{", text)
    return _match_block(text, m.end() - 1)[0] if m else ""


def _entries(block: str) -> list[tuple[str, str]]:
    """Top-level `name: { ... }` entries as (name, body) — nested blocks (rollingWindow, format, ...)
    are skipped because each matched block advances the cursor past it."""
    out: list[tuple[str, str]] = []
    i = 0
    pat = re.compile(r"([A-Za-z_$][\w]*)\s*:\s*\{")
    while True:
        m = pat.search(block, i)
        if not m:
            return out
        body, end = _match_block(block, m.end() - 1)
        out.append((m.group(1), body))
        i = end + 1


def _js_value(text: str, key: str) -> str | None:
    """Value of `key:` — a backtick string first (Cube's default; may contain quotes), else a quoted
    string."""
    for pat in (rf"\b{key}\s*:\s*`([^`]*)`", rf"\b{key}\s*:\s*'([^']*)'", rf'\b{key}\s*:\s*"([^"]*)"'):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _js_filters(body: str) -> list[str]:
    m = re.search(r"\bfilters\s*:\s*\[", body)
    if not m:
        return []
    seg = body[m.end():]
    return re.findall(r"sql\s*:\s*`([^`]*)`", seg) or re.findall(r"sql\s*:\s*'([^']*)'", seg)


def facts_from_cube_js(text: str) -> list[GroundingFact]:
    text = _strip_comments(text)
    m = re.search(r"cube\(\s*[`'\"]([^`'\"]+)[`'\"]", text)
    if not m:
        return []
    name = m.group(1)
    mm = re.search(r"\bmeasures\s*:", text)
    header = text[m.end():mm.start()] if mm else text
    base = _base(_js_value(header, "sql"), _js_value(header, "sql_table") or _js_value(header, "sqlTable"))
    entity = entity_from_base(base) or name
    out: list[GroundingFact] = []
    for mname, body in _entries(_block_after(text, "measures")):
        fpos = re.search(r"\bfilters\s*:", body)
        head = body[:fpos.start()] if fpos else body        # measure-level sql/type live before filters
        out.append(_fact(name, base, entity, mname,
                         _js_value(head, "type"), _js_value(head, "sql"), _js_filters(body)))
    return out


def load_cube(path: str | Path) -> list[GroundingFact]:
    """Load a Cube surface from a file or directory (*.yml/*.yaml parsed as YAML, *.js as JavaScript)."""
    p = Path(path)
    files = [p] if p.is_file() else (sorted(p.rglob("*.yml")) + sorted(p.rglob("*.yaml"))
                                     + sorted(p.rglob("*.js")))
    facts: list[GroundingFact] = []
    for f in files:
        try:
            text = f.read_text()
        except OSError:
            continue
        if f.suffix in (".yml", ".yaml"):
            try:
                doc = yaml.safe_load(text)
            except yaml.YAMLError:
                continue
            if isinstance(doc, dict):
                facts += facts_from_cube_yaml(doc)
        else:
            facts += facts_from_cube_js(text)
    return facts
