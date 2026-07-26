"""The agent's tools, gated by rung.

Every tool returns a ToolResult: the text the model reads, whether it failed, and — for a
governed query — the typed numbers it returned, so the output checks read the real result
instead of parsing it back out of the display text. Numbers are always computed here or by
the semantic layer / tree, never invented by the model. The terminal tools (`answer` / `refuse` / `clarify`) are defined
here so the model can see them, but the agent loop (not this dispatcher) handles them,
because they end the run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from semantic.semantic import SemanticError, SemanticLayer
from semantic.tree import MetricTree, TreeError

# The three terminal tools. Every run ends through exactly one of them, so the
# outcome is a typed field, never a phrase to be text-matched out of prose.
from warehouse.warehouse import DEFAULT_MAX_ROWS as MAX_ROWS  # the cap _fmt_rows reports
from warehouse.warehouse import QueryError, describe_table, run_query, schema_text

from . import input_guardrail
from .guardrails import LADDER, GuardrailSet
from .protocol import ToolResult

REFUSAL_REASONS = ["no_governed_definition", "out_of_coverage", "segment_undefined",
                   "no_causal_evidence", "false_premise", "wrong_measure", "wrong_grain",
                   "dimension_not_supported", "ungoverned_dimension_value",
                   "result_empty", "implausible_value", "other"]

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
                        "description": "The specific definition, coverage window, segment, or evidence that is missing."},
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
# check and the coverage check run; here the model may run them itself before committing.
_CHECK_METRIC = {
    "name": "check_metric_exists",
    "description": "Check whether a governed metric/definition exists for a term (e.g. 'engagement score').",
    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
}

_CHECK_COVERAGE = {
    "name": "check_coverage",
    "description": "Check whether data coverage exists for a period, optionally for one region "
                   "or country. Pass both start and end for a range; the whole period must be "
                   "covered.",
    "input_schema": {"type": "object", "properties": {
        "start": {"type": "string", "description": "YYYY-MM-DD"},
        "end": {"type": "string", "description": "YYYY-MM-DD (end of the range)"},
        "region": {"type": "string"},
        # A country inherits its region's availability window, so a question scoped to one is
        # answerable-or-not on the same terms. Without this the model could not ask.
        "country": {"type": "string"}}, "required": ["start", "end"]},
}

_CHECK_SEGMENT = {
    "name": "check_segment_defined",
    "description": "Check whether a segment term (e.g. 'enterprise users') has a governed definition.",
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


# --------------------------------------------------------------------------- #
# Handlers. Each sits next to the schema it implements; `tb` is the Toolbox holding the live
# warehouse / semantic / tree handles and the guardrail set.
# --------------------------------------------------------------------------- #
def _fmt_rows(columns, rows) -> str:
    head = ", ".join(columns)
    if not rows:
        return f"columns: {head}\n(no rows)"
    body = "\n".join(str(tuple(r)) for r in rows)
    note = "" if len(rows) < MAX_ROWS else f"\n(truncated at {MAX_ROWS} rows)"
    return f"columns: {head}\n{body}{note}"


def _measure_values(cols, rows) -> list:
    """The numbers a governed query reported, one per row: the `value` column the compiler
    always aliases the measure to.

    Reading every numeric cell of every row instead loses which cell IS the measure, and the
    checks downstream take the first one — so a breakdown handed them its first group's number
    rather than the group the answer came from, and a numeric dimension member could pass for
    a governed result. No `value` column means nothing verifiable came back, which fails the
    provenance check closed rather than silently checking the wrong number."""
    if "value" not in cols:
        return []
    i = cols.index("value")
    return [float(r[i]) for r in rows
            if isinstance(r[i], (int, float)) and not isinstance(r[i], bool)]


def _verdict(ok: bool, detail: str) -> str:
    return ("YES — " if ok else "NO — ") + detail


def _get_schema(tb, args) -> ToolResult:
    return ToolResult(schema_text(tb.con, tb.rung))


def _describe_table(tb, args) -> ToolResult:
    return ToolResult(describe_table(tb.con, args["table"], tb.rung))


def _run_sql(tb, args) -> ToolResult:
    cols, rows = run_query(tb.con, args["query"])
    return ToolResult(_fmt_rows(cols, rows))


def _list_metrics(tb, args) -> ToolResult:
    return ToolResult(tb.semantic.list_metrics_text())


def _query_metric(tb, args) -> ToolResult:
    """The governed data path. The input guardrail runs first, so a call that must not be
    answered never reaches the warehouse; transparency then shows the model what it actually
    got — the scope the number covers and the exact SQL — rather than a bare figure to trust."""
    blocked = input_guardrail.block(tb.semantic, tb.g, args)
    if blocked is not None:
        return ToolResult(blocked, is_error=True)
    sql, cols, rows = tb.semantic.query_with_sql(
        args["metric"], group_by=args.get("group_by"), filters=args.get("filters"),
        time_grain=args.get("time_grain"), start=args.get("start"), end=args.get("end"),
        period=args.get("period"), resolve=tb.g.resolve, segment=args.get("segment"))
    text = _fmt_rows(cols, rows)
    if tb.g.transparency:
        text += "\n[scope] " + tb.semantic.scope_line(
            args["metric"], filters=args.get("filters"), period=args.get("period"),
            start=args.get("start"), end=args.get("end"),
            group_by=args.get("group_by"), resolve=tb.g.resolve)
        text += f"\n[sql] {sql}"
    return ToolResult(text, values=_measure_values(cols, rows))


def _check_metric_exists(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.metric_exists(args["term"])))


def _check_coverage(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.in_coverage(
        args.get("start"), args.get("end"), args.get("region"), args.get("country"))))


def _check_segment_defined(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.segment_defined(args["term"])))


def _check_causal_evidence(tb, args) -> ToolResult:
    if tb.tree is None:
        return ToolResult("NO — no metric tree at this rung; no causal evidence is encoded.")
    return ToolResult(_verdict(*tb.tree.causal_evidence(args.get("driver"), args.get("outcome"))))


def _get_metric_tree(tb, args) -> ToolResult:
    return ToolResult(tb.tree.describe())


def _explain_change(tb, args) -> ToolResult:
    out = tb.tree.explain_change(node=args.get("node"),
                                 period_a=args.get("period_a", "prev_week"),
                                 period_b=args.get("period_b", "last_week"),
                                 filters=args.get("filters"))
    return ToolResult(json.dumps(out, default=str, indent=2))


@dataclass(frozen=True)
class Tool:
    """One tool: the schema the model sees and the code that runs it, in one place.

    `run=None` marks a TERMINAL tool — it ends the run, so the agent loop decides what it means
    and there is nothing to dispatch. That is the only legitimate reason for a tool to have no
    handler, and tests/test_semantic.py holds it to that."""

    schema: dict
    run: Callable | None = None

    @property
    def name(self) -> str:
        return self.schema["name"]


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool(_GET_SCHEMA, _get_schema),
    Tool(_DESCRIBE_TABLE, _describe_table),
    Tool(_RUN_SQL, _run_sql),
    Tool(_LIST_METRICS, _list_metrics),
    Tool(_QUERY_METRIC, _query_metric),
    Tool(_CHECK_METRIC, _check_metric_exists),
    Tool(_CHECK_COVERAGE, _check_coverage),
    Tool(_CHECK_SEGMENT, _check_segment_defined),
    Tool(_CHECK_CAUSAL, _check_causal_evidence),
    Tool(_GET_METRIC_TREE, _get_metric_tree),
    Tool(_EXPLAIN_CHANGE, _explain_change),
    Tool(_ANSWER), Tool(_REFUSE), Tool(_CLARIFY),      # terminal: the loop ends the run
]}



class Toolbox:
    """Holds the live warehouse/semantic/tree handles and exposes the tools for a rung.

    `rung` gates grounding (what the agent knows); the `guardrails` set gates reliability
    (what the agent may do about not knowing):
      0 = no refuse tool · 1+ = typed refusal · 2+ = check_* tools callable ·
      3+ = the coverage check (governed calls validated; out-of-coverage /
           undefined requests are blocked by the system, not the model) ·
      4+ = the tool restriction (raw SQL removed, so every data path is a gated governed call).
    The coverage check and tool restriction are structural: they hold regardless of what the model does,
    which is why they can be proven exhaustively without an LLM (see tests/)."""

    def __init__(self, con, rung: int, semantic: SemanticLayer | None = None,
                 tree: MetricTree | None = None, guardrails: GuardrailSet | None = None):
        self.con = con
        self.rung = rung
        # GuardrailSet is the one primitive: which reliability guardrails are on. A ladder preset
        # (LADDER[n]) and an ablation cell are both just a GuardrailSet set; every guardrail below reads
        # from it, so a cell is expressible and self-describing. Default R1 (abstention).
        self.g = guardrails if guardrails is not None else LADDER[1]
        self.semantic = semantic
        self.tree = tree

    def specs(self, terminal_only: bool = False) -> list[dict]:
        """The action space. `terminal_only` withdraws every data tool, leaving just the exit
        tools — used to CLOSE a run that has stopped calling tools or is about to hit the
        iteration cap, so it ends through the typed protocol instead of dying as an untyped
        error row. Removing the choice is structural; nudging the model in prose is not."""
        specs: list[dict] = []
        if not terminal_only:
            specs += [_GET_SCHEMA, _DESCRIBE_TABLE]
            if not self.g.tool_restriction:
                specs.append(_RUN_SQL)
            if self.rung >= 3:
                specs += [_LIST_METRICS, self._query_metric_spec()]
            if self.rung >= 6:
                specs += [_GET_METRIC_TREE, _EXPLAIN_CHANGE]
            if self.g.check_tools and self.semantic is not None:   # R2: answerability check tools
                specs += [_CHECK_METRIC, _CHECK_COVERAGE, _CHECK_SEGMENT, _CHECK_CAUSAL]
        specs.append(self._answer_spec())
        if self.g.abstain:
            specs.append(_REFUSE)
        specs.append(_CLARIFY)
        return specs

    def _query_metric_spec(self) -> dict:
        """Constrain `metric` to the catalog once the coverage check is on (a closed menu — the model
        cannot even *name* a metric that doesn't exist), and offer the governed `segment`
        enum whenever the layer defines any (a named segment like real_acquisition)."""
        if self.semantic is None:
            return _QUERY_METRIC
        props = dict(_QUERY_METRIC["input_schema"]["properties"])
        if self.g.coverage_check:
            props["metric"] = {**props["metric"], "enum": list(self.semantic.metrics)}
        segs = self.semantic.segment_names()
        if segs:
            props["segment"] = {"type": "string", "enum": segs,
                                "description": "A governed named segment / reusable filter (see list_metrics), "
                                               "e.g. real_acquisition to exclude test channels."}
        return {**_QUERY_METRIC, "input_schema": {**_QUERY_METRIC["input_schema"], "properties": props}}

    def _answer_spec(self) -> dict:
        """At the spec-decomposition rung the answer carries its own TYPED provenance: the
        numeric `value` (a real number, so the checks read the answer instead of parsing it
        back out of prose) and the governed `source_metric` it came from (the same closed
        menu as query_metric). Both are the model's typed claims, more reliable than
        reconstructing them from the answer text. A prose / diagnostic answer leaves `value`
        unset, so the output checks stand down rather than force a spec onto words."""
        if not (self.g.single_metric and self.semantic is not None):
            return _ANSWER
        props = dict(_ANSWER["input_schema"]["properties"])
        props["value"] = {
            "type": "number",
            "description": "If your answer is a single number, repeat it here as a number "
                           "(not text). Leave it out for a non-numeric answer (an assessment, "
                           "a driver, a list) — the value check then does not apply."}
        props["source_metric"] = {
            "type": "string", "enum": list(self.semantic.metrics),
            "description": "If `value` came from a governed metric, name that metric (as passed "
                           "to query_metric). Omit for a derived or non-metric answer."}
        return {**_ANSWER, "input_schema": {**_ANSWER["input_schema"], "properties": props}}

    def dispatch(self, name: str, args: dict) -> ToolResult:
        """Run one tool. Errors come back as the DB/semantic message rather than as exceptions,
        so the model is told what went wrong and can correct itself — a crashed run is a lost
        measurement, which is worse than a wrong answer because it looks like neither."""
        tool = TOOLS.get(name)
        if tool is None or tool.run is None:
            return ToolResult(f"Unknown tool {name!r}.", is_error=True)
        try:
            return tool.run(self, args)
        except (QueryError, SemanticError, TreeError) as exc:
            return ToolResult(f"Error: {exc}", is_error=True)
        except KeyError as exc:
            return ToolResult(f"Error: missing argument {exc}", is_error=True)
