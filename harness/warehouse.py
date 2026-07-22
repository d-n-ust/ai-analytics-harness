"""The warehouse: a DuckDB connection with the star views created, plus per-rung
schema visibility and a guarded read-only query runner.

Information hiding: which tables exist for the agent depends on the rung. Rung 1
sees only the messy raw tables; rung 2+ sees only the clean star. The agg_* marts
are internal to the semantic layer and never shown as tables.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "warehouse.duckdb"
STAR_SQL = _ROOT / "grounding" / "rung2_star" / "star.sql"

RAW_TABLES = ("u", "hab", "evt", "subs", "spend", "ref")
STAR_TABLES = (
    "dim_users", "dim_habits", "fct_value_moments", "fct_reminders",
    "fct_subscriptions", "fct_marketing_spend", "fct_referrals",
)


def _statements(sql: str):
    """Yield individual statements from a ;-separated script. Strips `--` line
    comments first, so semicolons inside comments don't split a statement."""
    no_comments = "\n".join(re.sub(r"--.*$", "", ln) for ln in sql.splitlines())
    for chunk in no_comments.split(";"):
        body = chunk.strip()
        if body:
            yield body


# Reverse dependency order, so dropping never trips over a view that depends on another.
_STAR_DROP_ORDER = (
    "agg_user_activation", "agg_active_days", "fct_referrals", "fct_marketing_spend",
    "fct_subscriptions", "fct_reminders", "fct_value_moments", "dim_habits", "dim_users",
)


def create_star(con) -> None:
    for stmt in _statements(STAR_SQL.read_text()):
        con.execute(stmt)


def drop_star(con) -> None:
    for name in _STAR_DROP_ORDER:
        con.execute(f"DROP VIEW IF EXISTS {name}")


def set_star(con, enabled: bool) -> None:
    """Toggle the star views. Rung 1 runs with them dropped, so the messy-data baseline
    is genuinely raw-only — a model can't quietly query the clean tables and cheat."""
    create_star(con) if enabled else drop_star(con)


def open_warehouse(create_star_views: bool = True) -> duckdb.DuckDBPyConnection:
    """Open the warehouse and (by default) create the star views on top of the raw tables."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found — run `python run.py data` first."
        )
    con = duckdb.connect(str(DB_PATH))
    if create_star_views:
        create_star(con)
    return con


def visible_tables(rung: int) -> tuple[str, ...]:
    return RAW_TABLES if rung <= 1 else STAR_TABLES


# --------------------------------------------------------------------------- #
# Introspection helpers used by the agent's tools
# --------------------------------------------------------------------------- #
def schema_text(con, rung: int) -> str:
    """A compact 'table(col type, ...)' listing of everything visible at this rung."""
    lines = []
    for t in visible_tables(rung):
        cols = con.execute(f"DESCRIBE {t}").fetchall()  # (name, type, ...)
        coltxt = ", ".join(f"{c[0]} {c[1].lower()}" for c in cols)
        lines.append(f"{t}({coltxt})")
    return "\n".join(lines)


def describe_table(con, name: str, rung: int) -> str:
    """Columns + up to 3 sample rows for one visible table."""
    allowed = visible_tables(rung)
    if name not in allowed:
        return f"Error: unknown table {name!r}. Available: {', '.join(allowed)}"
    cols = con.execute(f"DESCRIBE {name}").fetchall()
    header = ", ".join(f"{c[0]} ({c[1].lower()})" for c in cols)
    sample = con.execute(f"SELECT * FROM {name} USING SAMPLE 3 ROWS").fetchall()
    rows = "\n".join(str(r) for r in sample)
    return f"{name}\ncolumns: {header}\nsample rows:\n{rows}"


class QueryError(Exception):
    pass


def run_query(con, sql: str, max_rows: int = 100) -> tuple[list[str], list[tuple]]:
    """Run a read-only query. Returns (column_names, rows). Raises QueryError with
    the database's own message on failure — that message is what the agent's
    self-correction loop feeds back to the model.

    Read-only is enforced by the DuckDB PARSER, not a string prefix: the statement's
    classified type must be SELECT. This blocks INSERT/UPDATE/DELETE/CREATE/COPY/ATTACH
    (each a distinct StatementType) even when they hide behind a leading comment or CTE,
    which a `startswith('select')` check would miss — and it needs exactly one statement,
    so a chained write is impossible."""
    stripped = sql.strip()
    try:
        statements = con.extract_statements(stripped)
    except Exception as exc:  # a parse error — surface it to the model verbatim
        raise QueryError(str(exc)) from exc
    if len(statements) != 1:
        raise QueryError("Run a single statement.")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise QueryError("Only read-only SELECT/WITH queries are allowed.")
    try:
        cur = con.execute(stripped)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
    except Exception as exc:  # noqa: BLE001 — surface the DB message verbatim
        raise QueryError(str(exc)) from exc
    return columns, rows
