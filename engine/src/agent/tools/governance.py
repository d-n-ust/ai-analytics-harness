"""The governance tools: answerability, coverage, segment and causal evidence.

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
from ._shared import _verdict                                                # noqa: F401


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


_CHECK_COVERAGE = {
    "name": "check_coverage",
    "description": "Produce citable evidence about data coverage for a period (optionally one "
                   "region or country). Coverage is ALREADY ENFORCED on every query — an "
                   "out-of-range query_metric is refused with the reason — so do NOT call this "
                   "before an ordinary query. Call it only when you need coverage as evidence: "
                   "before refusing out_of_coverage, or when a query was blocked and you are "
                   "deciding what IS answerable.",
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


_CAUSAL_WORD = {
    Causality.PROVEN: "YES",
    Causality.CORRELATIONAL: "CORRELATIONAL",
    Causality.NOT_ENCODED: "NOT ENCODED",
    Causality.UNKNOWN: "UNKNOWN",
}




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
    from ..guardrails.classify import answerability_via_graph
    measure = str(args.get("measure") or "").strip()
    v = answerability_via_graph(model, measure, ont)
    # The verdict is a DECISION, recorded as typed evidence so downstream gates can read it
    # deterministically: the measure-substitution judge stands down when the question's measure
    # was already resolved to the metric the answer serves — one semantic judgement per fact,
    # not two judges asked the same question in different words.
    resolution = ({"kind": "resolution", "verdict": v["verdict"],
                   "metric": v.get("governed_metric") or "", "measure": measure},)
    if v["verdict"] == "governed":
        return ToolResult(f"GOVERNED — {measure!r} maps to the governed metric `{v['governed_metric']}`. "
                          "Answer with it (apply any segment or period as a filter).",
                          evidence=resolution)
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
                      "`uninstrumented`.", evidence=resolution)


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


__all__ = ['_CAUSAL_WORD', '_CHECK_ANSWERABILITY', '_CHECK_CAUSAL', '_CHECK_COVERAGE', '_CHECK_SEGMENT', '_check_answerability', '_check_causal_evidence', '_check_coverage', '_check_segment_defined', '_verdict']
