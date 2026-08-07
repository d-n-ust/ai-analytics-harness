"""Run MetricFlow against the harness warehouse, with no dbt anywhere.

MetricFlow is usually reached through dbt: a project, `dbt parse`, a compiled `manifest.json`.
None of that is required. The engine ships a YAML parser of its own
(`parse_directory_of_yaml_files_to_semantic_manifest`) and a DuckDB SQL renderer, so a directory of
`semantic_model:` / `metric:` documents plus the thirty lines below is a working semantic layer.

    metricflow alone          14 packages, no dbt-core
    dbt-metricflow + adapter  51 packages, plus a telemetry client

THE ONE SIDE EFFECT, stated because it touches the warehouse. MetricFlow answers time-filtered
queries by joining a *time spine* — a table with one row per day. `ensure_time_spine` creates it as
a VIEW over the warehouse's own date range. A view is metadata: no rows are copied, and
`bench data` regenerates the file anyway. Without it, every question with a period in it fails,
and every question in this study has one.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from metricflow.data_table.mf_table import MetricFlowDataTable
from metricflow.protocols.sql_client import SqlClient, SqlEngine
from metricflow.sql.render.duckdb_renderer import DuckDbSqlPlanRenderer

WAREHOUSE = Path(__file__).resolve().parents[3] / "warehouse" / "warehouse.duckdb"


class DuckDbClient(SqlClient):
    """The entire adapter. MetricFlow's SqlClient protocol is four methods and two properties."""

    def __init__(self, path: Path | str = WAREHOUSE) -> None:
        self._con = duckdb.connect(str(path))
        self.ensure_time_spine()

    def ensure_time_spine(self) -> None:
        """One row per day, spanning the warehouse. A view, so nothing is materialised."""
        self._con.execute("""
            CREATE OR REPLACE VIEW main.mf_time_spine AS
            SELECT CAST(d AS DATE) AS ds
            FROM (SELECT UNNEST(generate_series(
                     (SELECT min(active_date) FROM main.agg_active_days),
                     (SELECT max(active_date) FROM main.agg_active_days),
                     INTERVAL 1 DAY)) AS d)
        """)

    @property
    def sql_engine_type(self) -> SqlEngine:
        return SqlEngine.DUCKDB

    @property
    def sql_plan_renderer(self) -> DuckDbSqlPlanRenderer:
        return DuckDbSqlPlanRenderer()

    def query(self, stmt: str, sql_bind_parameter_set=None) -> MetricFlowDataTable:
        cur = self._con.execute(stmt)
        return MetricFlowDataTable.create_from_rows(
            column_names=[d[0] for d in cur.description], rows=cur.fetchall())

    def execute(self, stmt: str, sql_bind_parameter_set=None) -> None:
        self._con.execute(stmt)

    def dry_run(self, stmt: str, sql_bind_parameter_set=None) -> None:
        self._con.execute(f"EXPLAIN {stmt}")

    def render_bind_parameter_key(self, bind_parameter_key: str) -> str:
        return f"${bind_parameter_key}"

    def close(self) -> None:
        self._con.close()


def engine_for(arm: str):
    """A MetricFlowEngine over one arm's YAML directory."""
    from metricflow.engine.metricflow_engine import MetricFlowEngine
    from metricflow_semantic_interfaces.parsing.dir_to_model import (
        parse_directory_of_yaml_files_to_semantic_manifest,
    )
    from metricflow_semantics.model.semantic_manifest_lookup import SemanticManifestLookup

    directory = Path(__file__).resolve().parent / "layers" / arm
    if not directory.exists():
        raise SystemExit(f"no such arm: {arm}\navailable: "
                         + ", ".join(sorted(p.name for p in (directory.parent).iterdir())))
    result = parse_directory_of_yaml_files_to_semantic_manifest(str(directory))
    return MetricFlowEngine(
        semantic_manifest_lookup=SemanticManifestLookup(result.semantic_manifest),
        sql_client=DuckDbClient(),
    )
