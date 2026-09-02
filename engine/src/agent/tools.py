"""The agent's action space: every tool, and the code that runs it.

Each tool appears ONCE, as a schema paired with its handler. They used to be three places apart
— a schema dict at the top, a gating line in specs(), a branch in a twelve-way if-chain 300
lines below — with nothing linking them, and they drifted: check_coverage's handler read a
`country` argument its schema never offered, so a model could not ask about the one dimension
the coverage rules resolve through.

A tool returns a ToolResult: the text the model reads, whether it failed, and — for a governed
query — the typed numbers it returned, so the output guardrails read the real result instead of
parsing it back out of the display text. Numbers are computed here or by the semantic layer /
tree, never invented by the model.

The terminal tools carry no handler, by design: they end the run, and the agent loop decides
what they mean. Which tools are OFFERED is not decided here either — that is the ACTION_SPACE
guardrails' job (guardrails/action_space.py), so the ladder stays readable in one place.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS  # the cap _fmt_rows reports
from warehouse import NAMED_PERIODS, TIME_GRAINS, QueryError, describe_table, run_query, schema_text

from .conversation import ToolResult
from .guardrails import LADDER, GuardrailSet, action_space, before, disclosure
from .outcomes import REASON_MEANINGS, REFUSAL_REASONS
from .protocol import Protocol
from .rungs import capabilities  # rung -> capabilities mapping stays here (the ladder's owner)

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
            # The enum shipped undocumented, and the model guessed: `other` was chosen 26 times
            # over a specific code that existed and fitted. The meanings live in outcomes.py
            # beside the codes, so the vocabulary the model reads and the one the grader scores
            # cannot drift apart.
            "reason": {
                "type": "string", "enum": REFUSAL_REASONS,
                "description": ("Why this cannot be answered. Name the ROOT CAUSE, not the "
                                "symptom:\n"
                                + "\n".join(f"- {k}: {v}" for k, v in REASON_MEANINGS.items()))},
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

# Answerability checks exposed to the model (reliability rung 3+). Each is one
# deterministic lookup against governance metadata — the same checks the excuse
# check and the coverage check run; here the model may run them itself before committing.
_CHECK_METRIC = {
    "name": "check_metric_exists",
    "description": "Check whether a governed metric/definition exists for a term (e.g. 'engagement score').",
    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
}

# The graph-grounded successor to check_metric_exists. That tool answers the narrower question — is
# there a governed metric NAMED this — which conflates "computable but ungoverned" with "not
# captured", and is the source of the wrong refusal reason. This returns the THREE-WAY answer the
# reason code actually turns on, read off the complete closed-world marts graph.
_CHECK_ANSWERABILITY = {
    "name": "check_answerability",
    "description": "Ground a measure against the complete marts graph: is it a GOVERNED metric, "
                   "COMPUTABLE from captured data with no governed metric, or UNINSTRUMENTED (not "
                   "captured) — and which refuse reason follows. Use it before deciding, instead of "
                   "guessing whether the data exists.",
    "input_schema": {"type": "object", "properties": {
        "measure": {"type": "string",
                    "description": "The measure/quantity to ground, e.g. '90-day retention by channel'."}},
        "required": ["measure"]},
}

_DEFINE_MEASURE = {
    "name": "define_measure",
    "description": "Author a VERIFIED definition for a measure that has no governed metric, and "
                   "compute it. The definition is grounded in the graph, checked for validity, "
                   "executed by construction, and challenged for aptness; the result comes back with "
                   "the definition disclosed. Use this instead of raw SQL for an ungoverned measure "
                   "(a retention/cohort calculation, a custom ratio).",
    "input_schema": {"type": "object", "properties": {
        "measure": {"type": "string",
                    "description": "The measure to define and compute, in the question's own words "
                                   "(e.g. '90-day retention by acquisition channel')."}},
        "required": ["measure"]},
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
    "description": ("Which governed metrics produce or influence another — the structural map, "
                    "no data read. Identity edges are exact arithmetic (a parent IS the product "
                    "of its children); influence edges are correlational only, and carry a "
                    "confidence and their evidence. Every node is a metric."),
    "input_schema": {"type": "object", "properties": {}},
}

# The description states the AXIS, which the old one ("use this for 'why did X move' questions")
# left open. A model reading that called this expecting per-region contributions — visible in its
# own `because` — because the tree is the only decomposition on offer and "why" is unbounded.
# Naming the axis and routing the other question to group_by is describing the tool, not answering
# the question: which slice a change landed in is still the model's to work out.
_DECOMPOSE_CHANGE = {
    "name": "decompose_change",
    "description": ("Attribute a metric's change between two periods to the metrics that COMPOSE "
                    "it, walking the tree: exact identity contributions (shares sum to 1) plus "
                    "hedged influence candidates. The numbers are computed for you.\n"
                    "This decomposes along the metric tree only — into component metrics, never "
                    "into dimension members. To see WHERE a change landed across a dimension "
                    "(region, platform), call query_metric with group_by instead; to decompose "
                    "WITHIN one scope, pass filters here."),
    "input_schema": {
        "type": "object",
        "properties": {
            "node": {"type": "string",
                     "description": "The metric to decompose — a node from get_metric_tree "
                                    "(default: the root)."},
            # Enumerated for the same reason `period` is on query_metric: a free string invited a
            # date, the model passed "2026-06-29", and the run lost a turn to `unknown period`.
            # It is not offering less — this tool never took dates — it is saying so in the schema
            # instead of in an error message.
            "period_a": {"type": "string", "enum": list(NAMED_PERIODS),
                         "description": "Baseline period (default prev_week)."},
            "period_b": {"type": "string", "enum": list(NAMED_PERIODS),
                         "description": "Comparison period (default last_week)."},
            "filters": {"type": "object", "additionalProperties": True,
                        "description": "Restrict the WHOLE decomposition to one scope, e.g. "
                                       "{\"region\": \"EMEA\"} to decompose EMEA on its own. "
                                       "Every node is computed inside that scope."},
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
    """The numbers a governed query reported, one per row, each with the row that produced it:
    `[(label, value), …]`. The measure is the `value` column the compiler always aliases to.

    Reading every numeric cell of every row instead loses which cell IS the measure, and the
    checks downstream take the first one — so a breakdown handed them its first group's number
    rather than the group the answer came from, and a numeric dimension member could pass for
    a governed result. No `value` column means nothing verifiable came back, which fails the
    provenance check closed rather than silently checking the wrong number.

    The label is the row's other columns joined — `paid_search`, or `2026-06-12/ios` for a
    grouped time series — so a claim can cite the row it read instead of the whole result.
    A single unnamed value labels as the empty string."""
    if "value" not in cols:
        return []
    i = cols.index("value")
    keys = [k for k in range(len(cols)) if k != i]
    out = []
    for r in rows:
        if not isinstance(r[i], (int, float)) or isinstance(r[i], bool):
            continue
        out.append(("/".join(str(r[k]) for k in keys), float(r[i])))
    return out


# What the model reads first, per verdict. NOT_ENCODED and UNKNOWN both used to render as "NO",
# which is the difference between "we looked and found nothing" and "we have nowhere to look".
_CAUSAL_WORD = {
    Causality.PROVEN: "YES",
    Causality.CORRELATIONAL: "CORRELATIONAL",
    Causality.NOT_ENCODED: "NOT ENCODED",
    Causality.UNKNOWN: "UNKNOWN",
}


def _verdict(ok: bool, detail: str) -> str:
    return ("YES — " if ok else "NO — ") + detail


def _get_schema(tb, args) -> ToolResult:
    return ToolResult(schema_text(tb.con, capabilities(tb.rung).star, getattr(tb, "schema", None)))


def _describe_table(tb, args) -> ToolResult:
    return ToolResult(describe_table(tb.con, args["table"], capabilities(tb.rung).star,
                                     getattr(tb, "schema", None)))


def _run_sql(tb, args) -> ToolResult:
    cols, rows = run_query(tb.con, args["query"], schema=getattr(tb, "schema", None))
    return ToolResult(_fmt_rows(cols, rows))


def _list_metrics(tb, args) -> ToolResult:
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


def _time_scope_line(args) -> str:
    """One line naming the date range the query actually covered, on every result unconditionally.

    A tool that resolves an argument must say what it resolved to: `period=last_month` quietly
    meaning June is invisible in a bare row of numbers, and a model that mis-picked the period has
    no signal to catch itself on. This is contract-level disclosure (what did MY arguments mean),
    distinct from the transparency guardrail (what SQL ran, what scope the layer covered)."""
    from warehouse.config import resolve_period
    period, start, end = args.get("period"), args.get("start"), args.get("end")
    if period:
        try:
            s, e = resolve_period(period)
        except ValueError:
            return ""                          # the layer will raise the real error
        return f"time scope: period={period} -> {s}..{e}\n" if s else "time scope: all data\n"
    if start or end:
        return f"time scope: {start or 'open'}..{end or 'open'}\n"
    return "time scope: none given (a stock metric reads its latest snapshot)\n"


def _check_metric_exists(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.metric_exists(args["term"])))


def _define_measure(tb, args) -> ToolResult:
    """Author + verify + compute a definition for an ungoverned measure (agent/define.py). Returns the
    computed value with its definition disclosed, an uninstrumented refusal, or a could-not-define —
    the agent then serves the value (stating the definition) or refuses."""
    ont, model = getattr(tb, "ontology", None), getattr(tb, "model", None)
    if ont is None or model is None:
        return ToolResult("UNKNOWN — define_measure is unavailable in this configuration.")
    from .define import define_measure
    d = define_measure(model, str(args.get("measure") or ""), ont, tb.semantic)
    if d.outcome == "refuse":
        return ToolResult(f"UNINSTRUMENTED — {d.disclosure} `refuse` with reason `uninstrumented`.")
    if d.outcome == "gave_up":
        return ToolResult(f"COULD NOT DEFINE — {d.disclosure} Consider `clarify` or `refuse`.")
    val = d.value if d.value is not None else f"{len(d.rows)} rows: {list(d.rows)[:8]}"
    msg = f"COMPUTED (tier={d.tier}). value = {val}\nDEFINITION: {d.disclosure}"
    if d.aptness and d.aptness != "apt":
        msg += (f"\nAPTNESS {d.aptness.upper()}: {d.aptness_note} — disclose this alternative reading, "
                f"or `clarify` if it changes the answer.")
    msg += "\nServe this via `answer`, STATING the definition; the number rests on it."
    return ToolResult(msg)


def _check_answerability(tb, args) -> ToolResult:
    """Ground a measure against the closed-world marts graph and return the THREE-WAY verdict with the
    reason code it implies — concise and definitive, not the raw graph.

    The model decomposes the measure into ingredient nodes (interpretation); MartsOntology.verify()
    decides existence and joinability (deterministic). This is the answer check_metric_exists could
    not give: it distinguishes 'computable but ungoverned' (refuse `no_governed_definition`) from
    'not captured' (refuse `uninstrumented`) — the collapse that made retention pick the wrong reason.
    Returning a short verdict rather than the whole graph keeps the agent from over-exploring and
    running out of turns."""
    ont, model = getattr(tb, "ontology", None), getattr(tb, "model", None)
    if ont is None or model is None:
        return ToolResult("UNKNOWN — no marts graph is available here; fall back to list_metrics and "
                          "the schema to judge answerability.")
    from .guardrails.classify import answerability_via_graph
    measure = str(args.get("measure") or "").strip()
    v = answerability_via_graph(model, measure, ont)
    if v["verdict"] == "governed":
        return ToolResult(f"GOVERNED — {measure!r} maps to the governed metric `{v['governed_metric']}`. "
                          "Answer with it (apply any segment or period as a filter).")
    if v["verdict"] == "computable":
        basis = v.get("basis") or "attributes and measures the graph captures"
        # ROUTE to define_measure when it is offered: a computable measure needs a DEFINITION, and
        # authoring one (grounded, executed by construction, aptness-challenged, disclosed) is more
        # reliable than hand-rolling run_sql — which is how a computable measure came to be served as
        # a raw metric total. The deterministic verdict steers the agent to the authoring tool.
        if getattr(tb.g, "spec_authoring", False) and getattr(tb, "model", None) is not None:
            return ToolResult(
                f"COMPUTABLE — {measure!r} has NO governed metric, but the data IS captured ({basis}). "
                f"Call define_measure(measure={measure!r}) to author a VERIFIED definition and compute "
                f"it — do NOT hand-roll run_sql and do NOT serve a raw metric total. If it still "
                f"cannot be defined, `refuse` with reason `no_governed_definition`.")
        return ToolResult(f"COMPUTABLE — {measure!r} has NO governed metric, but the data IS captured "
                          f"({basis}). There is no governed definition. Under strict governance, "
                          "`refuse` with reason `no_governed_definition` — NOT `uninstrumented` (the "
                          "data is there) and NOT `other`; under a transparent policy, compute it and "
                          "STATE the definition you used.")
    miss = v.get("missing") or "the concept it needs is not captured by the warehouse"
    return ToolResult(f"UNINSTRUMENTED — {measure!r} is NOT captured: {miss}. `refuse` with reason "
                      "`uninstrumented`.")


def _check_coverage(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.in_coverage(
        args.get("start"), args.get("end"), args.get("region"), args.get("country"))))


def _check_segment_defined(tb, args) -> ToolResult:
    return ToolResult(_verdict(*tb.semantic.segment_defined(args["term"])))


def _check_causal_evidence(tb, args) -> ToolResult:
    if tb.tree is None:
        # UNKNOWN, not NO. Without a tree this configuration cannot tell whether a causal link
        # exists — and it said "NO — no causal evidence is encoded", which is a claim about the
        # world. A model reading NO concludes there is no link and refuses `no_causal_evidence`,
        # a reason it has no grounds for. The absence of the instrument is not evidence of
        # absence, and a check that cannot run must say so rather than answer.
        return ToolResult("UNKNOWN — there is no metric tree at this rung, so causal links "
                          "cannot be checked here. This is not evidence that no link exists: "
                          "you cannot tell either way, so do not refuse for no_causal_evidence "
                          "on the strength of this answer.")
    verdict, detail = tb.tree.causal_evidence(args.get("driver"), args.get("outcome"))
    # The LEADING WORD is what the model acts on, so it carries the verdict rather than a
    # yes/no cast from it. `NO — weak, correlational evidence — edge ... [confidence: medium]`
    # told the model the opposite of the finding in its own first word.
    return ToolResult(f"{_CAUSAL_WORD[verdict]} — {detail}")


def _get_metric_tree(tb, args) -> ToolResult:
    return ToolResult(tb.tree.describe())


def _labelled(pairs) -> dict:
    """Split `[(label, value), …]` into the two parallel lists a ToolResult carries."""
    return {"values": [v for _, v in pairs], "labels": [k for k, _ in pairs]}


def _decomposition_values(out: dict) -> list:
    """Every number the tree COMPUTED for this decomposition, as governed values.

    They are governed in the same sense a query_metric result is: the tree derived each one
    deterministically from governed metrics, by an identity it declares. Recording them is what
    makes them addressable — the loop hands any result carrying values a handle, so an answer can
    cite the decomposition it read instead of the harness matching numbers back to it.

    Without this, everything the tree produced was invisible to provenance: `explain_change`
    returned prose-shaped JSON and no values, so a diagnostic answer built on it could not be
    traced by anything, and governed_numbers' predecessor refused all of it as hand-composed.
    The numbers were
    never hand-composed; nothing had written them down.

    Shares and percent changes are included, not just levels. They are the answer to "why did it
    move" — the quantity a diagnosis actually reports — and they are computed by the tree, not by
    the model.
    """
    values: list = []

    def take(d: dict, prefix: str = "") -> None:
        for key in ("value_a", "value_b", "pct_change", "contribution_share"):
            v = d.get(key)
            if isinstance(v, (int, float)):
                values.append((prefix + key, float(v)))

    # The root's own figures are unprefixed; a child's carry the child's name, so an answer
    # cites `days_per_user.contribution_share` rather than "one of the eighteen numbers in r1".
    take(out)
    for child in out.get("identity_decomposition") or []:
        take(child, str(child.get("child", "")) + ".")
    # Influences are keyed by the child they hang off, and the KEY is part of the address:
    # `active_users.new_signups.pct_change` says which branch the driver belongs to, which is the
    # whole point of reporting them per child. A flat `new_signups.pct_change` would lose it.
    for parent, group in (out.get("influences") or {}).items():
        for child in group:
            take(child, f"{parent}.{child.get('child', '')}."
                        if parent != out.get("node") else f"{child.get('child', '')}.")
    # The tree's OWN conclusions, addressable. They were computed, shown in the JSON, and given no
    # address — so an answer reporting "days per user is the primary driver" had to cite one of
    # the things being ranked, which is a citation that does not support the word "primary".
    for name, entry in (("primary_driver", out.get("primary_driver")),):
        if isinstance(entry, dict):
            take(entry, f"{name}.")
    for c in out.get("offsetting") or []:
        take(c, f"offsetting.{c.get('child', '')}.")
    return values


def _decompose_change(tb, args) -> ToolResult:
    # The tool is `decompose_change`; the tree METHOD keeps its own name. It returns more than the
    # tool need ever expose (the judge's evidence is built from it in guardrails/after.py), so the
    # two names are not required to agree.
    out = tb.tree.explain_change(node=args.get("node"),
                                 period_a=args.get("period_a", "prev_week"),
                                 period_b=args.get("period_b", "last_week"),
                                 filters=args.get("filters"))
    return ToolResult(json.dumps(out, default=str, indent=2),
                      **_labelled(_decomposition_values(out)))


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
    Tool(_SHOW_ONTOLOGY, _show_metric_ontology),
    Tool(_QUERY_METRIC, _query_metric),
    Tool(_CHECK_METRIC, _check_metric_exists),
    Tool(_CHECK_ANSWERABILITY, _check_answerability),
    Tool(_DEFINE_MEASURE, _define_measure),
    Tool(_CHECK_COVERAGE, _check_coverage),
    Tool(_CHECK_SEGMENT, _check_segment_defined),
    Tool(_CHECK_CAUSAL, _check_causal_evidence),
    Tool(_GET_METRIC_TREE, _get_metric_tree),
    Tool(_DECOMPOSE_CHANGE, _decompose_change),
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
                 tree: MetricTree | None = None, guardrails: GuardrailSet | None = None,
                 protocol: Protocol | None = None, schema: str | None = None, ontology=None):
        self.con = con
        self.rung = rung
        # The complete marts graph, when the grounding built one. `check_answerability` reads it to
        # ground a measure upfront; None leaves that tool a no-op fallback and the gate on its old path.
        self.ontology = ontology
        # The run's model, injected by run_agent. `check_answerability` uses it to DECOMPOSE the
        # measure (the interpretation half) before the graph verifies it; None -> the tool falls back.
        self.model = None
        # The warehouse schema this agent may read, when the study gives its arm one. None means
        # the shared warehouse — every study before per-arm environments existed. When it is set,
        # `run_sql` refuses any statement naming another schema: `search_path` hides the others,
        # and only this forbids them.
        self.schema = schema
        # GuardrailSet is the one primitive: which reliability guardrails are on. A ladder preset
        # (LADDER[n]) and an ablation cell are both just a GuardrailSet set; every guardrail below reads
        # from it, so a cell is expressible and self-describing. Default R1 (abstention).
        self.g = guardrails if guardrails is not None else LADDER[1]
        # What the answer must DECLARE — a peer of the guardrail set, not a part of it. It gates
        # fields on the answer tool the way the set gates whole tools.
        self.p = protocol if protocol is not None else Protocol()
        self.semantic = semantic
        self.tree = tree

    def specs(self, terminal_only: bool = False, record=None) -> list[dict]:
        """The action space for this configuration — assembled by the ACTION_SPACE guardrails,
        which is where the ladder is legible."""
        return action_space.offer(TOOLS, self.rung, self.g, self.semantic, self.tree,
                                  protocol=self.p, terminal_only=terminal_only, record=record,
                                  ontology=self.ontology)

    def dispatch(self, name: str, args: dict) -> ToolResult:
        """Run one tool. Errors come back as the DB/semantic message rather than as exceptions,
        so the model is told what went wrong and can correct itself — a crashed run is a lost
        measurement, which is worse than a wrong answer because it looks like neither."""
        tool = TOOLS.get(name)
        if tool is None or tool.run is None:
            return ToolResult(f"Unknown tool {name!r}.", is_error=True)
        # Every call passes the BEFORE guardrails and every result passes DISCLOSURE, rather than
        # each handler remembering to ask. A tool added later is guarded by existing; for a call
        # with no scope to check both are no-ops.
        acts: list = []
        verdict = before.check(self.semantic, self.g, args, record=acts)
        if not verdict.allowed:
            return ToolResult(verdict.detail, is_error=True, reason=verdict.reason,
                              blocked_by=verdict.guardrail, acts=tuple(acts))
        try:
            result = disclosure.annotate(tool.run(self, args), args, self.semantic, self.g,
                                         record=acts)
            return replace(result, acts=tuple(acts))
        except (QueryError, SemanticError, TreeError) as exc:
            return ToolResult(f"Error: {exc}", is_error=True, acts=tuple(acts))
        except KeyError as exc:
            return ToolResult(f"Error: missing argument {exc}", is_error=True, acts=tuple(acts))
