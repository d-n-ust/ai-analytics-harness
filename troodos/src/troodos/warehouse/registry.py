"""Resolving a connection string to an adapter.

Adapters are registered rather than imported eagerly, so that installing troodos does not install
every driver. A user connecting to DuckDB should never have `snowflake-connector-python` on disk:
it costs install time, it costs bundle size when this is signed and shipped, and every unused
native wheel is another Mach-O object that has to be re-signed and notarized.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .base import Warehouse, WarehouseError

# scheme -> factory. Kept as thunks so the driver import happens on connect, not on import.
_ADAPTERS: dict[str, Callable[..., Warehouse]] = {}


def register(scheme: str, factory: Callable[..., Warehouse]) -> None:
    _ADAPTERS[scheme] = factory


def _duckdb_factory(target: str, **kw) -> Warehouse:
    from .duckdb import DuckDBWarehouse

    return DuckDBWarehouse(target, **kw)


register("duckdb", _duckdb_factory)
register("md", _duckdb_factory)          # MotherDuck, via the same driver
register("motherduck", _duckdb_factory)


def schemes() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


def connect(target: str | Path, **kw) -> Warehouse:
    """Open a warehouse from a connection string.

    Accepted forms:
        analytics.duckdb            a path — the extension decides the adapter
        duckdb:analytics.duckdb     explicit
        md:my_database              MotherDuck
        :memory:                    ephemeral

    A bare path is supported because it is what a person types first, and refusing it in favour
    of a scheme is the kind of pedantry that makes a first run feel hostile.
    """
    target = str(target)

    if target == ":memory:":
        return _duckdb_factory(":memory:", **kw)

    scheme, sep, rest = target.partition(":")
    # A Windows drive letter or a relative path with a colon must not be read as a scheme.
    if sep and scheme in _ADAPTERS:
        payload = target if scheme in ("md", "motherduck") else rest
        return _ADAPTERS[scheme](payload, **kw)

    suffix = Path(target).suffix.lower()
    if suffix in (".duckdb", ".db", ".ddb"):
        return _duckdb_factory(target, **kw)

    raise WarehouseError(
        f"don't know how to connect to {target!r}. "
        f"Use a path to a .duckdb file, or one of: {', '.join(s + ':' for s in schemes())}"
    )
