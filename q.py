"""Run one-off SQL against the warehouse WITH the star views built (dim_*/fct_*/agg_*).

    uv run python q.py "SELECT count(*) FROM dim_users"
    uv run python q.py "SELECT count(*) FROM dim_users WHERE NOT is_internal"

Opening data/warehouse.duckdb directly (duckdb CLI) shows only the RAW tables; the
dim_/fct_/agg_ names the eval SQL uses are views created at runtime, so use this.
"""

import sys

from harness.warehouse import open_warehouse

if len(sys.argv) < 2:
    con = open_warehouse(create_star_views=True)
    tables = con.execute(
        "select table_name from information_schema.tables order by table_name").fetchall()
    print("usage: uv run python q.py \"SELECT ...\"\n\navailable tables/views:")
    print("  " + ", ".join(t[0] for t in tables))
    sys.exit(0)

con = open_warehouse(create_star_views=True)
con.sql(" ".join(sys.argv[1:])).show(max_rows=100)
