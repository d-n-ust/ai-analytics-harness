"""The data-plane tools: schema, tables, raw SQL, the catalogue, and the governed query.

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json                                                                  # noqa: F401
from dataclasses import replace                                              # noqa: F401

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS                           # noqa: F401
from warehouse import NAMED_PERIODS, TIME_GRAINS, QueryError, describe_table, run_query, schema_text  # noqa: F401,E501

from ..core.conversation import ToolResult                                        # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401
from ..core.outcomes import REASON_MEANINGS, REFUSAL_REASONS                      # noqa: F401
from ..core.protocol import Protocol                                              # noqa: F401
from ..core.rungs import capabilities                                             # noqa: F401
from ._shared import _fmt_rows, _labelled, _measure_values, _time_scope_line, _verdict  # noqa: F401


_GET_SCHEMA = {
    "name": "get_schema",
    "description": "List the tables available to you and their columns.",
    "input_schema": {"type": "object", "properties": {}},
}


_DESCRIBE_TABLE = {
    "name": "describe_table",
    "description": "Show one table's columns and a few sample rows.",
    "input_schema": {
        "type": "object",
        "properties": {"table": {"type": "string"}},
        "required": ["table"],
    },
}


_RUN_SQL = {
    "name": "run_sql",
    "description": "Run a read-only DuckDB SQL query (a single SELECT/WITH) and get the rows back.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}


_LIST_METRICS = {
    "name": "list_metrics",
    "description": "Re-print the governed metric catalogue. The FULL catalogue is already in your "
                   "instructions under GOVERNED METRIC CATALOGUE — read it there; call this only "
                   "if you genuinely need it re-printed.",
    "input_schema": {"type": "object", "properties": {}},
}


_SHOW_ONTOLOGY = {
    "name": "show_metric_ontology",
    "description": ("Show a governed metric's full ontology BEFORE querying it: its exact "
                    "definition and rules, the arguments it accepts, its dimensions with their "
                    "governed values, and a usage example. Call it to confirm a segment value "
                    "exists before you filter by it; a value it does not list is not in the data."),
    "input_schema": {"type": "object",
                     "properties": {"metric": {"type": "string",
                                    "description": "Metric name, from the governed metric list."}},
                     "required": ["metric"]},
}


_QUERY_METRIC = {
    "name": "query_metric",
    "description": ("Compute a governed metric. Prefer this over raw SQL for defined "
                    "business measures so the definition and grain are correct."),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "description": "Metric name (see list_metrics)."},
            "group_by": {"type": "array", "items": {"type": "string"},
                         "description": "Dimensions to break the metric down by."},
            "filters": {"type": "object", "additionalProperties": True,
                        "description": "e.g. {\"platform\": \"ios\", \"is_internal\": false}"},
            "time_grain": {"type": "string", "enum": list(TIME_GRAINS),
                           "description": "Bucket the time column (for trends)."},
            # The contract, stated where the model reads it: named values are RELATIVE and always
            # complete periods; a specific calendar month is YYYY-MM; anything else is start/end;
            # OMISSION means the current value. The enum alone taught a measured failure: asked for
            # "April 2026" with only relative presets on the menu, a model took the nearest legal
            # item (last_month) and silently got June. The pattern makes the natural utterance
            # legal instead. The omission sentence closed a second measured failure of the same
            # shape: nothing at decision time said what leaving period out means, so a model asked
            # for "MRR right now" reached for last_month and served June's snapshot as current.
            # The response echoed the omission rule, but only after an unscoped call the model
            # never risked making.
            "period": {"type": "string",
                       "anyOf": [{"enum": list(NAMED_PERIODS)},
                                 {"pattern": r"^\d{4}-(\d{2}|[Qq][1-4]|[Hh][12])$"}],
                       "description": "Either a RELATIVE preset (always a complete period: "
                                      f"{', '.join(NAMED_PERIODS)}), a calendar month as YYYY-MM, "
                                      "a quarter as YYYY-Qn (e.g. 2026-Q2), or a half-year as "
                                      "YYYY-Hn. For any other exact range use start/end. "
                                      "Omit period entirely for the current value: a snapshot "
                                      "(stock) metric then returns its latest snapshot, which is "
                                      "the 'right now' number; a flow metric totals all time."},
            "start": {"type": "string", "description": "Explicit start date YYYY-MM-DD "
                                                       "(for exact calendar ranges)."},
            "end": {"type": "string", "description": "Explicit end date YYYY-MM-DD."},
        },
        "required": ["metric"],
    },
}


_CHECK_METRIC = {
    "name": "check_metric_exists",
    "description": "Check whether a governed metric/definition exists for a term (e.g. 'engagement score').",
    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
}


def _get_schema(tb, args) -> ToolResult:
    return ToolResult(schema_text(tb.con, capabilities(tb.rung).star, getattr(tb, "schema", None)))


def _describe_table(tb, args) -> ToolResult:
    return ToolResult(describe_table(tb.con, args["table"], capabilities(tb.rung).star,
                                     getattr(tb, "schema", None)))


def _run_sql(tb, args) -> ToolResult:
    cols, rows = run_query(tb.con, args["query"], schema=getattr(tb, "schema", None))
    return ToolResult(_fmt_rows(cols, rows))


def _list_metrics(tb, args) -> ToolResult:
    # The same text the system prompt preloads (grounding.py) — the tool stays for re-reading,
    # but a run that starts by calling it is spending a turn on what it was already given.
    return ToolResult(tb.semantic.list_metrics_text())


def _show_metric_ontology(tb, args) -> ToolResult:
    # The handler behind the `ontology_tool` guardrail: the full per-metric contract, on demand.
    name = args.get("metric")
    if not name or not hasattr(tb.semantic, "metric_ontology"):
        return ToolResult("show_metric_ontology needs a metric name", is_error=True)
    text = tb.semantic.metric_ontology(name)
    return ToolResult(text or f"no governed metric named {name!r}; see the metric list",
                      is_error=not text)


def _query_metric(tb, args) -> ToolResult:
    """The governed data path: compile the metric to SQL, run it, return the rows plus the typed
    measure values the AFTER guardrails read. The SQL travels with the result so DISCLOSURE can
    show what actually ran; whether it is shown is not this function's business."""
    # A null-valued filter is a malformed constraint, not an absent one. Passing it through
    # compiled to WHERE dim = None (a Binder Error, three times in one live run); silently
    # dropping it would be worse — {"user__signup_date": null} usually MEANS a time window, and
    # a dropped window is a whole-history figure served as the period's. Bounce with the fix.
    nulls = [d for d, v in (args.get("filters") or {}).items() if v is None]
    if nulls:
        return ToolResult(
            f"filters carry null for {', '.join(nulls)} — a filter needs a value. For a time "
            f"window use `period` (or `start`/`end`); otherwise omit the key.", is_error=True)
    sql, cols, rows = tb.semantic.query_with_sql(
        args["metric"], group_by=args.get("group_by"), filters=args.get("filters"),
        time_grain=args.get("time_grain"), start=args.get("start"), end=args.get("end"),
        period=args.get("period"), resolve=tb.g.resolve, segment=args.get("segment"))
    # The `metric_brief` arm prepends the metric's focused contract to its own result — governed
    # values, the refuse-if-absent rule, and a mark on the segments this call applied. It rides on a
    # result the agent already reads, so it adds no model turn (loop.py's `applied_segment` is the
    # enforcement half). Guarded on hasattr so engines without the block are unaffected.
    brief = (tb.semantic.metric_brief(args["metric"], applied=args.get("filters"))
             if getattr(tb.g, "metric_brief", False) and hasattr(tb.semantic, "metric_brief") else "")
    values = _measure_values(cols, rows)
    # EMPTY RESULT IS NOT ZERO. A filtered/dated query that returns no numeric measure — a filter
    # value that matches nothing (cohort_month='2026-Q2' when the values are monthly), a period out
    # of coverage — otherwise reaches the model as a bare (None,)/(no rows) it reads as 0 and serves.
    # An empty result is a FACT the query returned; flag it here so the model cannot serve a confident
    # zero, with the dimension's real values as a non-brittle hint (advisory, never a gate).
    # Two ways a filter matches nothing, both flagged so the model cannot serve a confident zero:
    #   empty   — no numeric measure came back (a SUM of no rows is NULL, e.g. cohort_month='2026-Q2').
    #   unknown — a filter value that is not a governed MEMBER of its dimension (a COUNT of no rows is
    #             0, indistinguishable from a real zero at the value level — plan='enterprise' -> 0).
    # `unknown` is the non-brittle form of value-grounding: it fires only for a dimension the layer
    # ENUMERATES (low-cardinality; the member list is authoritative), case-normalised, so it never
    # false-flags a real value; an unbounded dimension (dates) has no members and is left to `empty`.
    empty = not values and (args.get("filters") or args.get("period") or args.get("start"))
    unknown = _unknown_filter_values(tb, args)
    warning = (_empty_result_note(args, unknown) + "\n") if (empty or unknown) else ""
    return ToolResult(warning + brief + _time_scope_line(args) + _fmt_rows(cols, rows),
                      sql=sql, **_labelled(values))


def _unknown_filter_values(tb, args) -> list:
    """Filters whose VALUE is not a governed member of its dimension — [(dim, value, [members])].
    Only for dimensions the layer enumerates (authoritative member list); case/whitespace-normalised,
    so a valid value in any casing is never flagged. Unbounded dimensions (no members) are skipped."""
    try:
        members = tb.semantic.dimension_members()
    except Exception:                                                       # noqa: BLE001
        return []
    norm = lambda s: str(s).strip().lower()
    out = []
    for dim, val in (args.get("filters") or {}).items():
        vals = members.get(dim) or members.get(str(dim).split("__")[-1])
        if vals and norm(val) not in {norm(v) for v in vals}:
            out.append((dim, val, list(vals)))
    return out


def _empty_result_note(args, unknown) -> str:
    """The 'matched nothing' flag: an empty result or an unknown filter value is NOT zero. Lists the
    dimension's real values so the model can re-query — the members come from the layer, advisory."""
    lines = ["EMPTY RESULT — this query matched NO ROWS, which is NOT zero. Do not report 0. A filter "
             "value that is not a real member of its dimension, or a period outside coverage, matches "
             "nothing."]
    for dim, val, vals in unknown:
        lines.append(f"  {dim}={val!r} is NOT a governed value of {dim}; its values are: "
                     f"{', '.join(map(str, vals))}.")
    lines.append("Re-query with a valid value (or the period for a quarter), or `refuse` "
                 "(out_of_coverage / ungoverned_dimension_value) — never serve 0.")
    return "\n".join(lines)


def _check_metric_exists(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.metric_exists(args["term"])))


__all__ = ['_CHECK_METRIC', '_DESCRIBE_TABLE', '_GET_SCHEMA', '_LIST_METRICS', '_QUERY_METRIC', '_RUN_SQL', '_SHOW_ONTOLOGY', '_check_metric_exists', '_describe_table', '_empty_result_note', '_get_schema', '_list_metrics', '_query_metric', '_run_sql', '_show_metric_ontology', '_unknown_filter_values']
