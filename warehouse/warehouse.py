"""The warehouse: a DuckDB connection with the star views created, plus per-rung
schema visibility and a guarded read-only query runner.

Information hiding: which tables exist for the agent depends on the rung. Rung 1
sees only the messy raw tables; rung 2+ sees only the clean star. The agg_* marts
are internal to the semantic layer and never shown as tables.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

# Import rather than recompute: see warehouse/config.py:default_db.
from warehouse.config import default_db

_HERE = Path(__file__).resolve().parent
STAR_SQL = _HERE / "star.sql"             # the clean dim_/fct_ views over the raw tables

RAW_TABLES = ("u", "hab", "evt", "subs", "spend", "ref")
STAR_TABLES = (
    "dim_users", "dim_habits", "fct_value_moments", "fct_reminders",
    "fct_subscriptions", "fct_marketing_spend", "fct_referrals",
)


def _statements(sql: str):
    """Yield individual statements from a ;-separated script.

    Aware of `--` line comments AND of single-quoted strings: a `COMMENT ON ... IS 'Archived date;
    NULL while active'` contains a semicolon that is part of the value, and splitting there
    produced an unterminated string. `''` inside a string is an escaped quote, not a terminator.
    """
    out, buf, in_string = [], [], False
    for line in sql.splitlines():
        i, cleaned = 0, []
        while i < len(line):
            ch = line[i]
            if in_string:
                cleaned.append(ch)
                if ch == "'":
                    if i + 1 < len(line) and line[i + 1] == "'":   # '' is an escaped quote
                        cleaned.append("'")
                        i += 1
                    else:
                        in_string = False
            elif ch == "'":
                in_string = True
                cleaned.append(ch)
            elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                break                                              # rest of the line is a comment
            elif ch == ";":
                buf.append("".join(cleaned))
                if body := "".join(buf).strip():
                    out.append(body)
                buf, cleaned = [], []
            else:
                cleaned.append(ch)
            i += 1
        buf.append("".join(cleaned) + "\n")
    if body := "".join(buf).strip():
        out.append(body)
    return out


# Reverse dependency order, so dropping never trips over a view that depends on another.
_STAR_DROP_ORDER = (
    "agg_user_activation", "agg_active_days", "fct_referrals", "fct_marketing_spend",
    "fct_subscriptions", "fct_reminders", "fct_value_moments", "dim_habits", "dim_users",
)


# Where the star lives now that it is out of `main`. `main` is always implicitly in DuckDB's
# search_path, so anything left there is visible to EVERY cursor — including an arm that is supposed
# to see only messy tables. Emptying `main` is what makes an arm's isolation structural rather than
# a matter of not mentioning the clean tables.
STAR_SCHEMA = "_star"


def create_star(con, schema: str = STAR_SCHEMA) -> None:
    """Build the star into `schema`. Source tables are qualified in star.sql; references BETWEEN
    the star's own views are not, so they resolve inside whichever schema receives them — which is
    how one file can serve both the shared `_star` and an arm's private copy."""
    from warehouse.environment import ensure_source
    ensure_source(con)
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    cur = con.cursor()
    cur.execute(f"SET search_path='{schema}'")
    for stmt in _statements(STAR_SQL.read_text()):
        cur.execute(stmt)


def drop_star(con, schema: str = STAR_SCHEMA) -> None:
    con.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def _empty_main(con) -> None:
    """Remove the originals from `main`, once `_source` and `_star` hold them.

    Not tidiness: `main` cannot be excluded from a search_path, so a table left there is reachable
    by every arm no matter what that arm declares."""
    from warehouse.environment import RAW
    for name in _STAR_DROP_ORDER:
        con.execute(f'DROP VIEW IF EXISTS main."{name}"')
    for name in RAW:
        con.execute(f'DROP TABLE IF EXISTS main."{name}"')


def set_star(con, enabled: bool) -> None:
    """Toggle the star views. Rung 1 runs with them dropped, so the messy-data baseline
    is genuinely raw-only — a model can't quietly query the clean tables and cheat."""
    create_star(con) if enabled else drop_star(con)
    # Re-point the connection: it may be scoped at a schema this call just dropped or created.
    _scope(con)


def open_warehouse(create_star_views: bool = True) -> duckdb.DuckDBPyConnection:
    """Open the warehouse and (by default) create the star views on top of the raw tables."""
    db = default_db()
    if not db.exists():
        raise FileNotFoundError(
            f"{db} not found — run `bench data` (or `make data`) first."
        )
    con = duckdb.connect(str(db))
    from warehouse.environment import ensure_source
    ensure_source(con)
    if create_star_views:
        create_star(con)
    _empty_main(con)
    # The DEFAULT connection sees everything, so every existing caller — the semantic layer, gold
    # SQL, `bench query`, the tests — keeps working with unqualified names. Only an ARM's cursor is
    # narrowed, and that narrowing is the experiment.
    _scope(con)
    return con


def _scope(target) -> None:
    """Point `target` at the shared warehouse's schemas — whichever of them exist.

    Built by inspection rather than hardcoded to `_star,_source`, because rung 1 runs with the
    star DROPPED (`set_star(con, False)` removes the whole schema, CASCADE) and DuckDB treats a
    missing schema in a search_path as a catalog error, not a no-op. A fixed pair therefore
    raised on exactly the raw-data baseline the grounding ladder is measured against.
    """
    from warehouse.environment import SOURCE
    present = {r[0] for r in target.execute(
        "SELECT schema_name FROM information_schema.schemata").fetchall()}
    path = [s for s in (STAR_SCHEMA, SOURCE) if s in present]
    if path:
        target.execute(f"SET search_path='{','.join(path)}'")


def cursor(con):
    """A cursor on the shared warehouse, scoped like the connection `open_warehouse` returns.

    A bare `con.cursor()` starts on the DEFAULT search_path, which is `main` — and `main` is empty
    now that the tables live in `_source` and `_star`. So a thread that made its own cursor could
    see nothing at all. Arms with their own environment get `Environment.cursor`; everything else
    gets this, and neither should ever call `con.cursor()` directly."""
    cur = con.cursor()
    _scope(cur)
    return cur


def visible_tables(rung: float) -> tuple[str, ...]:
    """Which tables exist at this rung — ASKED of the rung, never inferred from its number.

    This read `rung <= 1` until rung 1.5 was added, at which point a documented-but-messy rung
    silently showed the clean star tables: the number was larger, so the comparison said star. The
    ladder is not monotonic and a rung number is not a statement about capability."""
    from agent.rungs import capabilities
    return STAR_TABLES if capabilities(rung).star else RAW_TABLES


# --------------------------------------------------------------------------- #
# Introspection helpers used by the agent's tools
# --------------------------------------------------------------------------- #
def _tables_in_scope(con, rung, schema: str | None):
    """The tables the agent may see: the arm's own schema when it has one, otherwise the rung's set.

    Asked of the DATABASE when a schema exists, so an arm that declares a view gets it listed
    without anything restating the table list. The hardcoded tuples remain only for studies that
    share the warehouse."""
    if schema is None:
        return visible_tables(rung)
    # `agg_*` are the semantic layer's own inputs. star.sql has always said they "are internal to
    # the semantic layer and are not shown to the agent as tables", and before per-arm schemas that
    # held because STAR_TABLES listed the rest. An arm's schema must CONTAIN them — the layer
    # compiles against them on this very cursor — so the hiding belongs here, at the listing.
    return tuple(r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ? "
        "AND table_name NOT LIKE 'agg\\_%' ESCAPE '\\' ORDER BY 1", [schema]).fetchall())


def _comments(con, schema: str | None) -> tuple[dict, dict]:
    """Table and column comments, read from the database's own catalog.

    This is where a real tool would read them: `COMMENT ON` is the mechanism Snowflake, BigQuery,
    Postgres and Databricks all expose, and dbt's `description:` compiles to it. Reading the catalog
    rather than a file the harness carries is what lets a documentation result be about warehouses
    rather than about this repository."""
    if schema is None:
        return {}, {}
    tables = {r[0]: r[1] for r in con.execute(
        "SELECT view_name, comment FROM duckdb_views() WHERE schema_name = ? AND comment IS NOT NULL",
        [schema]).fetchall()}
    cols: dict = {}
    for table, column, comment in con.execute(
        "SELECT table_name, column_name, comment FROM duckdb_columns() "
        "WHERE schema_name = ? AND comment IS NOT NULL", [schema]).fetchall():
        cols.setdefault(table, {})[column] = comment
    return tables, cols


def schema_text(con, rung: int, schema: str | None = None) -> str:
    """A compact 'table(col type, ...)' listing of everything visible at this rung.

    At a DOCUMENTED rung each table also carries its one-line description — the whole of the
    matrix's `documented` column, and the only thing that separates rung 1 from 1.5. Nothing is
    renamed and no view is created; the tables are the same objects either way.
    """
    table_docs, column_docs = _comments(con, schema)
    lines = []
    for t in _tables_in_scope(con, rung, schema):
        cols = con.execute(f"DESCRIBE {t}").fetchall()  # (name, type, ...)
        coltxt = ", ".join(f"{c[0]} {c[1].lower()}" for c in cols)
        lines.append(f"{t}({coltxt})")
        if doc := table_docs.get(t):
            lines.append(f"    {doc}")
        for column, doc in (column_docs.get(t) or {}).items():
            lines.append(f"    {column}: {doc}")
    return "\n".join(lines)


def describe_table(con, name: str, rung: int, schema: str | None = None) -> str:
    """Columns + up to 3 sample rows for one visible table."""
    allowed = _tables_in_scope(con, rung, schema)
    if name not in allowed:
        return f"Error: unknown table {name!r}. Available: {', '.join(allowed)}"
    cols = con.execute(f"DESCRIBE {name}").fetchall()
    header = ", ".join(f"{c[0]} ({c[1].lower()})" for c in cols)
    sample = con.execute(f"SELECT * FROM {name} USING SAMPLE 3 ROWS").fetchall()
    rows = "\n".join(str(r) for r in sample)
    return f"{name}\ncolumns: {header}\nsample rows:\n{rows}"


class QueryError(Exception):
    pass


DEFAULT_MAX_ROWS = 100   # the row cap; agent.tools reports it rather than restating it


def foreign_schemas(con, sql: str, allowed: str) -> set[str]:
    """Schemas this statement names that are not `allowed`.

    Read from DuckDB's own parse tree, never from the query text: a regex over `schema.table` is
    defeated by quoting, casing and whitespace, and the thing it would be protecting is the claim
    that one arm cannot read another's warehouse.

    An UNQUALIFIED reference is fine and comes back with an empty schema — it resolves through
    `search_path`, which is the arm's schema alone, so it can only find the arm's own objects.
    Common table expressions also arrive unqualified, which is why the empty case must be allowed
    rather than treated as suspicious.

    FAILS CLOSED. If the tree cannot be read, every schema is reported foreign. A guard that
    permits what it could not parse is not a guard.
    """
    try:
        tree = json.loads(con.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
    except Exception:  # noqa: BLE001 — unreadable means refused, never allowed
        return {"<unparseable>"}
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            if node.get("type") == "BASE_TABLE" and node.get("schema_name"):
                found.add(node["schema_name"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(tree)
    return found - {allowed}


def run_query(con, sql: str, max_rows: int = DEFAULT_MAX_ROWS,
              schema: str | None = None) -> tuple[list[str], list[tuple]]:
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
    # An arm may read its own warehouse and nothing else. `search_path` HIDES the other schemas;
    # only this FORBIDS them, and the difference matters because reaching into another arm would
    # not crash — it would return a plausible number computed from the wrong environment, which no
    # downstream check could catch.
    if schema is not None:
        foreign = foreign_schemas(con, stripped, schema)
        if foreign:
            raise QueryError(
                f"This query names {', '.join(sorted(foreign))}, which is outside this "
                f"environment. Use the tables listed by get_schema, unqualified.")
    try:
        cur = con.execute(stripped)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
    except Exception as exc:  # noqa: BLE001 — surface the DB message verbatim
        raise QueryError(str(exc)) from exc
    return columns, rows
