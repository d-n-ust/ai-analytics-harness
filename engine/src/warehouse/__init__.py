"""The warehouse: the generated star, its live DuckDB, and the query interface the agent's tools use.

This is the package's public API. Depend on these names, not on the internal module layout.
"""

from .config import NAMED_PERIODS, TIME_GRAINS, NotConfigured
from .warehouse import (
    DEFAULT_MAX_ROWS,
    QueryError,
    describe_table,
    open_warehouse,
    run_query,
    schema_text,
    set_star,
)

__all__ = [
    "run_query", "describe_table", "schema_text", "open_warehouse", "set_star",
    "QueryError", "DEFAULT_MAX_ROWS", "NAMED_PERIODS", "TIME_GRAINS", "NotConfigured",
]
