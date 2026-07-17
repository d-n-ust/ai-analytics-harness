"""The agent's tools, gated by rung.

Every tool returns a plain string (plus an is_error flag) — the string is what the
model reads. Numbers are always computed here or by the semantic layer / tree, never
invented by the model. `final_answer` is defined here so the model can see it, but the
agent loop (not this dispatcher) handles it, because it ends the run.
"""

from __future__ import annotations

import json

from .semantic import SemanticError, SemanticLayer
from .tree import MetricTree, TreeError
from .warehouse import QueryError, describe_table, run_query, schema_text

_FINAL_ANSWER = {
    "name": "final_answer",
    "description": ("Submit your final answer and end. Put the direct value in `answer` "
                    "(a number for numeric questions), and a one-line justification in "
                    "`explanation`. If the data cannot answer the question reliably, set "
                    "answer to 'I cannot answer this reliably' and say why."),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "The direct answer (a number if numeric)."},
            "explanation": {"type": "string", "description": "One line on how you got it."},
        },
        "required": ["answer", "explanation"],
    },
}

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
    "description": "List the governed metrics available through the semantic layer.",
    "input_schema": {"type": "object", "properties": {}},
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
            "time_grain": {"type": "string", "enum": ["day", "week", "month"],
                           "description": "Bucket the time column (for trends)."},
            "period": {"type": "string",
                       "enum": ["last_week", "prev_week", "last_month", "last_quarter", "ytd", "all"],
                       "description": "A named period."},
            "start": {"type": "string", "description": "Explicit start date YYYY-MM-DD."},
            "end": {"type": "string", "description": "Explicit end date YYYY-MM-DD."},
        },
        "required": ["metric"],
    },
}

_GET_METRIC_TREE = {
    "name": "get_metric_tree",
    "description": "Show the metric tree: how the North Star decomposes, with identity and influence edges.",
    "input_schema": {"type": "object", "properties": {}},
}

_EXPLAIN_CHANGE = {
    "name": "explain_change",
    "description": ("Decompose why a metric changed between two periods, walking the tree. "
                    "Returns exact identity contributions plus likely (hedged) influence drivers. "
                    "Use this for 'why did X move' questions. The numbers are computed for you."),
    "input_schema": {
        "type": "object",
        "properties": {
            "node": {"type": "string", "description": "Tree node to explain (default: the root)."},
            "period_a": {"type": "string", "description": "Baseline period (default prev_week)."},
            "period_b": {"type": "string", "description": "Comparison period (default last_week)."},
            "filters": {"type": "object", "additionalProperties": True},
        },
    },
}


def _fmt_rows(columns, rows) -> str:
    head = ", ".join(columns)
    if not rows:
        return f"columns: {head}\n(no rows)"
    body = "\n".join(str(tuple(r)) for r in rows)
    note = "" if len(rows) < 100 else "\n(truncated at 100 rows)"
    return f"columns: {head}\n{body}{note}"


class Toolbox:
    """Holds the live warehouse/semantic/tree handles and exposes the tools for a rung."""

    def __init__(self, con, rung: int, semantic: SemanticLayer | None = None,
                 tree: MetricTree | None = None):
        self.con = con
        self.rung = rung
        self.semantic = semantic
        self.tree = tree

    def specs(self) -> list[dict]:
        specs = [_GET_SCHEMA, _DESCRIBE_TABLE, _RUN_SQL]
        if self.rung >= 3:
            specs += [_LIST_METRICS, _QUERY_METRIC]
        if self.rung >= 6:
            specs += [_GET_METRIC_TREE, _EXPLAIN_CHANGE]
        specs.append(_FINAL_ANSWER)
        return specs

    def dispatch(self, name: str, args: dict) -> tuple[str, bool]:
        """Run a tool. Returns (text, is_error). Errors come back as the DB/semantic
        message so the model can self-correct."""
        try:
            if name == "get_schema":
                return schema_text(self.con, self.rung), False
            if name == "describe_table":
                return describe_table(self.con, args["table"], self.rung), False
            if name == "run_sql":
                cols, rows = run_query(self.con, args["query"])
                return _fmt_rows(cols, rows), False
            if name == "list_metrics":
                return self.semantic.list_metrics_text(), False
            if name == "query_metric":
                cols, rows = self.semantic.query(
                    args["metric"], group_by=args.get("group_by"), filters=args.get("filters"),
                    time_grain=args.get("time_grain"), start=args.get("start"),
                    end=args.get("end"), period=args.get("period"))
                return _fmt_rows(cols, rows), False
            if name == "get_metric_tree":
                return self.tree.describe(), False
            if name == "explain_change":
                out = self.tree.explain_change(
                    node=args.get("node"), period_a=args.get("period_a", "prev_week"),
                    period_b=args.get("period_b", "last_week"), filters=args.get("filters"))
                return json.dumps(out, default=str, indent=2), False
            return f"Unknown tool {name!r}.", True
        except (QueryError, SemanticError, TreeError) as exc:
            return f"Error: {exc}", True
        except KeyError as exc:
            return f"Error: missing argument {exc}", True
