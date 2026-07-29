"""Guardrails at position ACTION_SPACE: which tools exist, and how narrow their schemas are.

These are the strongest guardrails available, because they do not judge a request — they remove
the ability to make it. A tool that is not offered cannot be called; a metric that is not in an
enum cannot be named. Nothing the model does can route around them, which is why they can be
proven without ever calling a model. The price is that they cannot express a conditional rule:
the choice is on or off, for the whole run.

This is the one place the action space is assembled. Pushing availability onto each tool would
scatter the ladder across fourteen declarations, and the ladder is the experiment — it has to be
readable in one screen.

The tool registry arrives as an argument rather than an import, so the guardrails package never
depends on the tools it gates.
"""

from __future__ import annotations

from ..rungs import capabilities
from . import GOVERNED_TOOLS, Position, note

_CHECK_TOOLS = ("check_metric_exists", "check_coverage",
                "check_segment_defined", "check_causal_evidence")

# The field is named `because` rather than `purpose` or `intent` because the name is itself a
# prompt: "because" invites the reason a call is being made, where a formal noun invites a restated
# label ("regional analysis"). What we want recorded is the sub-question, in the analyst's words.
_BECAUSE = {
    "type": "string",
    "description": "One line: what you are trying to establish with this call, in plain words "
                   "(e.g. \"check whether the drop is uniform across regions or concentrated in "
                   "one\"). It records your reasoning; it does not affect the result.",
}


def with_purpose(base: dict) -> dict:
    """A tool schema that also offers `because` — the caller's own account of what it is for.

    Additive and inert by construction: the field is optional, and no handler, guardrail or
    compiler reads it (`agent/tools.py` takes its arguments by name). Omitting it therefore
    produces exactly the run that would have happened without this guardrail, which is what keeps
    a declaration from ever costing coverage.
    """
    props = {**base["input_schema"]["properties"], "because": _BECAUSE}
    return {**base, "input_schema": {**base["input_schema"], "properties": props}}


def offer(tools: dict, rung: int, guardrails, semantic=None, tree=None,
          *, terminal_only: bool = False, record=None) -> list[dict]:
    """The tool schemas this configuration offers the model.

    Two axes decide it, and they are not the same thing: `rung` is grounding — what the agent
    KNOWS, which is the experiment's other variable — and `guardrails` is what it may DO about
    not knowing. A tool can be absent because the rung has no semantic layer to serve it, or
    because a guardrail withdrew it.

    `terminal_only` withdraws every data tool, leaving just the exits. It closes a run that has
    stopped calling tools or is about to hit the iteration cap, so it ends through the typed
    protocol instead of dying as an untyped error row — a lost measurement, not a model
    behaviour. Removing the choice is structural; asking the model nicely is not.
    """
    schema = lambda name: tools[name].schema        # noqa: E731 — a lookup, not a function
    offered: list[dict] = []
    if terminal_only:
        note(record, "(closing)", Position.ACTION_SPACE, "withdrew",
             "every data tool — the run must end through a terminal tool")
    if not terminal_only:
        offered += [schema("get_schema"), schema("describe_table")]
        if guardrails.tool_restriction:
            note(record, "tool_restriction", Position.ACTION_SPACE, "withdrew",
                 "run_sql — every data path is a governed call")
        else:
            offered.append(schema("run_sql"))
        caps = capabilities(rung)
        if caps.semantic:
            offered += [schema("list_metrics"),
                        query_metric_schema(schema("query_metric"), guardrails, semantic, record)]
        if caps.tree:
            offered += [schema("get_metric_tree"),
                        decompose_schema(schema("decompose_change"), guardrails, tree, record)]
        if guardrails.check_tools and semantic is not None:
            offered += [schema(name) for name in _CHECK_TOOLS]
            note(record, "check_tools", Position.ACTION_SPACE, "applied",
                 f"offered {len(_CHECK_TOOLS)} answerability lookups")
    offered.append(answer_schema(schema("answer"), guardrails, semantic, record))
    if guardrails.abstain:
        offered.append(schema("refuse"))
        note(record, "abstain", Position.ACTION_SPACE, "applied", "offered the refuse tool")
    offered.append(schema("clarify"))
    # Applied once over the assembled list rather than at each governed tool: the set of calls
    # that carry a purpose is one fact about the configuration, and stating it once means adding
    # a third governed tool later cannot leave `because` off it by omission.
    if guardrails.declared_purpose:
        offered = [with_purpose(s) if s["name"] in GOVERNED_TOOLS else s for s in offered]
        note(record, "declared_purpose", Position.ACTION_SPACE, "applied",
             f"governed calls gained `because` ({', '.join(GOVERNED_TOOLS)})")
    return offered


def query_metric_schema(base: dict, guardrails, semantic, record=None) -> dict:
    """Narrow the governed-query tool to what this configuration allows.

    Under the coverage check `metric` becomes a closed menu of the catalog, so the model cannot
    even NAME a metric that does not exist — a stronger guarantee than refusing one afterwards,
    and one the provider enforces for us. The governed `segment` enum is offered whenever the
    layer defines any, since a named segment is part of the vocabulary rather than a guardrail.
    """
    if semantic is None:
        return base
    props = dict(base["input_schema"]["properties"])
    if guardrails.coverage_check:
        props["metric"] = {**props["metric"], "enum": list(semantic.metrics)}
        note(record, "coverage_check", Position.ACTION_SPACE, "narrowed",
             f"metric closed to the {len(semantic.metrics)}-metric catalog")
    segments = semantic.segment_names()
    if segments:
        props["segment"] = {
            "type": "string", "enum": segments,
            "description": "A governed named segment / reusable filter (see list_metrics), "
                           "e.g. real_acquisition to exclude test channels."}
    return {**base, "input_schema": {**base["input_schema"], "properties": props}}


def decompose_schema(base: dict, guardrails, tree, record=None) -> dict:
    """Close `node` to the tree's own nodes, for the same reason `metric` is closed to the catalog.

    A node name that does not exist costs a whole turn: the model guessed `value_moments` (a metric)
    where the node is `weekly_value_moments`, read the error, and corrected — on three diagnostic
    runs out of three. An enum makes the mistake unmakeable rather than recoverable, which is what
    an ACTION_SPACE guardrail is for.

    Gated on the coverage check because it IS that guardrail's mechanism, one level along: close the
    vocabulary to what the governed layer defines. Ungated it would be an unattributable improvement
    to every cell, which is the one thing an ablation must not contain.
    """
    if tree is None or not guardrails.coverage_check:
        return base
    props = {**base["input_schema"]["properties"],
             "node": {**base["input_schema"]["properties"]["node"], "enum": list(tree.nodes)}}
    note(record, "coverage_check", Position.ACTION_SPACE, "narrowed",
         f"node closed to the {len(tree.nodes)} tree nodes")
    return {**base, "input_schema": {**base["input_schema"], "properties": props}}


def answer_schema(base: dict, guardrails, semantic, record=None) -> dict:
    """Add typed provenance to the answer tool when the served number must be checked.

    `value` is the number as a number, so the AFTER guardrails read what was served instead of
    parsing it back out of prose, and `source_metric` names the definition it came from — the
    same closed menu as the query tool. Both are the model's own typed claims, which are more
    reliable than anything reconstructed from the answer text.

    A prose or diagnostic answer leaves `value` unset and the numeric checks stand down rather
    than force a spec onto words. That is a deliberate hole, and the loop closes it from the
    other side: an answer that IS a number is recovered and checked even when the field is
    empty (see numbers.bare_number).
    """
    if not (guardrails.governed_numbers and semantic is not None):
        return base
    props = dict(base["input_schema"]["properties"])
    props["value"] = {
        "type": "number",
        "description": "If your answer is a single number, repeat it here as a number "
                       "(not text). Leave it out for a non-numeric answer (an assessment, "
                       "a driver, a list) — the value check then does not apply."}
    note(record, "governed_numbers", Position.ACTION_SPACE, "narrowed",
         "answer gained typed `value` + `source_metric`")
    props["source_metric"] = {
        "type": "string", "enum": list(semantic.metrics),
        "description": "If `value` came from a governed metric, name that metric (as passed "
                       "to query_metric). Omit for a derived or non-metric answer."}
    props["source_result"] = {
        "type": "string",
        "description": "The handle of the result you are reporting — every governed result is "
                       "printed with one, like [r2]. Give just the handle (r2). This says WHICH "
                       "query your number came from, so it does not have to be guessed by "
                       "matching numbers."}
    return {**base, "input_schema": {**base["input_schema"], "properties": props}}
