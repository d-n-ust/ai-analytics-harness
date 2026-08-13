"""The layering rule, enforced rather than documented.

    cli  ->  agent  ->  {guardrails, semantic, models}  ->  {warehouse, dialect}

A README that states this decays the first time someone reaches for a driver to fix a bug in a
hurry. A test that walks the import graph does not. ruff's banned-api rules catch the same thing
at lint time; this catches it for transitive imports, which ruff cannot see.

The rule buys two concrete things. Adding Snowflake must not require touching the agent, and
shipping a DuckDB-only build must not drag a Postgres driver into a signed bundle. Both stop
being true the moment `agent/` imports a driver directly.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "troodos"

# Concrete drivers and vendor SDKs. Only the adapter packages may name these.
DRIVERS = {"duckdb", "psycopg", "psycopg2", "snowflake", "google", "databricks", "sqlalchemy"}
SDKS = {"anthropic", "openai", "boto3"}

# Packages allowed to import a driver — they exist precisely to wrap one.
ADAPTER_PACKAGES = {"warehouse", "models", "dialect"}


def _modules():
    for path in sorted(SRC.rglob("*.py")):
        yield path, path.relative_to(SRC).parts[0]


def _imported_roots(path: pathlib.Path) -> set[str]:
    """Top-level package of every import in a file, including function-local ones.

    Walks the whole tree rather than the module top level on purpose: `providers.py` imports its
    SDKs inside functions to keep them off the startup path, and an import that is lazy is still
    an import for the purposes of this rule.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path,package", list(_modules()), ids=lambda v: str(v))
def test_engine_never_imports_a_driver(path, package):
    if package in ADAPTER_PACKAGES:
        pytest.skip(f"{package}/ is an adapter package — drivers belong here")
    offenders = _imported_roots(path) & (DRIVERS | SDKS)
    assert not offenders, (
        f"{path.relative_to(SRC)} imports {sorted(offenders)}. "
        f"Engine code must go through the Warehouse / Dialect / Model protocols. "
        f"If this file genuinely wraps a driver, it belongs under {sorted(ADAPTER_PACKAGES)}."
    )


def test_dialect_does_not_depend_on_warehouse():
    """Dialects describe SQL, warehouses hold connections. A dialect that reaches for a
    connection has started doing introspection, which is the warehouse's job — and it makes the
    dialect untestable without a live database."""
    for path in sorted((SRC / "dialect").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "warehouse" in node.module:
                pytest.fail(f"{path.name} imports from warehouse; dialects must stay standalone")
            # `from ..warehouse import x` shows up as a relative import with no module match
            if isinstance(node, ast.ImportFrom) and node.level and node.module == "warehouse":
                pytest.fail(f"{path.name} imports from warehouse; dialects must stay standalone")
