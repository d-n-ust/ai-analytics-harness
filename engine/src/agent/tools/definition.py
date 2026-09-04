"""The definition tool: author + verify + compute an ungoverned measure (spec pipeline).

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json  # noqa: F401
from dataclasses import replace  # noqa: F401

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS  # noqa: F401
from warehouse import (  # noqa: F401,E501
    NAMED_PERIODS,
    TIME_GRAINS,
    QueryError,
    describe_table,
    run_query,
    schema_text,
)

from ..core.conversation import ToolResult  # noqa: F401
from ..core.outcomes import REASON_MEANINGS, REFUSAL_REASONS  # noqa: F401
from ..core.protocol import Protocol  # noqa: F401
from ..core.rungs import capabilities  # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401

_DEFINE_MEASURE = {
    "name": "define_measure",
    "description": "Author a VERIFIED definition for a measure that has no governed metric, and "
                   "compute it. The definition is grounded in the graph, checked for validity, "
                   "executed by construction, and challenged for aptness; the result comes back with "
                   "the definition disclosed. Use this instead of raw SQL for an ungoverned measure "
                   "(a retention/cohort calculation, a custom ratio) AND for any answer that "
                   "COMBINES governed metrics — a ratio, share, or per-unit figure. Authoring the "
                   "combination makes the operation a declared, checked fact; dividing figures by "
                   "hand in the answer does not.",
    "input_schema": {"type": "object", "properties": {
        "measure": {"type": "string",
                    "description": "The measure to define and compute, in the question's own words "
                                   "(e.g. '90-day retention by acquisition channel')."}},
        "required": ["measure"]},
}


def _spec_evidence(spec) -> tuple:
    """The typed evidence records a spec's leaves stand for. A metric/derived leaf IS a governed
    evaluation — (metric, filters, period) — and registers as one, so every trace-reading gate
    treats it exactly like a query_metric call. A raw leaf registers as raw SQL: visible to
    provenance, never claiming governed status."""
    if spec.kind == "metric":
        return ({"kind": "governed", "metric": spec.metric,
                 "args": {"filters": dict(spec.filters) or None,
                          "period": spec.period or None}},)
    if spec.kind == "derived":
        return tuple(e for s in spec.inputs for e in _spec_evidence(s))
    if spec.kind == "raw":
        return ({"kind": "raw", "sql": spec.sql},)
    return ()


def _define_measure(tb, args) -> ToolResult:
    """Author + verify + compute a definition for an ungoverned measure (agent/define.py). Returns the
    computed value with its definition disclosed, an uninstrumented refusal, or a could-not-define —
    the agent then serves the value (stating the definition) or refuses."""
    ont, model = getattr(tb, "ontology", None), getattr(tb, "model", None)
    if ont is None or model is None:
        return ToolResult("UNKNOWN — define_measure is unavailable in this configuration.")
    # FAILED-RETRY DISCIPLINE (symmetric to the anti-shopping line on COMPUTED). A gave_up is the
    # authoring pipeline's verdict that this measure cannot be defined; the agent re-called the
    # tool up to four times on a reworded measure (time_to_first: 27 model calls), each internally
    # exhausting its own retries. After two could-not-define results in a run, the authoring
    # answer will not change — the third call is terminal: refuse or clarify, do not re-author.
    prior_giveups = getattr(tb, "_define_giveups", 0)
    if prior_giveups >= 2:
        return ToolResult(
            "COULD NOT DEFINE (and define_measure has already failed twice this run) — the "
            "authoring pipeline cannot produce a valid definition for this measure. Do NOT call "
            "define_measure again; `refuse` (reason `no_governed_definition`) or `clarify`.")
    from ..runtime.define import define_measure
    d = define_measure(model, str(args.get("measure") or ""), ont, tb.semantic,
                       verifier_model=getattr(tb, "verifier_model", None))
    if d.outcome == "refuse":
        return ToolResult(f"UNINSTRUMENTED — {d.disclosure} `refuse` with reason `uninstrumented`.")
    if d.outcome == "gave_up":
        tb._define_giveups = prior_giveups + 1
        tail = (" define_measure has now failed twice; do not call it again — `refuse` or "
                "`clarify`." if tb._define_giveups >= 2 else " Consider `clarify` or `refuse`.")
        return ToolResult(f"COULD NOT DEFINE — {d.disclosure}{tail}")
    # Present the computed result so the agent can answer FROM IT directly — a scalar, or the rows
    # laid out (already ordered by the definition's SQL) so "which is best/highest" is readable
    # without a re-query. The recompute-with-run_sql wrinkle was the rows arriving as a bare list.
    if d.value is not None:
        result = f"value = {d.value}"
    else:
        rows = "\n  ".join(", ".join(str(c) for c in r) for r in d.rows[:20])
        result = f"result rows ({len(d.rows)}, in the definition's order):\n  {rows}"
    # "do NOT re-define" closes the loop "do NOT recompute" left open: a scrutinized run called
    # define_measure four times, got four slightly different COMPUTED readings, and refused —
    # shopping for a definition that would come back governed. Re-defining changes the reading,
    # never the status.
    msg = (f"COMPUTED (tier={d.tier}). This IS the computed answer — answer FROM this directly, "
           f"stating the definition; do NOT recompute with run_sql and do NOT call "
           f"define_measure again (a re-definition changes the reading, never its governance "
           f"status).\n{result}\n"
           f"DEFINITION: {d.disclosure}")
    if d.aptness and d.aptness != "apt":
        # THE FOURTH ACTION at the definition level: a contested definition is served like a
        # contested metric — the reader holds BOTH readings, never a silent pick. The alternative
        # is one more define_measure call away; a reading that cannot be authored is disclosed in
        # words.
        msg += (f"\nAPTNESS {d.aptness.upper()}: {d.aptness_note}\n"
                f"Do NOT serve this figure alone. Either (a) call define_measure once more with "
                f"the alternative reading and serve BOTH figures, each labelled with its "
                f"definition, or (b) serve this figure while STATING the alternative reading and "
                f"why your definition was chosen — or `clarify` if the choice changes the answer "
                f"materially and you cannot compute both.")
    # The step carries WHAT was computed, typed: values for provenance/citation, evidence records
    # for the trace-reading gates. Without these the define path was a second data path the
    # repair chain could not see.
    values = [d.value] if d.value is not None else [
        c for r in d.rows[:50] for c in r if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return ToolResult(msg, values=values or None,
                      labels=[""] * len(values) if values else None,
                      evidence=_spec_evidence(d.spec))


__all__ = ['_DEFINE_MEASURE', '_define_measure', '_spec_evidence']
