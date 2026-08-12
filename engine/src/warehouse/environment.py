"""An arm's warehouse, as its own schema.

WHAT AN ARM COULD NOT SAY BEFORE. An arm declared a rung, and the rung selected between two
hardcoded tuples of table names. It could not add a view, rename a table, split a mixed one, or
carry its own documentation — so the `modelled` column of the primitives matrix, where a warehouse
object makes a fact structurally true, was inexpressible. `experiments/04_repair_matrix/
primitives_matrix.md` has that column empty for every row, and this is why.

WHAT THIS GIVES INSTEAD. Each arm gets a DuckDB schema holding exactly the objects its agent may
see, and a cursor whose `search_path` is that schema. Four properties were measured before the
module was written, because each one decides whether the design works at all:

    per-cursor search_path      two cursors resolve the SAME unqualified name to different objects,
                                so arms no longer share warehouse state and can run concurrently
    lazy view resolution        a view's references resolve in the QUERYING cursor's path, not the
                                creating one — so every arm view must qualify its sources, or it
                                breaks when the agent reads it
    `main` is always searched   an arm cannot be isolated while the source tables live in `main`;
                                they move to `_source`, which no arm's path includes
    DROP SCHEMA ... CASCADE     teardown is one statement and cannot leak into the next arm

HIDING IS NOT FORBIDDING, so there are two mechanisms and both are needed. `search_path` hides the
other schemas; `warehouse.foreign_schemas` refuses a statement that NAMES one, read off DuckDB's
parse tree rather than the query text. Without the second, `SELECT count(*) FROM _star.dim_users`
still answers — and it would not crash, it would return a plausible number computed from another
arm's warehouse, which no downstream check could catch.

For comparison, what this replaces did not even hide: `visible_tables(rung)` only decided what
`get_schema` LISTS, so an agent at rung 2 could always query the raw tables by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent

__all__ = ["RAW", "SOURCE", "Environment", "build", "ensure_source", "presets", "teardown"]

# Where the generated tables live once they are out of `main`. Leading underscore because no arm
# ever names it: it is the warehouse's private ground truth, and an arm sees only its own views.
SOURCE = "_source"

# The raw tables as the generator writes them. An arm asking for `raw` gets these unchanged, which
# is the messy baseline: cryptic names, coded columns, nothing describing any of it.
RAW = ("u", "hab", "evt", "subs", "spend", "ref")


@dataclass(frozen=True)
class Environment:
    """One arm's warehouse: a schema name, the objects in it, and their descriptions.

    `tables` maps the name the agent sees to the SQL that defines it. Every definition must qualify
    its sources with `_source.`, because a view resolves in the reader's search_path and the agent's
    path contains only this schema.
    """

    schema: str
    preset_sql: str = ""
    docs_sql: str = ""
    tables: dict[str, str] = field(default_factory=dict)

    def create(self, con) -> None:
        """Build the schema: the preset's DDL first, then this arm's own views.

        Both run on a cursor whose search_path is this schema, so unqualified CREATE VIEW lands
        here and nowhere else. Dropped first, so a rerun cannot inherit a previous arm's objects.
        """
        from warehouse.warehouse import _statements

        teardown(con, self.schema)
        con.execute(f'CREATE SCHEMA "{self.schema}"')
        cur = con.cursor()
        cur.execute(f"SET search_path='{self.schema}'")
        for stmt in _statements(self.preset_sql):
            cur.execute(stmt)
        # Arm-local views last, so an arm may REPLACE a preset object rather than only add to it.
        for name, sql in self.tables.items():
            cur.execute(f'CREATE OR REPLACE VIEW "{self.schema}"."{name}" AS {sql}')
        # Comments go on afterwards: COMMENT ON needs the object to exist, and an arm's own view
        # should be describable by the same file that describes the preset's.
        for stmt in _statements(self.docs_sql):
            cur.execute(stmt)

    def cursor(self, con):
        """A cursor scoped to this arm — the handle the agent's tools are given.

        `search_path` is this schema alone. `_source` is deliberately absent, so an unqualified
        reference to a raw table fails rather than silently returning ground truth.
        """
        cur = con.cursor()
        cur.execute(f"SET search_path='{self.schema}'")
        return cur


def ensure_source(con) -> None:
    """Move the generated tables into `_source`, once.

    A copy rather than a move: DuckDB has no `ALTER TABLE ... SET SCHEMA`. It runs on a local file
    and the largest table is under 200k rows, so the cost is a fraction of a second and it happens
    only when `main` still holds the originals.
    """
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{SOURCE}"')
    present = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [SOURCE],
    ).fetchall()}
    for name in RAW:
        if name in present:
            continue
        in_main = con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = ?", [name],
        ).fetchone()[0]
        if in_main:
            con.execute(f'CREATE TABLE "{SOURCE}"."{name}" AS SELECT * FROM main."{name}"')


def teardown(con, schema: str) -> None:
    """Remove an arm's schema and everything in it. One statement, so nothing survives it."""
    con.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


# A PRESET IS A FILE, not a branch in this module. `warehouse/presets/<name>.sql` holds the DDL for
# one warehouse shape, so `tables: messy_tables` in an arm points at something a reader can open
# without knowing Python — which was the whole complaint about `rung: 1`, one level down. Adding a
# shape means adding a file; nothing here needs to learn about it.
PRESETS_DIR = _HERE / "presets"
# Descriptions live beside the shapes, one file per preset, for the same reason: `docs: messy_tables`
# in an arm must point at something a reader can open. Documentation used to be switched on by a
# RUNG NUMBER (1.5 meant "documented"), which made two arms differing only in documentation look
# identical in their declarations — the exact opacity this whole module exists to remove.
# Named `grain` rather than `docs` because a second directory called docs, one level
# down from the repo's own docs/, made every grep for either return both.
GRAIN_DIR = _HERE / "grain"


def presets() -> tuple[str, ...]:
    """Every shape an arm can ask for. Discovered from the directory, so the list cannot disagree
    with what is on disk — the failure mode of every registry ever written."""
    return tuple(sorted(p.stem for p in PRESETS_DIR.glob("*.sql")))


def build(con, schema: str, spec: dict | None = None) -> Environment:
    """One arm's warehouse, from its declaration.

        tables: <preset>        a file in warehouse/presets/ — the shape the agent sees
        views:  {name: sql}     arm-local objects, created after the preset
        docs:   {name: text}    descriptions, merged over the shared ones

    `views` is what makes the matrix's `modelled` column expressible: an arm can split a mixed
    table, pre-join a mart or materialise a roll-up, and the whole thing is removed afterwards by
    dropping one schema.
    """
    spec = dict(spec or {})
    name = spec.get("tables", "star_schema")
    path = PRESETS_DIR / f"{name}.sql"
    if not path.exists():
        raise ValueError(f"unknown table preset {name!r}; available: {list(presets())}")

    # `docs:` names a file of COMMENT ON statements, or is absent. ABSENT MEANS UNDOCUMENTED —
    # which is what most warehouses are, so it is the baseline rather than a missing setting.
    docs_sql = ""
    declared = spec.get("docs")
    if declared:
        doc_path = GRAIN_DIR / f"{declared}.sql"
        if not doc_path.exists():
            raise ValueError(f"unknown docs preset {declared!r}; available: "
                             f"{sorted(q.stem for q in GRAIN_DIR.glob('*.sql'))}")
        docs_sql = doc_path.read_text()

    return Environment(schema=schema, preset_sql=path.read_text(), docs_sql=docs_sql,
                       tables=dict(spec.get("views") or {}))



