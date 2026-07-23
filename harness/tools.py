"""The agent's tools, gated by rung.

Every tool returns a plain string (plus an is_error flag) — the string is what the
model reads. Numbers are always computed here or by the semantic layer / tree, never
invented by the model. The terminal tools (`answer` / `refuse` / `clarify`) are defined
here so the model can see them, but the agent loop (not this dispatcher) handles them,
because they end the run.
"""

from __future__ import annotations

import json

from . import spec_check, verifier
from .config import resolve_period
from .guardrails import LADDER, Guardrails
from .semantic import SemanticError, SemanticLayer
from .tree import MetricTree, TreeError
from .warehouse import QueryError, describe_table, run_query, schema_text

# The three terminal tools. Every run ends through exactly one of them, so the
# outcome is a typed field, never a phrase to be text-matched out of prose.
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


def _fmt_rows(columns, rows) -> str:
    head = ", ".join(columns)
    if not rows:
        return f"columns: {head}\n(no rows)"
    body = "\n".join(str(tuple(r)) for r in rows)
    note = "" if len(rows) < 100 else "\n(truncated at 100 rows)"
    return f"columns: {head}\n{body}{note}"


def _numeric_cells(rows) -> list:
    """The typed numeric values a governed query returned — so the output checks read the real
    result, never a number parsed back out of the display text (which now also carries SQL)."""
    return [float(c) for r in rows for c in r
            if isinstance(c, (int, float)) and not isinstance(c, bool)]


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
                 tree: MetricTree | None = None, rrung: int = 1,
                 guardrails: Guardrails | None = None):
        self.con = con
        self.rung = rung
        self.rrung = rrung
        # `rrung` names a preset; `guardrails` overrides it for an ablation cell. Every control
        # below is read from this one set, so a cell is expressible and self-describing.
        self.g = guardrails if guardrails is not None else LADDER[rrung]
        self.semantic = semantic
        self.tree = tree
        # The reliability ladder, re-ordered logically (R0 no guardrails; R1 abstention = the
        # refuse tool; R2 answerability check tools). The cost nudge, the 4-slot spec check, and
        # the unrequested-predicate check are retired from the ladder — the verifier subsumes the
        # latter two. Each guardrail's effect is still measured on its own rung.
        self.last_verdict = None

    # Each control reads from the guardrail set, so call sites are unchanged. Input guardrails
    # (stop a bad number being COMPUTED) then output guardrails (stop one being SERVED).
    @property
    def gate(self) -> bool: return self.g.gate                      # R3
    @property
    def tool_restriction(self) -> bool: return self.g.tool_restriction  # R4
    @property
    def resolve(self) -> bool: return self.g.resolve                # R5
    @property
    def show_sql(self) -> bool: return self.g.transparency          # R6: the compiled SQL...
    @property
    def scope_echo(self) -> bool: return self.g.transparency        # R6: ...and a scope line
    @property
    def single_metric(self) -> bool: return self.g.single_metric    # R7
    @property
    def output_validation(self) -> bool: return self.g.output_validation  # R8
    @property
    def trajectory_verify(self) -> bool: return self.g.trajectory_verify  # R9

    def specs(self, terminal_only: bool = False) -> list[dict]:
        """The action space. `terminal_only` withdraws every data tool, leaving just the exit
        tools — used to CLOSE a run that has stopped calling tools or is about to hit the
        iteration cap, so it ends through the typed protocol instead of dying as an untyped
        error row. Removing the choice is structural; nudging the model in prose is not."""
        specs: list[dict] = []
        if not terminal_only:
            specs += [_GET_SCHEMA, _DESCRIBE_TABLE]
            if not self.tool_restriction:
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
        """At the gate rung, constrain `metric` to the actual catalog (a closed menu):
        the model cannot even *name* a metric that does not exist."""
        if not (self.gate and self.semantic is not None):
            return _QUERY_METRIC
        props = dict(_QUERY_METRIC["input_schema"]["properties"])
        props["metric"] = {**props["metric"], "enum": list(self.semantic.metrics)}
        return {**_QUERY_METRIC, "input_schema": {**_QUERY_METRIC["input_schema"], "properties": props}}

    def _answer_spec(self) -> dict:
        """At the spec-decomposition rung the answer carries its own TYPED provenance: the
        numeric `value` (a real number, so the checks read the answer instead of parsing it
        back out of prose) and the governed `source_metric` it came from (the same closed
        menu as query_metric). Both are the model's typed claims, more reliable than
        reconstructing them from the answer text. A prose / diagnostic answer leaves `value`
        unset, so the output checks stand down rather than force a spec onto words."""
        if not (self.single_metric and self.semantic is not None):
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

    def _gate_block(self, name: str, args: dict) -> str | None:
        """The interception gate: before a governed data call runs, verify every filter VALUE is a
        governed member (R5) and the period/region are inside coverage (R3). Returns a block message
        that names the coded refusal reason, or None to allow. The gate needs no LLM — given a call,
        the verdict is deterministic."""
        if self.semantic is None or name != "query_metric":
            return None
        filters = args.get("filters") or {}
        # R5: an ungoverned filter value is blocked HERE, naming its own coded reason, so the model
        # never sees the "known members" list it would otherwise substitute a sibling from — the
        # failure that served Americas (504) for a "North America" question.
        if self.resolve:
            allowed = self.semantic.allowed_filters(args.get("metric"))
            for col, val in filters.items():
                # Two distinct failures, two reasons: the metric has no such DIMENSION, or the
                # dimension is fine but the VALUE is not a governed member.
                if allowed is not None and col not in allowed:
                    return (f"BLOCKED by governance — {args.get('metric')!r} has no governed "
                            f"dimension {col!r} (it can be sliced by: {sorted(allowed)}). Do NOT "
                            "substitute a different dimension; refuse (dimension_not_supported).")
                for v in (val if isinstance(val, (list, tuple)) else [val]):
                    if self.semantic.resolve_member(col, v) is None:
                        return (f"BLOCKED by governance — {v!r} is not a governed member of {col!r} "
                                "(it may be finer-grained than, or absent from, the governed "
                                "vocabulary). Do NOT substitute a different member and do NOT answer "
                                "for a broader slice; refuse (ungoverned_dimension_value).")
        if not self.gate:
            return None
        region, country = filters.get("region"), filters.get("country")
        start, end, period = args.get("start"), args.get("end"), args.get("period")
        if period:
            try:
                start, end = resolve_period(period)
            except ValueError:
                return None  # let compile() surface the period error
        if not (start or end or region or country):
            return None
        ok, detail = self.semantic.in_coverage(start, end, region, country)
        if not ok:
            return (f"BLOCKED by governance — {detail} This request is outside data coverage and "
                    "cannot be served; refuse (out_of_coverage) or query within coverage.")
        return None

    @staticmethod
    def _verdict(ok: bool, detail: str) -> str:
        return ("YES — " if ok else "NO — ") + detail

    def verify_answer(self, question: str, answer_text: str | None, steps: list, model=None,
                      source_metric: str | None = None, declared_value=None,
                      verifier_model=None) -> tuple[bool, str, str, str]:
        """The output guardrails on an answer before it is served, each gated by its own rung so
        their deltas are measured separately: single-metric enforcement (R7, the number must BE one
        governed result), output validation (R8, well-formed value), and the trajectory verifier
        (R9, the metric must actually answer the question). The 4-slot spec check and the
        unrequested-predicate check are retired from the ladder — the verifier subsumes them — but
        remain in spec_check as tested building blocks / comparison cells.
        Returns (ok, reason, missing, explanation); ok=False converts the answer to a refuse."""
        self.last_verdict = None      # one verdict per answer; the Toolbox outlives the question
        if self.semantic is None or not (self.output_validation or self.single_metric
                                         or self.trajectory_verify):
            return True, "", "", ""
        # the verifier is a careful checker — run it on its own (higher-reasoning) model when given
        vmodel = verifier_model or model
        verify_traj = self._trajectory_verifier(vmodel) if (self.trajectory_verify and vmodel) else None
        return spec_check.verify_answer(
            self.semantic, question, answer_text, steps,
            source_metric=source_metric, declared_value=declared_value,
            run_output_validation=self.output_validation,
            run_single_metric=self.single_metric, verify_traj=verify_traj)

    def _trajectory_verifier(self, model):
        """A callable (question, metric, metric_def, call_args, governed_value, claim) -> verdict,
        that recompiles the SQL the analyst ran and hands the verifier the analyst's ADDED filters
        separately from the metric's definitional clauses (the separation the isolated test showed
        is load-bearing)."""
        def run(question, metric, metric_def, args, gov_value, claim):
            a = args or {}
            sql = self.semantic.compile(
                metric, group_by=a.get("group_by"), filters=a.get("filters"),
                time_grain=a.get("time_grain"), start=a.get("start"), end=a.get("end"),
                period=a.get("period"), resolve=self.resolve)
            window = a.get("period") or (f"{a.get('start')}..{a.get('end')}"
                                         if (a.get("start") or a.get("end")) else None)
            ok, mismatch, reason = verifier.verify_trajectory(
                model, question, metric, metric_def, sql, gov_value,
                claim, applied_filters=a.get("filters"), time_window=window)
            # Persist the judge's own verdict WITH the evidence it saw, so its error rate can
            # later be scored against human labels. A judge you cannot score is just an
            # unverified opinion — and every "0 confident-wrong" claim rests on this one.
            self.last_verdict = {"answers_question": ok, "mismatch": mismatch, "reason": reason,
                                 "metric": metric, "sql": sql, "applied_filters": a.get("filters"),
                                 "time_window": window, "governed_value": gov_value, "claim": claim}
            return ok, mismatch, reason
        return run

    def dispatch(self, name: str, args: dict) -> tuple[str, bool, list | None]:
        """Run a tool. Returns (text, is_error, values): `text` is what the model reads, `values`
        the typed numeric result of a governed query (None for other tools) so the output checks
        never parse the display text. Errors come back as the DB/semantic message to self-correct."""
        try:
            if name == "get_schema":
                return schema_text(self.con, self.rung), False, None
            if name == "describe_table":
                return describe_table(self.con, args["table"], self.rung), False, None
            if name == "run_sql":
                cols, rows = run_query(self.con, args["query"])
                return _fmt_rows(cols, rows), False, None
            if name == "list_metrics":
                return self.semantic.list_metrics_text(), False, None
            if name == "query_metric":
                block = self._gate_block(name, args)
                if block is not None:
                    return block, True, None
                sql, cols, rows = self.semantic.query_with_sql(
                    args["metric"], group_by=args.get("group_by"), filters=args.get("filters"),
                    time_grain=args.get("time_grain"), start=args.get("start"),
                    end=args.get("end"), period=args.get("period"), resolve=self.resolve)
                text = _fmt_rows(cols, rows)
                if self.scope_echo:       # R9+: a plain scope line, flagging a narrowed subset
                    text += "\n[scope] " + self.semantic.scope_line(
                        args["metric"], filters=args.get("filters"), period=args.get("period"),
                        start=args.get("start"), end=args.get("end"),
                        group_by=args.get("group_by"), resolve=self.resolve)
                if self.show_sql:       # R9+: the exact compiled SQL
                    text += f"\n[sql] {sql}"
                return text, False, _numeric_cells(rows)
            if name == "check_metric_exists":
                return self._verdict(*self.semantic.metric_exists(args["term"])), False, None
            if name == "check_coverage":
                return self._verdict(*self.semantic.in_coverage(
                    args.get("start"), args.get("end"),
                    args.get("region"), args.get("country"))), False, None
            if name == "check_segment_defined":
                return self._verdict(*self.semantic.segment_defined(args["term"])), False, None
            if name == "check_causal_evidence":
                if self.tree is None:
                    return "NO — no metric tree at this rung; no causal evidence is encoded.", False, None
                return self._verdict(*self.tree.causal_evidence(
                    args.get("driver"), args.get("outcome"))), False, None
            if name == "get_metric_tree":
                return self.tree.describe(), False, None
            if name == "explain_change":
                out = self.tree.explain_change(
                    node=args.get("node"), period_a=args.get("period_a", "prev_week"),
                    period_b=args.get("period_b", "last_week"), filters=args.get("filters"))
                return json.dumps(out, default=str, indent=2), False, None
            return f"Unknown tool {name!r}.", True, None
        except (QueryError, SemanticError, TreeError) as exc:
            return f"Error: {exc}", True, None
        except KeyError as exc:
            return f"Error: missing argument {exc}", True, None
