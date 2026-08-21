#!/usr/bin/env python3
"""The static scan of the one warehouse: both floors, one report.

preflight reads the project's definitions — the metrics layer YAML and the models' DDL — and
reports the pairs an agent could confuse. Nothing is queried and no model runs; this is what a
team would see in CI, before any agent touches the warehouse.

The models' DDL is generated FROM THE LIVE SCHEMA rather than mirrored by hand, because a hand
mirror is one more copy of the truth to drift: an earlier version of this experiment kept
reporting a table that had already been renamed.

    python scan.py                     # lexical gate (what a plain install runs)
    python scan.py --gate embeddings   # the pre-registered measurement gate
"""
from __future__ import annotations

import argparse
import pathlib
import tempfile
from collections import Counter

import warehouses
import yaml
from preflight import adapt_warehouse, detect_collisions
from preflight.metricflow import facts_from_metricflow
from warehouse.warehouse import open_warehouse, set_star

HERE = pathlib.Path(__file__).resolve().parent
ARMS = [("before", warehouses.BEFORE), ("after", warehouses.AFTER)]

_TYPES = {"BIGINT": "BIGINT", "INTEGER": "INT", "DOUBLE": "DOUBLE", "VARCHAR": "VARCHAR",
          "BOOLEAN": "BOOLEAN", "DATE": "DATE", "TIMESTAMP": "TIMESTAMP"}


def ddl_of(con, schema: str) -> str:
    """The arm's models as CREATE TABLE statements, with column comments carried through as
    trailing SQL comments — the docs are half of what the linter compares."""
    stmts = []
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ? ORDER BY 1",
        [schema]).fetchall()]
    for table in tables:
        cols = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema, table]).fetchall()
        lines = []
        for name, dtype in cols:
            comment = con.execute(
                "SELECT comment FROM duckdb_columns() WHERE schema_name = ? AND table_name = ? "
                "AND column_name = ?", [schema, table, name]).fetchone()
            note = f"  -- {comment[0]}" if comment and comment[0] else ""
            lines.append(f"    {name} {_TYPES.get(str(dtype).upper(), 'VARCHAR')},{note}")
        body = "\n".join(lines).rstrip(",")
        if body.endswith(","):
            body = body[:-1]
        stmts.append(f"CREATE TABLE {table} (\n{body}\n);")
    return "\n\n".join(stmts).replace(",\n)", "\n)")


def metric_facts(arm: str):
    sems, mets = [], []
    for f in sorted((HERE / "layers" / arm).rglob("*.yaml")):
        for doc in yaml.safe_load_all(f.read_text()):
            if isinstance(doc, dict):
                if "semantic_model" in doc:
                    sems.append(doc["semantic_model"])
                if "metric" in doc:
                    mets.append(doc["metric"])
    return facts_from_metricflow(sems, mets)


def _ensure_snapshot_views(con) -> None:
    """The monthly habit snapshot both arms read. Defined here rather than imported from the
    runner: a static scan should not need the agent stack to be installed to run."""
    from warehouse.warehouse import STAR_SCHEMA as S
    con.execute(f'''CREATE OR REPLACE VIEW "{S}".fct_habit_months AS
        SELECT m.snapshot_month, h.habit_id, h.category
        FROM (SELECT DISTINCT date_trunc('month', active_date)::DATE AS snapshot_month
              FROM "{S}".agg_active_days) m
        JOIN "{S}".dim_habits h ON h.created_date < m.snapshot_month + INTERVAL 1 MONTH
            AND (h.archived_date IS NULL OR h.archived_date >= m.snapshot_month + INTERVAL 1 MONTH)''')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="lexical", choices=("lexical", "embeddings"))
    gate = ap.parse_args().gate

    con = open_warehouse(create_star_views=True)
    _ensure_snapshot_views(con)
    warehouses.build(con)

    lines = ["```", "", f"  ONE WAREHOUSE — STATIC SCAN        gate: {gate}", "  " + "-" * 62]
    detail: list[str] = []
    for arm, schema in ARMS:
        with tempfile.TemporaryDirectory() as tmp:
            sql = pathlib.Path(tmp) / "models.sql"
            sql.write_text(ddl_of(con, schema))
            facts = metric_facts(arm) + adapt_warehouse(sql)
        findings = detect_collisions(facts, gate=gate)
        c = Counter(f.danger for f in findings)
        lines.append(f"  {arm:<8} {len(findings):>2} findings   ({len(facts)} definitions · "
                     f"{c.get('high', 0)} high {c.get('medium', 0)} med {c.get('low', 0)} low)")
        detail.append(f"\n==== {arm} " + "=" * 50)
        if not findings:
            detail.append("  (no findings)")
        for f in findings:
            labels = "  ~  ".join(sorted({it.label for it in f.items}))
            detail.append(f"  {str(f.danger)[0].upper()} {f.type:<18} {labels}")
    lines += detail + ["", "```"]
    (HERE / "scan.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
