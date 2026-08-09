"""dbt MetricFlow behind the same interface as this repository's own layer.

So a study can name its engine and the agent does not change:

    engine: harness       semantic/semantic.py — this project's YAML and governance model
    engine: metricflow    a directory of MetricFlow YAML, parsed and queried by MetricFlow

WHY IT IS WORTH THE TROUBLE. Study 02's finding was about rendering: segments appeared in a global
list that never said which metric offered them. That is our renderer. Running the same study on an
engine thousands of teams use in production is the difference between a claim about semantic
modelling and a claim about one file format.

There is a second reason, discovered while porting study 01 and worth more than the first.
**MetricFlow has no synonym field.** A metric carries `name`, `description` and a single `label`,
and that is all. Study 01's headline is unattributable partly because one arm carried bespoke
synonyms matching the question wording; on this engine that confound has nowhere to live.

WHAT IT CANNOT DO, declared rather than discovered mid-run:

    coverage    MetricFlow has no data-coverage window. `in_coverage` would have to invent one.
    segments    a metric filter is an expression over a dimension. There is no reusable, named,
                described population — only the predicate survives into the catalogue.
    members     no governed dimension-member vocabulary, so a free-text value cannot be resolved.
    additivity  not declared, so nothing can say a distinct count must not be summed over time.

`Capabilities` states all four, and `check_compatible` refuses a study whose guardrails need them.
That is deliberate: a guardrail quietly passing because this engine returned a default would look
like a clean run and would be measuring nothing.

NO DBT. MetricFlow is normally reached through a dbt project and a compiled manifest. None of it is
needed — the engine ships its own YAML parser and a DuckDB renderer. `metricflow` alone is 14
packages and pulls no dbt-core, against 51 for the dbt route.
"""

from __future__ import annotations

import threading
from pathlib import Path

from semantic.engine import Capabilities
from warehouse.config import TIME_GRAINS
from warehouse.warehouse import STAR_SCHEMA

# One time spine per database, however many layers are built concurrently.
_SPINE_LOCK = threading.Lock()

__all__ = ["MetricFlowLayer"]


class MetricFlowLayer:
    """The agent surface, served by MetricFlow.

    Deliberately the same method names as `SemanticLayer` rather than a wrapper with its own
    vocabulary: the tools call one interface, and a second set of names would be a second thing to
    keep in step.
    """

    capabilities = Capabilities(name="metricflow", catalogue=True, query=True,
                                coverage=False, segments=False, members=False, additivity=False)

    def __init__(self, con, spec_path: Path) -> None:
        """`spec_path` is a DIRECTORY of MetricFlow YAML, not a file — that is what its parser
        takes, and pointing this at a single file is the mistake worth naming here."""
        from metricflow.engine.metricflow_engine import MetricFlowEngine
        from metricflow_semantic_interfaces.parsing.dir_to_model import (
            parse_directory_of_yaml_files_to_semantic_manifest,
        )
        from metricflow_semantics.model.semantic_manifest_lookup import SemanticManifestLookup

        directory = Path(spec_path)
        if not directory.is_dir():
            raise SystemExit(f"{directory}: the metricflow engine takes a DIRECTORY of YAML "
                             "(semantic_model: / metric: documents), not a single file")
        self.con = con
        self._ensure_time_spine()
        result = parse_directory_of_yaml_files_to_semantic_manifest(str(directory))
        self._manifest = result.semantic_manifest
        self._engine = MetricFlowEngine(
            semantic_manifest_lookup=SemanticManifestLookup(self._manifest),
            sql_client=_DuckDbClient(con))
        self.metrics = {m.name: {"description": m.description} for m in self._manifest.metrics}

    def _ensure_time_spine(self) -> None:
        """One row per day over the warehouse's own range. MetricFlow joins this for any
        time-filtered query, and every question in these studies names a period.

        SCHEMA-QUALIFIED, because `main` is empty: the generated tables live in `_source` and the
        star in `_star`. This was the second copy of this statement — the other is in the study's
        own `client.py`, which is used by its standalone check script — and only that one was
        updated when the tables moved, so this failed at study load with a catalog error.

        CREATED ONCE, under a lock. Every worker thread builds its own layer and so calls this;
        concurrent `CREATE OR REPLACE VIEW` on one object raises a write-write conflict in DuckDB.
        The view is identical whoever makes it, so the first thread wins and the rest skip."""
        with _SPINE_LOCK:
            exists = self.con.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = ? AND table_name = 'mf_time_spine'", [STAR_SCHEMA],
            ).fetchone()[0]
            if exists:
                return
            self.con.execute(f'''
            CREATE OR REPLACE VIEW "{STAR_SCHEMA}".mf_time_spine AS
            SELECT CAST(d AS DATE) AS ds FROM (SELECT UNNEST(generate_series(
                (SELECT min(active_date) FROM "{STAR_SCHEMA}".agg_active_days),
                (SELECT max(active_date) FROM "{STAR_SCHEMA}".agg_active_days),
                INTERVAL 1 DAY)) AS d)
            ''')

    # -- the agent surface ---------------------------------------------------- #

    def list_metrics_text(self) -> str:
        """The catalogue, rendered from everything MetricFlow actually exposes.

        THE FIRST VERSION OF THIS METHOD WAS THE EXPERIMENT'S BIGGEST CONFOUND. It rendered names,
        descriptions and dimension names and stopped: 461 characters against the harness layer's
        5,133. Comparing the two engines then compared a rich renderer with a lazy one, and any
        difference in the agent's behaviour was as likely to be mine as MetricFlow's.

        MetricFlow offers more than that, and it is used here: dimension VALUES via
        `get_dimension_values`, and the named periods the tool actually accepts. What it genuinely
        does not have is synonyms — a metric carries one optional `label`, not a list.

        ONE THING IS DELIBERATELY WITHHELD, and it is a treatment rather than an omission. A
        MetricFlow metric's own filter is machine-readable: `real_value_moments` carries
        `where: {{ Dimension('user__is_internal') }} = false`. Rendering it would tell the agent
        who each metric counts even in the arm whose whole premise is that nothing does — the
        A/B treatment would leak and the study would measure nothing. Our own layer makes the same
        choice, hiding `default_filters` from its catalogue. Whether SHOWING it repairs the defect
        is a real and cheap question, and it deserves its own arm rather than being decided here
        by accident.
        """
        by_name = {m.name: m for m in self._engine.list_metrics()}
        ordered = [by_name[m.name] for m in self._manifest.metrics if m.name in by_name]
        lines = ["Governed metrics (call query_metric with these names):"]
        dims_seen: set = set()
        for m in ordered:
            lines.append(f"- {m.name}: {m.description or ''}".rstrip())
            if getattr(m, "label", None):
                lines.append(f"    also called: {m.label}")
            dims = sorted(d.granularity_free_dunder_name
                          for d in self._engine.simple_dimensions_for_metrics([m.name]))
            if dims:
                lines.append(f"    group_by / filter dimensions: {', '.join(dims)}")
                dims_seen.update(d for d in dims if not d.startswith("metric_time"))
            lines.append("    time-filterable (period=…) and grainable "
                         f"(time_grain={'|'.join(TIME_GRAINS)})")

        from warehouse.config import NAMED_PERIODS
        lines.append(f"\nNamed periods: {', '.join(NAMED_PERIODS)} "
                     "(or pass explicit start/end 'YYYY-MM-DD').")

        # Dimension values, which MetricFlow can enumerate and the first renderer threw away.
        # Time dimensions are skipped: their domain is every date, which is noise rather than a
        # governed vocabulary.
        values = []
        for d in sorted(dims_seen):
            if d.endswith("_date") or d.endswith("__ds"):
                continue
            try:
                got = self._engine.get_dimension_values(
                    metric_names=[ordered[0].name], get_group_by_values=d)
            except Exception:
                continue
            if got:
                values.append(f"- {d}: {', '.join(sorted(str(v) for v in got))}")
        if values:
            lines.append("\nGoverned dimension values (any other value is refused, "
                         "not approximated):")
            lines += values

        # DIMENSION DESCRIPTIONS, which the first two versions of this renderer dropped.
        # That was not a cosmetic omission: the C arm's ENTIRE repair is a description on
        # `is_internal` saying what filtering it selects, and dropping it left that arm running as
        # "the absent arm with the twin deleted" — no repair at all, and three runs interpreted as
        # if there were one. The engine's `Dimension` object does not carry a description; the
        # manifest does, so it is read from there.
        described = []
        for sm in self._manifest.semantic_models:
            entity = next((e.name for e in sm.entities), None)
            for d in sm.dimensions:
                if d.description:
                    name = f"{entity}__{d.name}" if entity else d.name
                    described.append(f"- {name}: {' '.join(d.description.split())}")
        if described:
            lines.append("\nWhat the dimensions mean:")
            lines += described
        return "\n".join(lines)

    def query_with_sql(self, name: str, **kw) -> tuple:
        """The governed data path.

        NAMED PERIODS ARE TRANSLATED HERE, and the first version of this method did not do it —
        the tool passes `period="last_week"`, MetricFlow knows nothing of that vocabulary, and the
        window was silently dropped. The result was an all-time figure returned under a scope line
        that said `period=last_week`: a plausible number for the wrong window, with nothing
        anywhere to catch it. That is the exact defect class this project studies, produced by the
        adapter meant to study it.
        """
        import datetime as dt

        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

        from warehouse.config import resolve_period

        start, end = kw.get("start"), kw.get("end")
        if kw.get("period"):
            start, end = resolve_period(kw["period"])
        to_dt = lambda d: (None if d is None else                       # noqa: E731
                           dt.datetime.combine(d, dt.time()) if isinstance(d, dt.date)
                           and not isinstance(d, dt.datetime)
                           else d if isinstance(d, dt.datetime) else dt.datetime.fromisoformat(str(d)))

        where = kw.get("where")
        if not where and kw.get("filters"):
            # The catalogue shows dimensions already entity-qualified (`user__is_internal`), so
            # the model passes them that way. Prefixing unconditionally produced
            # `user__user__is_internal` and MetricFlow rejected it — qualify only what is bare.
            def _qualified(col: str) -> str:
                return col if "__" in col else f"user__{col}"

            def _literal(val) -> str:
                return str(val).lower() if isinstance(val, bool) else repr(val)

            def _predicate(col: str, val) -> str:
                """One comparison. A LIST becomes IN (...), not `= [...]`.

                The harness engine has always accepted a list for a filter value, so the model
                passes one, and the catalogue's governed member lists invite it. This built
                `= ['android', 'ios', 'web', 'unknown']`, which DuckDB rejects with a cast error
                against a scalar column and which killed the whole run rather than one question."""
                dim = f"{{{{ Dimension('{_qualified(col)}') }}}}"
                if isinstance(val, (list, tuple, set)):
                    members = ", ".join(_literal(v) for v in val)
                    return f"{dim} IN ({members})"
                return f"{dim} = {_literal(val)}"

            where = " AND ".join(_predicate(col, val) for col, val in kw["filters"].items())
        request = MetricFlowQueryRequest.create(
            metric_names=[name],
            where_constraints=[where] if where else None,
            group_by_names=kw.get("group_by") or None,
            time_constraint_start=to_dt(start), time_constraint_end=to_dt(end))
        sql = self._engine.explain(request).sql_statement.sql
        table = self._engine.query(request).result_df
        # THE MEASURE COLUMN MUST BE CALLED `value`. That is the harness's contract — the AFTER
        # guardrails read the measure by that name and fail CLOSED when it is absent, so an
        # unaliased result does not produce a wrong answer, it produces a refusal saying nothing
        # governed was fetched. MetricFlow names the column after the metric, so it is renamed
        # here; grouping columns keep their own names, which is what labels a row.
        columns = ["value" if c == name else c for c in table.column_names]
        rows = [tuple(table.get_cell_value(r, c) for c in range(table.column_count))
                for r in range(table.row_count)]
        return sql, columns, rows

    def metric_exists(self, term: str) -> tuple:
        hit = term in self.metrics
        return hit, ("a governed metric" if hit else
                     f"no governed metric named {term!r}; available: "
                     + ", ".join(sorted(self.metrics)))

    def in_coverage(self, start=None, end=None, region=None, country=None) -> tuple:
        """Refused rather than answered. This engine has no coverage window, and a cheerful True
        would be a guardrail passing on a fact nobody established."""
        raise NotImplementedError(
            "the metricflow engine declares coverage=False; `check_compatible` should have "
            "refused this study before it ran")

    def scope_line(self, name, filters=None, period=None, start=None, end=None,
                   group_by=None, resolve=True) -> str:
        """What a result actually covers, in one line.

        Implemented rather than declared missing, because transparency is the guardrail that shows
        the model what it computed — and MetricFlow knows the answer perfectly well. Values are NOT
        resolved against a governed vocabulary, because this engine has none; the filter is echoed
        as written, which is the truthful thing for a layer with no member list.
        """
        when = (f"period={period}" if period
                else f"window {start or '…'}..{end or '…'}" if (start or end) else "all time")
        parts = [f"[scope] {name} over {when}"]
        if filters:
            parts.append("filters " + ", ".join(f"{k}={v}" for k, v in filters.items())
                         + " (echoed as written — this layer declares no governed members)")
        else:
            parts.append("no filters — the whole population this metric defines")
        if group_by:
            parts.append("grouped by " + ", ".join(group_by))
        return "; ".join(parts)

    def segment_names(self) -> list:
        """None, truthfully. MetricFlow expresses a population as a filter over a dimension, so
        there is no named segment to offer — and an empty list is exactly right: the tool schema
        then offers no `segment` argument at all, which is the honest surface for this engine."""
        return []

    def allowed_filters(self, metric: str) -> set:
        """The dimensions this metric can be filtered by — MetricFlow's answer to the same
        question our layer answers with `allowed_filters`."""
        dims = self._engine.simple_dimensions_for_metrics([metric])
        return {d.granularity_free_dunder_name for d in dims}

    def segment_defined(self, term: str) -> tuple:
        """Always false, and truthfully so: MetricFlow has no named segments, so no term is one."""
        return False, ("this layer declares no named segments — a population is expressed as a "
                       "filter over a dimension, so name the dimension and the value instead")


class _DuckDbClient:
    """MetricFlow's SqlClient protocol: four methods and two properties, over the connection the
    harness already opened. Kept private because nothing outside this module should need it."""

    def __init__(self, con) -> None:
        self._con = con

    @property
    def sql_engine_type(self):
        from metricflow.protocols.sql_client import SqlEngine
        return SqlEngine.DUCKDB

    @property
    def sql_plan_renderer(self):
        from metricflow.sql.render.duckdb_renderer import DuckDbSqlPlanRenderer
        return DuckDbSqlPlanRenderer()

    def query(self, stmt: str, sql_bind_parameter_set=None):
        from metricflow.data_table.mf_table import MetricFlowDataTable
        cur = self._con.execute(stmt)
        return MetricFlowDataTable.create_from_rows(
            column_names=[d[0] for d in cur.description], rows=cur.fetchall())

    def execute(self, stmt: str, sql_bind_parameter_set=None) -> None:
        self._con.execute(stmt)

    def dry_run(self, stmt: str, sql_bind_parameter_set=None) -> None:
        self._con.execute(f"EXPLAIN {stmt}")

    def render_bind_parameter_key(self, bind_parameter_key: str) -> str:
        return f"${bind_parameter_key}"
