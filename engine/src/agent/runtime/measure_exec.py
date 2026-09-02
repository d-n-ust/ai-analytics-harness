"""Executing a measure Spec — the IMPERATIVE SHELL of the spec pipeline.

Everything in `measure.py` is a pure function of plain data; the one place that touches the warehouse
lives here, isolated on purpose. `run_ephemeral` computes the value a GROUNDED spec defines and
returns it with the SQL / definition that produced it — so the number is disclosed with its basis and
the run is reproducible from the trace.

Verification-as-construction: the number is PRODUCED BY the spec (a governed metric's compiled SQL, a
composition of its inputs, or the raw SQL itself), so it cannot drift from the definition — there is
no separate "does the number match the spec" check to get wrong. Ground and coherence-check a spec
(measure.py) BEFORE running it here; this shell assumes a spec that already passed those.
"""
from __future__ import annotations

from dataclasses import dataclass

# The binary compositions a derived spec can be — the same registry the contest check uses, kept here
# so the executor composes without importing the loop.
_COMPOSE = {
    "ratio": lambda a, b: (a / b) if b else None,
    "difference": lambda a, b: a - b,
    "sum": lambda a, b: a + b,
    "product": lambda a, b: a * b,
}


@dataclass(frozen=True)
class Result:
    """What running a spec produced: the value(s), and the artifact that produced them.

    `value` is the scalar when the spec resolves to one (a metric total, a composition), else None;
    `rows`/`columns` carry a grouped or multi-row result (a raw model, a per-segment breakdown).
    `sql` and `definition` are the disclosable basis — the compiled SQL, the composition expression,
    or the raw statement — recorded on the trace so the answer can show how the number was computed."""

    value: float | None
    rows: tuple = ()
    columns: tuple = ()
    sql: str = ""
    definition: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def _scalar(keyed) -> float | None:
    """The single number from a value_of result ({label: value}), or None if it is not one row."""
    if isinstance(keyed, dict) and len(keyed) == 1:
        (v,) = keyed.values()
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return None


def run_ephemeral(spec, engine) -> Result:
    """Compute the value the grounded spec defines. The only I/O in the measure pipeline; returns a
    Result carrying the value (or rows) AND the SQL/definition that produced it. On any execution
    failure returns a Result with `error` set — a fact to surface, never a number to trust."""
    from ..guardrails import before

    if spec.kind == "metric":
        args = {"filters": dict(spec.filters) or None, "period": spec.period or None}
        try:
            keyed = before.value_of(engine, args, spec.metric)
        except Exception as exc:                                            # noqa: BLE001
            return Result(value=None, error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
        if keyed is None:
            return Result(value=None, error=f"metric {spec.metric!r} returned nothing for {args}")
        defn = f"governed metric {spec.metric}" + (f" filtered {dict(spec.filters)}" if spec.filters else "")
        return Result(value=_scalar(keyed),
                      rows=tuple(keyed.items()), columns=("label", "value"),
                      sql=f"query_metric({spec.metric}, {args})", definition=defn)

    if spec.kind == "derived":
        op = _COMPOSE.get(spec.op)
        if op is None:
            return Result(value=None, error=f"unknown derived op {spec.op!r}")
        parts, defs = [], []
        for sub in spec.inputs:
            r = run_ephemeral(sub, engine)
            if not r.ok or r.value is None:
                return Result(value=None, error=f"derived input failed: {r.error or 'no scalar value'}")
            parts.append(r.value)
            defs.append(r.definition)
        val = parts[0]
        for p in parts[1:]:
            val = op(val, p)
            if val is None:
                return Result(value=None, error=f"{spec.op} undefined (division by zero?)")
        return Result(value=round(val, 6),
                      sql=f" {spec.op} ".join(defs),
                      definition=f"{spec.op} of [{', '.join(defs)}]")

    if spec.kind == "raw":
        # Agent-authored SQL runs through the SAME guarded runner the agent's run_sql uses —
        # read-only enforced by the DuckDB PARSER (SELECT/WITH only; INSERT/UPDATE/DELETE/CREATE/COPY/
        # ATTACH blocked even behind a comment or CTE), single-statement, and scoped to the arm's
        # schema — never a bare con.execute of whatever the model wrote. This is the sandbox the raw
        # tier needs: a definition can read, never mutate.
        from warehouse import run_query
        try:
            cols, rows = run_query(engine.con, spec.sql, schema=getattr(engine, "schema", None))
            cols, rows = tuple(cols), tuple(rows)
        except Exception as exc:                                            # noqa: BLE001
            return Result(value=None, error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
        # A single-cell result is a scalar; anything wider/taller is a grouped result the caller reads.
        val = rows[0][0] if len(rows) == 1 and len(cols) == 1 and isinstance(
            rows[0][0], (int, float)) and not isinstance(rows[0][0], bool) else None
        return Result(value=val, rows=rows, columns=cols, sql=spec.sql,
                      definition=spec.definition or "raw SQL")

    if spec.kind == "query":
        # Executing an ad-hoc query leaf needs the entity->table mapping and SQL generation; deferred
        # to the next step. Named rather than silently mis-run.
        return Result(value=None, error="query-leaf execution not yet implemented")

    return Result(value=None, error=f"unknown spec kind {spec.kind!r}")
