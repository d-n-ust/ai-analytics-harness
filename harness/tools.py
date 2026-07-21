"""The agent's tools, gated by rung.

Every tool returns a plain string (plus an is_error flag) — the string is what the
model reads. Numbers are always computed here or by the semantic layer / tree, never
invented by the model. The terminal tools (`answer` / `refuse` / `clarify`) are defined
here so the model can see them, but the agent loop (not this dispatcher) handles them,
because they end the run.
"""

from __future__ import annotations

import json

from .config import resolve_period
from .semantic import SemanticError, SemanticLayer
from .tree import MetricTree, TreeError
from .warehouse import QueryError, describe_table, run_query, schema_text

# The three terminal tools. Every run ends through exactly one of them, so the
# outcome is a typed field, never a phrase to be text-matched out of prose.
REFUSAL_REASONS = ["no_governed_definition", "out_of_coverage", "population_undefined",
                   "no_causal_evidence", "false_premise", "other"]

_ANSWER = {
    "name": "answer",
    "description": ("Submit the final answer and end. Put the direct value in `answer` "
                    "(a number for numeric questions), and a one-line justification in "
                    "`explanation`."),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "The direct answer (a number if numeric)."},
            "explanation": {"type": "string", "description": "One line on how you got it."},
        },
        "required": ["answer", "explanation"],
    },
}

_REFUSE = {
    "name": "refuse",
    "description": ("Decline to answer and end, because no reliable answer exists in the "
                    "available data. Give the coded reason and name the specific thing that "
                    "is missing, so the claim can be checked."),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "enum": REFUSAL_REASONS},
            "missing": {"type": "string",
                        "description": "The specific definition, coverage window, population, or evidence that is missing."},
            "explanation": {"type": "string", "description": "One line: why this cannot be answered reliably."},
        },
        "required": ["reason", "missing"],
    },
}

_CLARIFY = {
    "name": "clarify",
    "description": ("End by asking one clarifying question, because the question is ambiguous "
                    "and materially different readings would give different answers."),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The single clarifying question to ask."},
        },
        "required": ["question"],
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

# Answerability checks exposed to the model (reliability rung 3+). Each is one
# deterministic lookup against governance metadata — the same checks the excuse
# check and the gate run; here the model may run them itself before committing.
_CHECK_METRIC = {
    "name": "check_metric_exists",
    "description": "Check whether a governed metric/definition exists for a term (e.g. 'engagement score').",
    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
}

_CHECK_COVERAGE = {
    "name": "check_coverage",
    "description": "Check whether data coverage exists for a period (and optional region). "
                   "Pass both start and end for a range; the whole period must be covered.",
    "input_schema": {"type": "object", "properties": {
        "start": {"type": "string", "description": "YYYY-MM-DD"},
        "end": {"type": "string", "description": "YYYY-MM-DD (end of the range)"},
        "region": {"type": "string"}}, "required": ["start", "end"]},
}

_CHECK_POPULATION = {
    "name": "check_population_defined",
    "description": "Check whether a population term (e.g. 'enterprise users') has a governed definition.",
    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
}

_CHECK_CAUSAL = {
    "name": "check_causal_evidence",
    "description": "Check whether the governed metric tree carries causal evidence linking a driver to an outcome.",
    "input_schema": {"type": "object", "properties": {
        "driver": {"type": "string"}, "outcome": {"type": "string"}},
        "required": ["driver", "outcome"]},
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
    """Holds the live warehouse/semantic/tree handles and exposes the tools for a rung.

    `rung` gates grounding (what the agent knows); `rrung` gates reliability
    (what the agent may do about not knowing):
      0 = no refuse tool · 1+ = typed refusal · 3+ = check_* tools callable ·
      4+ = the interception GATE (governed calls validated; out-of-coverage /
           undefined requests are blocked by the system, not the model) ·
      5+ = the FENCE (raw SQL removed, so every data path is a gated governed call).
    The gate and fence are structural: they hold regardless of what the model does,
    which is why they can be proven exhaustively without an LLM (see tests/)."""

    def __init__(self, con, rung: int, semantic: SemanticLayer | None = None,
                 tree: MetricTree | None = None, rrung: int = 1):
        self.con = con
        self.rung = rung
        self.rrung = rrung
        self.semantic = semantic
        self.tree = tree
        self.gate = rrung >= 4          # validate governed calls; block on failure
        self.fence = rrung >= 5         # no raw SQL — governed metrics only

    def specs(self) -> list[dict]:
        specs = [_GET_SCHEMA, _DESCRIBE_TABLE]
        if not self.fence:
            specs.append(_RUN_SQL)
        if self.rung >= 3:
            specs += [_LIST_METRICS, self._query_metric_spec()]
        if self.rung >= 6:
            specs += [_GET_METRIC_TREE, _EXPLAIN_CHANGE]
        if self.rrung >= 3 and self.semantic is not None:
            specs += [_CHECK_METRIC, _CHECK_COVERAGE, _CHECK_POPULATION, _CHECK_CAUSAL]
        specs.append(_ANSWER)
        if self.rrung >= 1:
            specs.append(_REFUSE)
        specs.append(_CLARIFY)
        return specs

    def _query_metric_spec(self) -> dict:
        """At the gate rung, constrain `metric` to the actual catalog (a closed menu):
        the model cannot even *name* a metric that does not exist."""
        if not (self.gate and self.semantic is not None):
            return _QUERY_METRIC
        props = dict(_QUERY_METRIC["input_schema"]["properties"])
        props["metric"] = {**props["metric"], "enum": list(self.semantic.metrics)}
        return {**_QUERY_METRIC, "input_schema": {**_QUERY_METRIC["input_schema"], "properties": props}}

    def _gate_block(self, name: str, args: dict) -> str | None:
        """The interception gate: before a governed data call runs, verify the period
        (and region) are inside coverage. Returns a block message, or None to allow.
        The gate needs no LLM — given a call, the verdict is deterministic."""
        if not self.gate or self.semantic is None or name != "query_metric":
            return None
        filters = args.get("filters") or {}
        region = filters.get("region")
        start, end, period = args.get("start"), args.get("end"), args.get("period")
        if period:
            try:
                start, end = resolve_period(period)
            except ValueError:
                return None  # let compile() surface the period error
        if not (start or end or region):
            return None
        ok, detail = self.semantic.in_coverage(start, end, region)
        if not ok:
            return (f"BLOCKED by governance — {detail} This request is outside data coverage and "
                    "cannot be served; refuse (out_of_coverage) or query within coverage.")
        return None

    @staticmethod
    def _verdict(ok: bool, detail: str) -> str:
        return ("YES — " if ok else "NO — ") + detail

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
                block = self._gate_block(name, args)
                if block is not None:
                    return block, True
                cols, rows = self.semantic.query(
                    args["metric"], group_by=args.get("group_by"), filters=args.get("filters"),
                    time_grain=args.get("time_grain"), start=args.get("start"),
                    end=args.get("end"), period=args.get("period"))
                return _fmt_rows(cols, rows), False
            if name == "check_metric_exists":
                return self._verdict(*self.semantic.metric_exists(args["term"])), False
            if name == "check_coverage":
                return self._verdict(*self.semantic.in_coverage(
                    args.get("start"), args.get("end"), args.get("region"))), False
            if name == "check_population_defined":
                return self._verdict(*self.semantic.population_defined(args["term"])), False
            if name == "check_causal_evidence":
                if self.tree is None:
                    return "NO — no metric tree at this rung; no causal evidence is encoded.", False
                return self._verdict(*self.tree.causal_evidence(
                    args.get("driver"), args.get("outcome"))), False
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
