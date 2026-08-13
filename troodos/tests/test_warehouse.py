"""The connection-layer guarantees.

The read-only tests are the important ones. They are written as an adversarial list rather than
a happy path because the check they protect replaced a `sql.startswith("select")` test, and each
case below is a way that check was actually defeated.
"""

from __future__ import annotations

import datetime as dt

import pytest

from troodos.dialect import DuckDBDialect
from troodos.dialect.base import DialectError
from troodos.warehouse import connect
from troodos.warehouse.base import ReadOnlyViolation, WarehouseError


@pytest.fixture
def wh():
    w = connect(":memory:")
    w._con.execute("CREATE TABLE dim_users(user_id INT, region VARCHAR, is_internal BOOLEAN)")
    w._con.execute("INSERT INTO dim_users VALUES (1,'EU',false),(2,'NA',false),(3,'EU',true)")
    w._con.execute("CREATE VIEW v_users AS SELECT * FROM dim_users WHERE NOT is_internal")
    w._con.execute("COMMENT ON TABLE dim_users IS 'One row per user.'")
    w._con.execute("COMMENT ON COLUMN dim_users.region IS 'Billing region.'")
    yield w
    w.close()


# --------------------------------------------------------------------- read-only

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select count(*) from dim_users",
        "WITH x AS (SELECT 1 AS a) SELECT a FROM x",       # a CTE is still a read
        "  \n SELECT 1 \n ",                                # whitespace is not a signal
        "-- a comment\nSELECT 1",                           # nor is a leading comment
    ],
)
def test_reads_are_allowed(wh, sql):
    wh.assert_read_only(sql)


@pytest.mark.parametrize(
    "sql,why",
    [
        ("DELETE FROM dim_users", "plain write"),
        ("DROP TABLE dim_users", "DDL"),
        ("UPDATE dim_users SET region='X'", "update"),
        ("INSERT INTO dim_users VALUES (9,'EU',false)", "insert"),
        ("CREATE TABLE t(a INT)", "create"),
        ("ATTACH 'other.db'", "attach — reaches a second database"),
        ("COPY dim_users TO 'out.csv'", "copy — writes the filesystem"),
        ("-- looks harmless\nDROP TABLE dim_users", "write hidden behind a comment"),
        ("SELECT 1; DROP TABLE dim_users", "write chained after a read"),
        ("", "empty"),
    ],
)
def test_writes_are_blocked(wh, sql, why):
    with pytest.raises(ReadOnlyViolation):
        wh.assert_read_only(sql)


def test_execute_refuses_a_write_before_touching_the_database(wh):
    with pytest.raises(ReadOnlyViolation):
        wh.execute("DELETE FROM dim_users")
    assert wh.execute("SELECT count(*) FROM dim_users").scalar() == 3


def test_database_errors_reach_the_caller_verbatim(wh):
    """The model's self-correction loop is only as good as the message it is shown. A wrapped
    'query failed' teaches it nothing; the database naming the missing column teaches it
    everything."""
    with pytest.raises(WarehouseError, match="nonexistent_column"):
        wh.execute("SELECT nonexistent_column FROM dim_users")


# --------------------------------------------------------------------- results

def test_truncation_is_reported_not_inferred(wh):
    """A caller that cannot tell 'exactly N rows' from 'at least N rows' eventually reports a
    row cap as a total."""
    result = wh.execute("SELECT * FROM dim_users", max_rows=2)
    assert len(result.rows) == 2
    assert result.truncated is True
    assert wh.execute("SELECT * FROM dim_users", max_rows=10).truncated is False


def test_scalar_only_for_one_by_one(wh):
    assert wh.execute("SELECT count(*) FROM dim_users").scalar() == 3
    assert wh.execute("SELECT * FROM dim_users").scalar() is None


# --------------------------------------------------------------------- introspection

def test_relations_carry_comments(wh):
    by_name = {r.name: r for r in wh.relations()}
    assert by_name["dim_users"].comment == "One row per user."
    region = next(c for c in by_name["dim_users"].columns if c.name == "region")
    assert region.comment == "Billing region."


def test_views_sort_before_tables(wh):
    """In a modelled warehouse the views are usually the curated layer. Showing them first is
    what nudges an agent toward the governed relation rather than the raw one."""
    assert [r.name for r in wh.relations()][0] == "v_users"


def test_documented_flag_reflects_table_or_column_comments(wh):
    by_name = {r.name: r for r in wh.relations()}
    assert by_name["dim_users"].documented is True
    assert by_name["v_users"].documented is False


def test_label_never_leaks_a_motherduck_token():
    """This string reaches traces, logs and error messages, any of which may be pasted into a
    public issue."""
    from troodos.warehouse.duckdb import DuckDBWarehouse

    w = DuckDBWarehouse.__new__(DuckDBWarehouse)
    w._source = "md:analytics?motherduck_token=SECRET_VALUE"
    assert "SECRET_VALUE" not in w.label
    assert w.label == "motherduck:analytics"


# --------------------------------------------------------------------- registry

def test_bare_path_is_accepted(tmp_path):
    """Refusing a bare path in favour of a scheme is the kind of pedantry that makes a first run
    feel hostile. A path is what a person types first."""
    import duckdb

    p = tmp_path / "x.duckdb"
    duckdb.connect(str(p)).close()
    with connect(str(p)) as w:
        assert w.label == "duckdb:x.duckdb"


def test_unknown_target_names_what_is_supported():
    with pytest.raises(WarehouseError, match="duckdb:"):
        connect("postgres://localhost/mydb")


def test_missing_file_is_a_clear_error(tmp_path):
    with pytest.raises(WarehouseError, match="no database at"):
        connect(str(tmp_path / "nope.duckdb"))


# --------------------------------------------------------------------- dialect

def test_truncate_date_yields_a_date_not_a_timestamp(wh):
    """Without the cast, a grouped period is a timestamp at midnight, which compares unequal to
    the DATE literals the same query filters on — and silently returns nothing."""
    d = DuckDBDialect()
    sql = f"SELECT {d.truncate_date('ts', 'week')} AS period FROM (SELECT TIMESTAMP '2026-07-08 13:45' AS ts)"
    result = wh.execute(sql)
    assert result.rows[0][0] == dt.date(2026, 7, 6)  # the Monday


def test_date_literal_requires_a_real_date():
    """Every value interpolated into SQL is a place an injection can hide. A typed parameter
    cannot carry one, so the caller is forced to have parsed it first."""
    d = DuckDBDialect()
    assert d.date_literal(dt.date(2026, 7, 12)) == "DATE '2026-07-12'"
    with pytest.raises(DialectError):
        d.date_literal("2026-07-12'; DROP TABLE dim_users --")


def test_unknown_grain_is_refused():
    with pytest.raises(DialectError, match="unknown time grain"):
        DuckDBDialect().truncate_date("ts", "fortnight")


def test_string_literal_escapes_quotes():
    assert DuckDBDialect().string_literal("O'Brien") == "'O''Brien'"


# --------------------------------------------------------------------- overlay

def test_overlay_creates_views_without_write_access(tmp_path):
    """The common case: the user's curated layer is not in their warehouse, because they only
    have read access to it. Temporary views give the agent the curated relations without
    needing — or granting — write permission."""
    import duckdb

    from troodos.warehouse.duckdb import DuckDBWarehouse

    db = tmp_path / "raw.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE u(id INT, plat VARCHAR, internal INT)")
    con.execute("INSERT INTO u VALUES (1,'iOS',0),(2,'ios',0),(3,'web',1)")
    con.close()

    sql = tmp_path / "star.sql"
    sql.write_text(
        "-- a curated layer; note the semicolon in this comment; must not split the statement\n"
        "CREATE OR REPLACE VIEW dim_users AS\n"
        "  SELECT id, lower(plat) AS platform FROM u WHERE internal = 0;\n"
    )

    with DuckDBWarehouse(str(db), read_only=True, overlay=str(sql)) as w:
        assert "dim_users" in {r.name for r in w.relations()}
        assert w.execute("SELECT count(*) FROM dim_users").scalar() == 2
        # the overlay must not have weakened the read-only guarantee
        with pytest.raises(ReadOnlyViolation):
            w.execute("DROP VIEW dim_users")

    # and nothing was persisted into the user's database
    con = duckdb.connect(str(db), read_only=True)
    names = {r[0] for r in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()}
    con.close()
    assert "dim_users" not in names


def test_missing_overlay_file_is_a_clear_error(tmp_path):
    import duckdb

    from troodos.warehouse.duckdb import DuckDBWarehouse

    db = tmp_path / "x.duckdb"
    duckdb.connect(str(db)).close()
    with pytest.raises(WarehouseError, match="overlay file not found"):
        DuckDBWarehouse(str(db), overlay=str(tmp_path / "nope.sql"))


def test_broken_overlay_statement_names_the_statement(tmp_path):
    import duckdb

    from troodos.warehouse.duckdb import DuckDBWarehouse

    db = tmp_path / "x.duckdb"
    duckdb.connect(str(db)).close()
    sql = tmp_path / "bad.sql"
    sql.write_text("CREATE OR REPLACE VIEW v AS SELECT * FROM table_that_does_not_exist;")
    with pytest.raises(WarehouseError, match="overlay statement failed"):
        DuckDBWarehouse(str(db), overlay=str(sql))


# --------------------------------------------------------------------- schema selection

def test_schema_scopes_what_the_agent_sees(tmp_path):
    """Real warehouses are not one flat namespace. Curated models sit in `analytics` or `marts`
    beside staging schemas and other teams' work; the agent should see one of them, not all."""
    import duckdb

    from troodos.warehouse.duckdb import DuckDBWarehouse

    db = tmp_path / "multi.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA analytics; CREATE SCHEMA staging")
    con.execute("CREATE TABLE analytics.dim_users(id INT)")
    con.execute("INSERT INTO analytics.dim_users VALUES (1),(2)")
    con.execute("CREATE TABLE staging.raw_users(id INT)")
    con.close()

    with DuckDBWarehouse(str(db), schema="analytics") as w:
        names = {r.name for r in w.relations()}
        assert names == {"dim_users"}, "staging must not be visible"
        # search_path makes the unqualified name resolve, so a semantic spec stays portable
        assert w.execute("SELECT count(*) FROM dim_users").scalar() == 2
        # and the chosen schema is implicit in the name, not repeated in it
        assert next(iter(w.relations())).qualified == "dim_users"


def test_unknown_schema_lists_the_real_ones(tmp_path):
    import duckdb

    from troodos.warehouse.duckdb import DuckDBWarehouse

    db = tmp_path / "s.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA analytics")
    con.close()
    with pytest.raises(WarehouseError, match="analytics"):
        DuckDBWarehouse(str(db), schema="typo")
