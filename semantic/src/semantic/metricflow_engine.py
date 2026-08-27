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
from semantic.semantic import SemanticError
from warehouse.config import TIME_GRAINS
from warehouse.warehouse import STAR_SCHEMA

# One time spine per database, however many layers are built concurrently.
_SPINE_LOCK = threading.Lock()

__all__ = ["MetricFlowLayer"]


def _as_date(value):
    """A date from whatever the caller or DuckDB handed over — a `date`, a `datetime`, a string.
    None for anything unparseable, so a bad argument reads as "no bound" rather than raising."""
    import datetime as _dt
    if value is None or isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.datetime):
        return value.date()
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _by_entity(dims: list[str]) -> list[tuple[str, list[str]]]:
    """Dimension names grouped by the entity prefix MetricFlow gives them.

    `user__country` belongs to the `user` entity; `habit__category` to `habit`; `metric_time` to
    neither and is its own group. The metric's OWN entity is not distinguishable from a joined one
    by name alone, so the order is stable rather than meaningful: entities alphabetically, time
    last. What the grouping buys is that a reader can see there are several sources, which a single
    sorted line does not show."""
    groups: dict = {}
    for d in dims:
        prefix = "metric_time" if d.startswith("metric_time") else d.split("__", 1)[0]
        groups.setdefault(prefix, []).append(d)
    ordered = sorted(k for k in groups if k != "metric_time")
    return [(k, sorted(groups[k])) for k in ordered] + (
        [("metric_time", sorted(groups["metric_time"]))] if "metric_time" in groups else [])


class MetricFlowLayer:
    """The agent surface, served by MetricFlow.

    Deliberately the same method names as `SemanticLayer` rather than a wrapper with its own
    vocabulary: the tools call one interface, and a second set of names would be a second thing to
    keep in step.
    """

    # COVERAGE IS COMPUTED, NOT DECLARED, and that is the whole reason it can be True here.
    # MetricFlow's spec has no field for "what period does this hold data for" — but every semantic
    # model names an `agg_time_dimension`, and the window is min/max of that column. A layer that
    # knows which column carries time knows what it covers; it simply never says so.
    #
    # `segments` and `members` stay False because no computation recovers them: a governed segment
    # and a governed member vocabulary are decisions somebody has to write down, and MetricFlow
    # provides nowhere to write them. `additivity` likewise.
    capabilities = Capabilities(name="metricflow", catalogue=True, query=True,
                                coverage=True, segments=False, members=False, additivity=False)

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
        # HOW THE CATALOGUE IS LAID OUT. Read at render time, so a study selects an arm by setting
        # it on the layer rather than by threading a parameter through build_grounding.
        #
        #   "full"     every metric followed by its own dimensions, grains and time note. Five
        #              lines of machinery between one description and the next.
        #   "compact"  the same facts, reordered: every name and description contiguous first,
        #              the per-metric machinery in a second block below.
        #
        # This exists because two metrics that answer one question are five lines apart in "full",
        # and an agent that picks by name rather than by description might simply never be holding
        # the two descriptions at once. Same tokens, same facts, different adjacency — so a
        # difference between the arms is layout and nothing else.
        self.catalogue = "full"
        # The ambiguity index, when one sits beside the definitions. Loaded here rather than by the
        # guardrail so the index travels with the layer it describes and the engine never learns
        # which tool produced it. None means no file — which a guardrail that needs one must treat
        # as an error, not as "nothing competes".
        from .clusters import load as _load_clusters
        self.clusters = _load_clusters(directory)
        self._windows: dict[str, tuple] = {}   # semantic model -> (first date, last date), lazily read

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

    def _own_entity(self, metric) -> str | None:
        """The entity of the semantic model this metric's measure lives on.

        A metric's dimensions arrive from two places — its own model, and every model reachable by a
        shared entity — and MetricFlow prefixes both identically. Which is which is the difference
        between `habit__category`, an attribute of the rows being counted, and `user__platform`, an
        attribute of something joined to them. The catalogue could not say."""
        params = getattr(metric, "type_params", None)
        agg = getattr(params, "metric_aggregation_params", None) if params else None
        model_name = getattr(agg, "semantic_model", None) if agg else None
        if not model_name:
            return None
        for sm in self._manifest.semantic_models:
            if sm.name == model_name:
                primary = next((e.name for e in sm.entities if str(e.type).lower().endswith("primary")), None)
                return primary
        return None

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
        # In "compact" the headline lines are emitted together first and the machinery is
        # accumulated for a second block; in "full" both go out interleaved, as they always have.
        compact = self.catalogue == "compact"
        detail: list = []
        if compact:
            for m in ordered:
                lines.append(f"- {m.name}: {m.description or ''}".rstrip())
                if getattr(m, "label", None):
                    lines.append(f"    also called: {m.label}")
            detail.append("\nWhat each metric can be broken down by:")
        for m in ordered:
            block = detail if compact else lines
            if compact:
                block.append(f"- {m.name}")
            else:
                lines.append(f"- {m.name}: {m.description or ''}".rstrip())
                if getattr(m, "label", None):
                    lines.append(f"    also called: {m.label}")
            dims = sorted(d.granularity_free_dunder_name
                          for d in self._engine.simple_dimensions_for_metrics([m.name]))
            if dims:
                # GROUPED BY THE ENTITY THEY BELONG TO, not printed as one sorted list.
                #
                # A flat line hides the join graph. `people_with_habits` offers ten dimensions and
                # nine of them arrive across a join from `users`; the tenth, `habit__category`, is
                # the metric's own. Run 20260809-2216 shows the arm dropping exactly that one, four
                # times, while keeping the `user__` filters — the shape of a list where everything
                # looks alike.
                #
                # Cube groups dimensions by cube, LookML by view, and MetricFlow's own CLI by
                # entity. Ours printed them sorted, so `habit__category` sat between
                # `habit__is_archived` and `metric_time` with nothing to say it was the subject of
                # the metric rather than an attribute of something joined to it.
                # THE METRIC'S OWN ENTITY IS MARKED, not just grouped. Grouping alone cut the
                # dropped-filter failures from four to one per run and did not remove them, and the
                # dropped filter is ALWAYS the metric's own — `habit__category` goes while
                # `user__platform` stays. A positional list says there are two sources; it does not
                # say which one is the thing being counted.
                own = self._own_entity(m)
                for prefix, group in _by_entity(dims):
                    if prefix == "metric_time":
                        label = "time"
                    elif prefix == own:
                        label = f"by {prefix} (what this metric counts)"
                    else:
                        label = f"by {prefix} (joined)"
                    block.append(f"    {label}: {', '.join(group)}")
                dims_seen.update(d for d in dims if not d.startswith("metric_time"))
            block.append("    time-filterable (period=…) and grainable "
                         f"(time_grain={'|'.join(TIME_GRAINS)})")
        lines += detail

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
        # A NAMED PERIOD AND EXPLICIT DATES ARE A CONFLICT, NOT A PRECEDENCE. Both engines used to
        # let `period` win and drop the caller's start/end without a word. Run 20260810-000736 shows
        # what that costs: asked for accounts created in June, the agent sent
        # `period="all"` alongside `start=2026-06-01, end=2026-06-30` and was handed 2,500 — the
        # all-time figure — under a scope line that named the window it did not use. Two of three
        # repetitions of a CONTROL failed that way.
        #
        # That is this project's own subject matter: a plausible number for the wrong window,
        # produced by the layer rather than by the model. Refusing the call makes the mistake
        # unrepresentable instead of detectable, and the agent recovers — it reissues with one of
        # the two.
        if kw.get("period") and (start or end):
            raise SemanticError(
                f"period={kw['period']!r} was given together with start/end. Use one: a named "
                f"period, or an explicit start and end.")
        if kw.get("period"):
            # `resolve_period` raises ValueError on a name it does not know, and `dispatch` catches
            # SemanticError. semantic.py already translates it; this adapter did not, so an agent
            # passing `period="2026-06-01/2026-06-30"` — a date range where a NAME belongs — killed
            # the whole run instead of getting a recoverable error naming the six valid periods.
            # Same boundary rule as the MetricFlow exceptions below: a foreign error type stops here.
            try:
                start, end = resolve_period(kw["period"])
            except ValueError as exc:
                raise SemanticError(str(exc)) from exc
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
        # METRICFLOW'S OWN EXCEPTIONS STOP HERE. `dispatch` catches SemanticError and hands the
        # agent a recoverable tool error; an exception type it does not know propagates out of the
        # worker and kills the whole run. That is what happened on the first MetricFlow run of
        # 00_primitive_load: the agent guessed a metric name, MetricFlow raised
        # InvalidQueryException, and 23 questions were lost to one bad guess.
        #
        # Translating at the boundary is the adapter's job — every caller already handles
        # SemanticError, and a second exception type would have to be handled in each of them.
        try:
            sql = self._engine.explain(request).sql_statement.sql
            table = self._engine.query(request).result_df
        except Exception as exc:            # noqa: BLE001 — the foreign boundary is the point
            first = str(exc).strip().splitlines()
            detail = " ".join(x.strip() for x in first if x.strip())[:400]
            raise SemanticError(detail or f"{type(exc).__name__}") from exc
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

    # -- coverage: what period this layer actually holds ---------------------- #
    #
    # WHY THIS EXISTS. `E_enforced` answered both out-of-coverage questions wrong, three times each,
    # and `coverage_check` — the guardrail written to catch exactly that, emitting exactly the
    # `out_of_coverage` code the items expect — could not run, because this engine declared no
    # coverage. The agent was left to notice on its own that August 2026 is not in the warehouse,
    # and it did not. See FINDINGS.md §28.
    #
    # THE WINDOW IS PER MODEL, not per layer, and the difference is real in our own warehouse:
    # habits run to 2026-07-24 while subscriptions stop at 2026-07-12. A single layer-wide window
    # would either refuse answerable habit questions or admit unanswerable subscription ones.

    def _model_of(self, metric: str):
        """The semantic model a metric's numbers come from.

        A ratio or derived metric has no model of its own — it is built from others — so the search
        follows its inputs and takes the first that lands. Two inputs on different models would make
        the window ambiguous; the narrower one is taken in `_window_for`, because a figure is only
        as covered as its least-covered part."""
        by_name = {m.name: m for m in self._manifest.metrics}
        seen, stack, models = set(), [metric], []
        while stack:
            name = stack.pop()
            if name in seen or name not in by_name:
                continue
            seen.add(name)
            m = by_name[name]
            params = getattr(m, "type_params", None)
            agg = getattr(params, "metric_aggregation_params", None) if params else None
            own = getattr(agg, "semantic_model", None) if agg else None
            if own:
                models.append(own)
            for field in ("numerator", "denominator"):
                inp = getattr(params, field, None) if params else None
                if inp is not None:
                    stack.append(getattr(inp, "name", inp))
            for inp in (getattr(params, "metrics", None) or ()) if params else ():
                stack.append(getattr(inp, "name", inp))
        return [sm for sm in self._manifest.semantic_models if sm.name in models]

    def _window_of(self, sm) -> tuple:
        """(first, last) dates held by one semantic model, read from the table itself."""
        key = sm.name
        if key not in self._windows:
            time_dim = next((d for d in sm.dimensions if str(d.type).lower().endswith("time")), None)
            if time_dim is None:
                self._windows[key] = (None, None)
            else:
                expr = time_dim.expr or time_dim.name
                rel = sm.node_relation
                lo, hi = self.con.execute(
                    f"SELECT min({expr}), max({expr}) FROM {rel.schema_name}.{rel.alias}").fetchone()
                self._windows[key] = (_as_date(lo), _as_date(hi))
        return self._windows[key]

    def coverage_window(self, metric: str | None = None) -> tuple:
        """The period this layer can answer for — narrowed to one metric when one is named.

        With no metric the answer spans every model, which is the honest reply to "does this layer
        hold August 2026 at all". Narrowest-common is used within a metric so a composed figure is
        never reported as more covered than the data behind it."""
        models = self._model_of(metric) if metric else list(self._manifest.semantic_models)
        wins = [w for w in (self._window_of(sm) for sm in models) if w[0] and w[1]]
        if not wins:
            return (None, None)
        if metric:
            return (max(w[0] for w in wins), min(w[1] for w in wins))
        return (min(w[0] for w in wins), max(w[1] for w in wins))

    def in_coverage(self, start=None, end=None, region=None, country=None) -> tuple:
        """Is the whole period inside the data window? A partial overlap is a NO, matching the
        harness engine: a clipped answer over a window the asker did not ask for is the failure the
        check exists to prevent.

        `region` and `country` are accepted and NOT applied. This layer has no governed member
        vocabulary, so it has no per-region launch windows to check against — and saying so is
        better than resolving them silently against nothing."""
        lo, hi = self.coverage_window()
        s, e = _as_date(start), _as_date(end)
        if s is None and e is None:
            return False, "no period given; pass start (and end)."
        s, e = (s or e), (e or s)
        scope = (f" (this layer has no governed regions, so {region or country!r} was not applied)"
                 if (region or country) else "")
        if lo and s < lo:
            return False, f"period begins {s}, before data starts {lo}.{scope}"
        if hi and e > hi:
            return False, f"period ends {e}, after data ends {hi}.{scope}"
        return True, f"period {s}..{e} within coverage ({lo}..{hi}).{scope}"

    # Kimball's three classes, keyed on the aggregate, exactly as `SemanticLayer.additivity` reads
    # them. MetricFlow names its aggregates differently and means the same things.
    _ADDITIVE = {"sum", "count", "sum_boolean"}
    _SEMI_ADDITIVE = {"count_distinct"}

    def additivity(self, metric: str) -> str:
        """Whether this metric may be rolled up over time: additive / semi_additive / non_additive.

        DERIVED FROM THE AGGREGATE, not annotated — a `count_distinct` double-counts anyone present
        in two periods whether or not somebody wrote that down, and a ratio is meaningless added in
        any direction. A metric built from other metrics is non-additive: its inputs may each be
        summable and their combination is not.

        NEEDED BY `governed_numbers`, which is not what `GUARDRAIL_NEEDS` says. That table declares
        only `output_validation` as needing additivity, so this engine was cleared to run
        `governed_numbers` and then reached `_additive_total`, which calls this method — a second
        capability-versus-method gap after `scope_members`, and it cost a second paid run. The
        capability flag stays False because it gates `output_validation`, which needs unit and
        bounds metadata this layer genuinely lacks; the two questions were conflated under one
        name."""
        by_name = {m.name: m for m in self._manifest.metrics}
        m = by_name.get(metric)
        if m is None:
            return "non_additive"                  # unknown: never license a sum
        params = getattr(m, "type_params", None)
        measure = getattr(params, "measure", None) if params else None
        name = getattr(measure, "name", None) if measure is not None else None
        if not name:
            return "non_additive"                  # ratio or derived — built from others
        for sm in self._manifest.semantic_models:
            for meas in sm.measures:
                if meas.name != name:
                    continue
                # `non_additive_dimension` OVERRIDES THE AGGREGATE, and it has to. A periodic
                # snapshot's balance is declared `agg: sum` because it IS summed across customers
                # inside a month; what it may not do is sum across the snapshot date. Reading the
                # aggregate alone reported `mrr` as additive, which is the opposite of what the
                # model says one line below it.
                if getattr(meas, "non_additive_dimension", None) is not None:
                    return "semi_additive"
                agg = str(getattr(meas, "agg", "")).lower().rsplit(".", 1)[-1]
                if agg in self._ADDITIVE:
                    return "additive"
                return "semi_additive" if agg in self._SEMI_ADDITIVE else "non_additive"
        return "non_additive"

    # -- what `trajectory_verify` needs ---------------------------------------- #
    #
    # The judge recompiles the SQL the analyst ran and reads the filters it added on top of the
    # metric's own. All three methods below were on `_UNREACHABLE_ON_METRICFLOW` in
    # tests/test_adapters.py, annotated "only runs under trajectory_verify" — and then the guardrail
    # was switched on, which is the allow-list working as a to-do list rather than as an excuse.

    def compile(self, name, group_by=None, filters=None, time_grain=None,
                start=None, end=None, period=None, resolve=True, segment=None) -> str:
        """The SQL this metric call renders to. MetricFlow builds it as part of answering, so the
        query is planned and the statement returned; the judge reads it rather than runs it.

        `resolve` and `segment` are accepted and ignored: both need a governed member vocabulary
        this engine does not have, which is why `resolve` is refused by `check_compatible`."""
        sql, _cols, _rows = self.query_with_sql(
            name, group_by=group_by, filters=filters, time_grain=time_grain,
            start=start, end=end, period=period)
        return sql

    def redundant_filters(self, metric: str | None, filters: dict | None) -> dict:
        """Analyst filters that merely restate the metric's own definition — always empty here.

        The harness engine can answer this because a segment is a named, reusable object it can
        compare against. A MetricFlow filter is an expression over a dimension, so deciding whether
        `is_active = true` restates `subscribers_live` would mean parsing the metric's predicate and
        the analyst's and proving them equivalent. Returning nothing is the truthful answer: this
        layer cannot tell, and a wrong claim of redundancy would tell the judge to ignore a filter
        that genuinely narrowed the population."""
        return {}

    def available_from(self, dimension: str, member) -> object | None:
        """When a governed member's data begins — always None. The window lives on a dimension
        member, and this engine has no member vocabulary to hang one on. Distinct from the layer's
        COVERAGE, which is computed per model above and is a different fact."""
        return None

    def scope_members(self, filters=None, group_by=None) -> list[tuple]:
        """The coverage-bearing (dimension, member) pairs this call reports on — always empty here.

        A member carries coverage when governance records when its data begins (APAC launched in
        March). That is a written-down fact, and MetricFlow has nowhere to write it, so no filter
        value in this layer bears a window. The period check in `coverage_violations` is the whole
        of this engine's coverage.

        IMPLEMENTED RATHER THAN OMITTED because `check_compatible` guards CAPABILITIES, not
        METHODS: `coverage_check` declares it needs `coverage`, this engine now has it, and the
        guardrail was cleared to run — then called `scope_members` on the success path and killed
        the run with an AttributeError. Capability-compatible is not the same as method-complete."""
        return []

    def coverage_violations(self, filters=None, group_by=None, start=None, end=None,
                            period=None, metric=None) -> list[tuple]:
        """Which scopes this call reports on fall outside coverage: [(dimension, member, why)].

        Only the PERIOD is checkable here. The harness engine also walks the coverage-bearing
        members named in `filters`/`group_by`, and this layer has none — so a call is checked
        against the data window of the metric it asks for, and nothing else."""
        from warehouse.config import resolve_period
        if period and (start or end):
            return [(None, None, f"period={period!r} was given together with start/end. Use one.")]
        if period:
            try:
                start, end = resolve_period(period)
            except ValueError:
                # NOT A COVERAGE VIOLATION. An unresolvable period name is a bad argument, and
                # reporting it here would refuse the call with `out_of_coverage` — teaching the
                # agent that the data does not reach a window it never actually named. The query
                # path already raises the accurate error, so this check stands down.
                return []
        if start is None and end is None:
            return []                     # an all-time call asks for exactly what is there
        lo, hi = self.coverage_window(metric)
        s, e = _as_date(start), _as_date(end)
        s, e = (s or e), (e or s)
        named = f" for {metric!r}" if metric else ""
        if lo and s < lo:
            return [(None, None, f"the period begins {s}, before data starts {lo}{named}.")]
        if hi and e > hi:
            return [(None, None, f"the period ends {e}, after data ends {hi}{named}.")]
        return []

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
