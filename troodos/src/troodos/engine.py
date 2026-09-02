"""The seam between troodos and the research harness.

**This is the only module in troodos that imports harness code.** Everything else calls
`build_engine()` and `ask()`. That is the whole point: when the agent, guardrails and semantic
compiler are eventually vendored into `troodos/`, this file changes and nothing else does.

Keeping the quarantine is worth more than it looks, because the two codebases disagree about
three things and this module is where the disagreements are absorbed:

`rung` — the harness threads an experiment ordinal (1-6, how much grounding the agent was given)
through its toolbox, its action space and its prompt assembly. A product has no ladder; it has
whatever grounding the user actually has. So `Capabilities` below names the grounding directly
and translates to an ordinal at the last moment.

The data interface — the harness's `Toolbox` takes a live DuckDB connection handle, not an
abstraction. troodos's whole connection layer exists so the engine never sees a driver. The two
cannot both be right, so this module reaches through `DuckDBWarehouse` for its raw handle, in the
one place where that is allowed and visible.

The clock — the harness pins "today" to 2026-07-16 so its gold answers never drift. A product
must use the real date. Until the semantic layer is vendored, any named period ("last week")
resolves against the harness's frozen date, so `build_engine` refuses to guess and callers are
told to pass explicit dates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path

from .warehouse.base import Warehouse, WarehouseError
from .warehouse.duckdb import DuckDBWarehouse


class EngineError(Exception):
    """The engine could not be assembled. Distinct from a warehouse or model failure: this means
    the configuration itself does not describe a runnable analyst."""


# The grounding a deployment actually has, named for what it is rather than by ladder position.
# The harness's rungs are a total order because an experiment needed one; a real warehouse either
# has a semantic layer or does not, independently of whether it has a metric tree.
@dataclass(frozen=True)
class Capabilities:
    """What the agent is given, and what it may do.

    Replaces the harness's `rung` ordinal. The translation to one happens in `_rung()`, at the
    boundary, so no product code above this module ever names a rung.
    """

    semantic_layer: bool = True
    metric_tree: bool = False

    # Whether the agent may author SQL itself, rather than only calling governed metrics.
    #
    # This is the single source of truth for that choice. The harness expresses the same thing
    # inverted, as a `tool_restriction` guardrail, and carrying both would let them disagree —
    # a configuration claiming governed-only while raw SQL is on the table is precisely the
    # class of silent inconsistency this product exists to refuse. `build_engine` derives the
    # guardrail from this field, so there is nothing to keep in step.
    #
    # Off by default, and that default is the product. Governed-only means the model never writes
    # SQL at all: the semantic compiler does, from definitions a human approved. That is a
    # stronger guarantee than any check applied to model-authored SQL after the fact, because
    # there is no model-authored SQL to check.
    raw_sql: bool = False

    def _rung(self) -> int:
        """Map to the harness's ordinal.

        Lossy on purpose, and only in the safe direction: the harness's rungs 4 and 5 add
        verified examples and a prose knowledge base, which are properties of *its* fixture set
        rather than of a user's warehouse. Requesting the metric tree therefore lands on rung 6,
        which includes them — the agent is given more context, never less than it is told it has.
        """
        if self.metric_tree:
            return 6
        if self.semantic_layer:
            return 3
        return 2


@dataclass(frozen=True)
class Guardrails:
    """Which enforcement is switched on.

    Mirrors the harness's `GuardrailSet` field for field, but restated here so that product code
    never imports it. `trajectory_verify` defaults to OFF and that is a deliberate, load-bearing
    default: it is the only guardrail whose verdict is a probability rather than a proof, it
    fires on roughly half of all answers, and it transmits the compiled SQL, the query result and
    the causal record to an external model. Shipping it on by default would make "your data stays
    in your warehouse" false in the product's own crown-jewel component. It goes on per
    deployment, after it has been scored against that deployment's own labelled answers.
    """

    abstain: bool = True
    check_tools: bool = True
    coverage_check: bool = True
    resolve: bool = True
    transparency: bool = True
    governed_numbers: bool = True
    output_validation: bool = True
    trajectory_verify: bool = False

    # Deliberately absent: `tool_restriction`. It is the inverse of `Capabilities.raw_sql`, and
    # `build_engine` derives it from there. Two fields for one decision is two fields that can
    # disagree.

    def _coerce(self, caps: Capabilities) -> tuple[Guardrails, list[str]]:
        """Return the strongest coherent guardrail set for these capabilities, plus a plain-English
        account of anything that had to be switched off.

        The guardrails are not independent switches; they form a dependency lattice, and the
        harness refuses to assemble an incoherent combination rather than running one that
        silently means something else:

            governed_numbers   needs governed-only queries — it reads result values that only a
                               governed call records, so with raw SQL on, every answer would
                               auto-refuse
            output_validation  needs governed_numbers — the `value` and `source_metric` fields it
                               validates are only offered on the answer tool under it
            trajectory_verify  needs governed_numbers — it judges a metric+SQL trajectory, which a
                               hand-composed number does not have
            all of the above   need a semantic layer to act on at all

        Coercing rather than raising is the right call for a product: a user asking for raw SQL
        should get it, not a lecture about a fourth flag they also have to pass. But coercing
        SILENTLY would be indefensible — they would believe guardrails were running that are not.
        So the reasons come back with the result, and the caller is expected to show them.
        """
        disabled: list[str] = []
        g = self

        if not caps.semantic_layer:
            dropped = [n for n in ("check_tools", "coverage_check", "resolve", "transparency",
                                   "governed_numbers", "output_validation", "trajectory_verify")
                       if getattr(g, n)]
            if dropped:
                disabled.append(
                    f"no semantic layer, so {', '.join(dropped)} cannot act — there is no governed "
                    f"call for them to inspect"
                )
            return replace(g, check_tools=False, coverage_check=False, resolve=False,
                           transparency=False, governed_numbers=False, output_validation=False,
                           trajectory_verify=False), disabled

        if caps.raw_sql and g.governed_numbers:
            disabled.append(
                "governed_numbers is off: it verifies that a served number came from a governed "
                "result, and raw SQL produces numbers that record none. Left on, every raw-SQL "
                "answer would auto-refuse"
            )
            g = replace(g, governed_numbers=False)

        if not g.governed_numbers and g.output_validation:
            disabled.append(
                "output_validation is off: it checks a declared `value` and `source_metric`, and "
                "those fields are only offered on the answer tool when governed_numbers is on"
            )
            g = replace(g, output_validation=False)

        if not g.governed_numbers and g.trajectory_verify:
            disabled.append(
                "trajectory_verify is off: it judges a metric-and-SQL trajectory, which a "
                "hand-composed number does not have"
            )
            g = replace(g, trajectory_verify=False)

        return g, disabled

    def _set(self, *, raw_sql: bool):
        from agent.guardrails import GuardrailSet  # noqa: PLC0415 — quarantined by design

        return GuardrailSet(
            abstain=self.abstain,
            check_tools=self.check_tools,
            coverage_check=self.coverage_check,
            tool_restriction=not raw_sql,
            resolve=self.resolve,
            transparency=self.transparency,
            governed_numbers=self.governed_numbers,
            output_validation=self.output_validation,
            trajectory_verify=self.trajectory_verify,
        )


@dataclass
class Engine:
    """An assembled analyst: a warehouse, its grounding, and the guardrails over it."""

    warehouse: Warehouse
    grounding: object            # harness `Grounding`; opaque above this module
    capabilities: Capabilities
    guardrails: Guardrails       # the EFFECTIVE set, after coherence coercion
    # Why the effective set differs from what was asked for. Empty when nothing was coerced.
    # Callers are expected to surface this: a user who believes a guardrail is running when it
    # is not has been misled by the tool, which is the one failure this product cannot afford.
    concessions: tuple[str, ...] = ()

    def ask(self, question: str, model, *, max_iters: int = 8, verifier_model=None,
            on_event=None):
        """Answer one question. Returns the harness's `Answer` — a typed outcome, so a refusal is
        a refusal rather than a sentence that has to be grepped for one.

        `on_event(kind, name, info)` fires as work happens: `kind` is "thinking" (waiting on the
        model) or "tool" (running one). Answering takes several sequential model round trips, and
        a CLI that prints nothing for that whole time reads as hung rather than busy — the wait is
        the same either way, but only one of them is tolerable. The harness's loop has no callback,
        so the two call sites are wrapped here rather than in the loop, which also means this
        disappears cleanly when the agent is vendored and can emit events itself.
        """
        from agent.runtime.loop import run_agent  # noqa: PLC0415 — quarantined by design

        if on_event is not None:
            return self._ask_traced(question, model, max_iters, verifier_model, on_event, run_agent)

        return run_agent(
            question,
            self.grounding,
            model,
            max_iters=max_iters,
            verifier_model=verifier_model if self.guardrails.trajectory_verify else None,
        )

    def _ask_traced(self, question, model, max_iters, verifier_model, on_event, run_agent):
        """Run with the model and toolbox wrapped so progress can be reported.

        Both wrappers are restored in a `finally`. An Engine is reusable, and leaving a traced
        toolbox behind would make a later untraced `ask` emit events to a dead callback.
        """
        toolbox = self.grounding.toolbox
        real_dispatch, real_respond = toolbox.dispatch, model.respond

        def dispatch(name, args):
            on_event("tool", name, dict(args or {}))
            started = time.perf_counter()
            result = real_dispatch(name, args)
            # The renderer is handed the arguments and the whole result so it can summarise each
            # tool in its own terms — "6 tables, 1 view" rather than the first 90 characters of a
            # schema dump. Truncating here would decide, for every tool at once, something that
            # only makes sense per tool.
            on_event("tool_done", name, {
                "ok": not result.is_error,
                "ms": (time.perf_counter() - started) * 1000,
                "args": dict(args or {}),
                "content": str(result.content or ""),
                "values": result.values,
            })
            return result

        def respond(*a, **kw):
            on_event("thinking", model.spec.model_id if hasattr(model, "spec") else "model", {})
            started = time.perf_counter()
            turn = real_respond(*a, **kw)
            on_event("thinking_done", "", {"ms": (time.perf_counter() - started) * 1000})
            return turn

        toolbox.dispatch, model.respond = dispatch, respond
        try:
            return run_agent(
                question,
                self.grounding,
                model,
                max_iters=max_iters,
                verifier_model=verifier_model if self.guardrails.trajectory_verify else None,
            )
        finally:
            toolbox.dispatch, model.respond = real_dispatch, real_respond


def _schema_text(warehouse: Warehouse) -> str:
    """The schema, introspected from the live database.

    Replaces the harness's version, which builds this from a hardcoded table list selected by
    rung (`warehouse/warehouse.py`, `visible_tables`). That is correct for a fixture whose tables
    are known in advance and fatal for a product: point it at any database lacking those exact
    names and it raises a catalog error instead of describing what is actually there.

    Introspecting also earns something the hardcoded list could never carry — the `COMMENT ON`
    text. Table and column comments are the cheapest grounding available: already written,
    already reviewed, already living beside the data, and written straight into the warehouse by
    dbt's `persist_docs`. Handing them to the agent costs nothing and is often the difference
    between a column named `plat` being meaningless and being documented.
    """
    lines: list[str] = []
    for rel in warehouse.relations():
        cols = ", ".join(f"{c.name} {c.type.lower()}" for c in rel.columns)
        head = f"{rel.qualified}({cols})"
        if rel.comment:
            head += f"\n  -- {rel.comment}"
        for col in rel.columns:
            if col.comment:
                head += f"\n  -- {col.name}: {col.comment}"
        lines.append(head)
    return "\n".join(lines)


def _describe_text(warehouse: Warehouse, name: str) -> str:
    """One relation in detail, with a few sample rows."""
    match = next((r for r in warehouse.relations() if r.name == name or r.qualified == name), None)
    if match is None:
        available = ", ".join(r.qualified for r in warehouse.relations())
        return f"Error: unknown table {name!r}. Available: {available}"

    header = ", ".join(f"{c.name} ({c.type.lower()})" for c in match.columns)
    out = [match.qualified]
    if match.comment:
        out.append(match.comment)
    out.append(f"columns: {header}")
    for col in match.columns:
        if col.comment:
            out.append(f"  {col.name}: {col.comment}")
    try:
        sample = warehouse.execute(f"SELECT * FROM {match.qualified}", max_rows=3)
        out.append("sample rows:")
        out += [str(row) for row in sample.rows]
    except WarehouseError as exc:
        out.append(f"(could not sample: {exc})")
    return "\n".join(out)


def _bind_introspection(grounding, warehouse: Warehouse) -> None:
    """Serve `get_schema` and `describe_table` from the Warehouse protocol.

    Done by wrapping dispatch rather than by editing the harness, so the harness stays untouched
    and this disappears when the tools are vendored and can take a Warehouse directly.
    """
    toolbox = grounding.toolbox
    inner = toolbox.dispatch

    def dispatch(name: str, args: dict):
        from agent.core.conversation import ToolResult  # noqa: PLC0415 — quarantined by design

        if name == "get_schema":
            return ToolResult(_schema_text(warehouse))
        if name == "describe_table":
            requested = args.get("table") or args.get("name") or ""
            return ToolResult(_describe_text(warehouse, requested))
        return inner(name, args)

    toolbox.dispatch = dispatch


def _raw_connection(warehouse: Warehouse):
    """Reach through the abstraction for the driver handle the harness's Toolbox demands.

    Isolated into one function so the violation is greppable and has exactly one place to be
    deleted from. Every other line of troodos treats a warehouse as opaque; this one cannot,
    because the harness predates the abstraction.
    """
    if not isinstance(warehouse, DuckDBWarehouse):
        raise EngineError(
            f"{type(warehouse).__name__} cannot drive the harness engine yet — it needs a live "
            f"DuckDB connection. Vendoring the agent into troodos is what removes this limit."
        )
    return warehouse._con


def build_engine(
    warehouse: Warehouse,
    *,
    semantic_spec: str | Path | None = None,
    metric_tree: str | Path | None = None,
    capabilities: Capabilities | None = None,
    guardrails: Guardrails | None = None,
) -> Engine:
    """Assemble an analyst over an open warehouse.

    `semantic_spec` and `metric_tree` are paths to the governed definitions. Left unset, the
    harness's own fixture specs are used — which is right for a demo against the harness's
    synthetic warehouse and wrong for anything else, so callers pointing at real data must pass
    them explicitly.
    """
    from agent.runtime.grounding import build_grounding  # noqa: PLC0415 — quarantined by design
    from semantic.semantic import SemanticLayer
    from semantic.tree import MetricTree

    caps = capabilities or Capabilities()
    rails, concessions = (guardrails or Guardrails())._coerce(caps)

    if not caps.raw_sql and not caps.semantic_layer:
        raise EngineError(
            "no data path is available: raw SQL is off and there is no semantic layer, so the "
            "agent has nothing to query with. Either configure a semantic spec, or enable "
            "raw_sql to let it author SQL directly."
        )

    con = _raw_connection(warehouse)

    layer = None
    if caps.semantic_layer:
        try:
            layer = (
                SemanticLayer(con, Path(semantic_spec).expanduser())
                if semantic_spec
                else SemanticLayer(con)
            )
        except FileNotFoundError as exc:
            raise EngineError(f"semantic spec not found: {exc}") from exc

    tree = None
    if caps.metric_tree:
        if layer is None:
            raise EngineError("a metric tree describes relationships between governed metrics, "
                              "so it needs a semantic layer underneath it.")
        tree = MetricTree(layer, Path(metric_tree).expanduser()) if metric_tree else MetricTree(layer)

    try:
        grounding = build_grounding(con, caps._rung(), rails._set(raw_sql=caps.raw_sql))
    except Exception as exc:
        raise EngineError(f"could not assemble the agent: {exc}") from exc

    # build_grounding constructs its own Toolbox from the connection, so the specs built above
    # have to be attached afterwards. Reaching into it is ugly and is exactly the kind of thing
    # that disappears when the agent is vendored and its constructor can take them directly.
    if layer is not None:
        grounding.toolbox.semantic = layer
    if tree is not None:
        grounding.toolbox.tree = tree

    # Schema introspection comes from the Warehouse protocol, not the harness's hardcoded,
    # rung-keyed table list — which raises a catalog error against any database that does not
    # happen to contain the fixture's tables.
    _bind_introspection(grounding, warehouse)

    return Engine(warehouse=warehouse, grounding=grounding, capabilities=caps, guardrails=rails,
                  concessions=tuple(concessions))


def get_model(name: str, *, mock: bool = False, reasoning: str | None = None):
    """Resolve a model by name. Quarantined here with everything else harness-shaped, because the
    harness's catalog is a closed set of priced models chosen for an experiment — a product needs
    an open registry, and that arrives with the vendoring."""
    from agent.runtime.providers import get_model as _get  # noqa: PLC0415 — quarantined by design

    try:
        return _get(name, mock=mock, reasoning=reasoning)
    except Exception as exc:
        raise EngineError(f"unknown or unavailable model {name!r}: {exc}") from exc


__all__ = [
    "Capabilities", "Engine", "EngineError", "Guardrails",
    "build_engine", "get_model", "WarehouseError",
]
