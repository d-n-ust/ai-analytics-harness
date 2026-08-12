"""DuckDB adapter — local files, in-memory, and MotherDuck.

DuckDB earns first place for a reason beyond being easy: it is a federation layer. `ATTACH`
reaches Postgres, MySQL and SQLite; `httpfs` reads Parquet on S3; `iceberg` and `delta` read
open table formats. So a user can point this at their own database through DuckDB without this
project shipping a driver for it. That covers a real slice of warehouses on day one and leaves
Snowflake and BigQuery as the two that eventually need native adapters.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from ..dialect.duckdb import DuckDBDialect
from .base import Column, ReadOnlyViolation, Relation, Result, WarehouseError

# Rewrites `CREATE [OR REPLACE] VIEW` to its TEMP form when applying an overlay. Anchored to the
# start of a statement so it cannot touch a `create view` appearing inside a string or comment.
_VIEW_HEAD = re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+", re.IGNORECASE)

# Catalog entries DuckDB creates for itself. Showing them to an agent is pure distraction: it
# burns context and invites questions about the catalog instead of the business.
_SYSTEM_SCHEMAS = frozenset({"information_schema", "pg_catalog", "main.information_schema"})


class DuckDBWarehouse:
    """A DuckDB connection presented through the `Warehouse` protocol.

    `read_only=True` is the default and is passed to DuckDB itself, not merely honoured by this
    class. Defence in depth: `assert_read_only` stops a write before it is sent, and the
    connection flag means a bug in that check still cannot mutate the user's database. The two
    together are why raw SQL can be offered at all.
    """

    def __init__(
        self,
        source: str | Path = ":memory:",
        *,
        read_only: bool = True,
        visible: tuple[str, ...] | None = None,
        overlay: str | Path | None = None,
        schema: str | None = None,
    ) -> None:
        self._source = str(source)
        self._dialect = DuckDBDialect()
        self._visible = frozenset(visible) if visible else None

        is_motherduck = self._source.startswith("md:")
        is_memory = self._source == ":memory:"

        if not (is_motherduck or is_memory):
            path = Path(self._source).expanduser()
            if not path.exists():
                raise WarehouseError(
                    f"no database at {path}. Check the path, or run `troodos connect` to set one up."
                )
            self._source = str(path)

        try:
            # read_only is meaningless for a fresh in-memory database — there is nothing to
            # protect and DuckDB rejects the combination.
            if is_memory:
                self._con = duckdb.connect(":memory:")
            else:
                self._con = duckdb.connect(self._source, read_only=read_only)
        except Exception as exc:
            raise WarehouseError(f"could not open {self.label}: {exc}") from exc

        self._schema = schema
        if schema:
            self._use_schema(schema)

        if overlay:
            self._apply_overlay(Path(overlay).expanduser())

    def _use_schema(self, schema: str) -> None:
        """Point unqualified names at one schema, and narrow what the agent sees to it.

        Real warehouses are not one flat namespace. The curated models a user wants answered from
        live in `analytics` or `marts` or `_star`, next to staging schemas, source replicas and
        other teams' work. Without this, every metric definition would have to carry a schema
        prefix — which makes the same semantic spec unusable against a second warehouse that
        organises its schemas differently.

        Setting `search_path` rather than rewriting SQL means a governed definition can say
        `agg_active_days` and be portable; where that resolves is a property of the connection,
        which is exactly where deployment detail belongs.
        """
        known = {r[0] for r in self._con.execute(
            "SELECT schema_name FROM information_schema.schemata").fetchall()}
        if schema not in known:
            self.close()
            raise WarehouseError(
                f"no schema named {schema!r} in {self.label}. "
                f"Available: {', '.join(sorted(s for s in known if s not in _SYSTEM_SCHEMAS))}"
            )
        self._con.execute(f"SET search_path = {self._dialect.quote_ident(schema)}")

    def _apply_overlay(self, path: Path) -> None:
        """Apply a SQL file of view definitions as TEMPORARY views.

        This is the answer to a situation that is the norm rather than the exception: the curated
        layer a user wants the agent to see is not in their warehouse, because they only have
        read access to it. Their cleaning logic lives in a dbt project, a SQL file, or a
        colleague's head.

        Temporary views solve it exactly. They exist only for this connection, so no write
        permission is needed and nothing about the user's database changes — but to the agent
        they are indistinguishable from real relations, which is what matters. DuckDB still
        refuses a persistent `CREATE`, so the read-only guarantee is untouched.

        `CREATE VIEW` is rewritten to `CREATE TEMP VIEW` so that an existing file (a dbt-exported
        script, or a warehouse bootstrap like the harness's `star.sql`) works unmodified. The
        rewrite is anchored to the head of a statement, so it cannot alter one inside a string.
        """
        if not path.exists():
            raise WarehouseError(f"overlay file not found: {path}")

        # Strip line comments before splitting, so a semicolon inside `-- ...` cannot split a
        # statement in half and produce two invalid fragments.
        text = "\n".join(re.sub(r"--.*$", "", line) for line in path.read_text().splitlines())
        for chunk in text.split(";"):
            statement = chunk.strip()
            if not statement:
                continue
            if _VIEW_HEAD.match(statement):
                statement = _VIEW_HEAD.sub("CREATE OR REPLACE TEMP VIEW ", statement, count=1)
            try:
                self._con.execute(statement)
            except Exception as exc:
                head = " ".join(statement.split())[:70]
                raise WarehouseError(f"overlay statement failed ({head}...): {exc}") from exc

    @property
    def dialect(self) -> DuckDBDialect:
        return self._dialect

    @property
    def label(self) -> str:
        """MotherDuck sources are reported without their token — this string reaches traces,
        logs and error messages, and any of those may be pasted into an issue."""
        if self._source.startswith("md:"):
            return f"motherduck:{self._source[3:].split('?')[0]}"
        if self._source == ":memory:":
            return "duckdb:memory"
        return f"duckdb:{Path(self._source).name}"

    # ---------------------------------------------------------------- introspection

    def relations(self) -> tuple[Relation, ...]:
        """Tables and views with their `COMMENT ON` text.

        Comments are read because they are grounding that already exists: dbt's `persist_docs`
        writes model and column documentation straight into them, so a well-run warehouse hands
        over a large part of a semantic spec for free. They describe; they do not govern — no
        comment carries a grain, a default filter or an aggregate — so this feeds the
        bootstrapper, not the metric compiler.
        """
        cols_by_table: dict[tuple[str, str], list[Column]] = {}
        for schema, table, name, dtype, comment, nullable in self._con.execute(
            """
            SELECT schema_name, table_name, column_name, data_type, comment, is_nullable
            FROM duckdb_columns()
            ORDER BY schema_name, table_name, column_index
            """
        ).fetchall():
            cols_by_table.setdefault((schema, table), []).append(
                Column(name=name, type=str(dtype), comment=comment, nullable=bool(nullable))
            )

        found: list[Relation] = []
        for kind, query in (
            ("table", "SELECT schema_name, table_name, comment FROM duckdb_tables()"),
            ("view", "SELECT schema_name, view_name, comment FROM duckdb_views() WHERE NOT internal"),
        ):
            for schema, name, comment in self._con.execute(query).fetchall():
                if schema in _SYSTEM_SCHEMAS:
                    continue
                # A chosen schema is the whole world: showing relations the agent's search_path
                # cannot resolve invites it to name something that will fail.
                if self._schema is not None and schema != self._schema:
                    continue
                if self._visible is not None and name not in self._visible:
                    continue
                found.append(
                    Relation(
                        name=name,
                        kind=kind,
                        # `main` is DuckDB's default, and a chosen schema is implicit in every
                        # name once search_path points at it. Qualifying either adds noise to
                        # every prompt and error message for no information.
                        schema=None if schema in ("main", self._schema) else schema,
                        comment=comment,
                        columns=tuple(cols_by_table.get((schema, name), ())),
                    )
                )
        return tuple(sorted(found, key=lambda r: (r.kind != "view", r.qualified)))

    # ---------------------------------------------------------------- safety

    def assert_read_only(self, sql: str) -> None:
        """Reject anything that is not exactly one read statement.

        Enforced by DuckDB's own parser rather than by inspecting the string. A prefix check on
        `select` is defeated three ways that all appear in practice: a leading `--` comment, a
        `WITH` clause, and a second statement chained after a semicolon. Classifying the parsed
        statement catches all three, and catches every write verb without enumerating them.
        """
        stripped = sql.strip()
        if not stripped:
            raise ReadOnlyViolation("empty statement.")
        try:
            statements = self._con.extract_statements(stripped)
        except Exception as exc:
            raise ReadOnlyViolation(f"could not parse: {exc}") from exc
        if len(statements) != 1:
            raise ReadOnlyViolation(
                f"run a single statement; got {len(statements)}."
            )
        if statements[0].type != duckdb.StatementType.SELECT:
            raise ReadOnlyViolation("only read-only SELECT/WITH queries are allowed.")

    def execute(self, sql: str, max_rows: int = 100) -> Result:
        self.assert_read_only(sql)
        try:
            cur = self._con.execute(sql.strip())
            columns = tuple(d[0] for d in cur.description) if cur.description else ()
            # One row beyond the cap, so truncation is observed rather than inferred. A caller
            # that cannot distinguish "exactly 100 rows" from "at least 100 rows" will eventually
            # report a total that is really a limit.
            rows = cur.fetchmany(max_rows + 1)
        except Exception as exc:
            # The database's own message, unwrapped: it names the column the model invented,
            # which is the whole value of feeding an error back into a self-correction loop.
            raise WarehouseError(str(exc)) from exc
        truncated = len(rows) > max_rows
        return Result(columns=columns, rows=tuple(rows[:max_rows]), truncated=truncated)

    def close(self) -> None:
        try:
            self._con.close()
        except Exception:  # noqa: BLE001 — closing a dead connection is not a caller's problem
            pass

    def __enter__(self) -> DuckDBWarehouse:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
