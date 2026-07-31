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

from ..protocol import Protocol
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
          *, protocol: Protocol | None = None, terminal_only: bool = False,
          record=None) -> list[dict]:
    """The tool schemas this configuration offers the model.

    Three axes decide it, and they are not the same thing: `rung` is grounding — what the agent
    KNOWS — `guardrails` is what it may DO about not knowing, and `protocol` is what it must
    DECLARE about what it did. A tool can be absent because the rung has no semantic layer to
    serve it, or because a guardrail withdrew it; a FIELD can be absent because the protocol did
    not ask for it.

    `terminal_only` withdraws every data tool, leaving just the exits. It closes a run that has
    stopped calling tools or is about to hit the iteration cap, so it ends through the typed
    protocol instead of dying as an untyped error row — a lost measurement, not a model
    behaviour. Removing the choice is structural; asking the model nicely is not.
    """
    schema = lambda name: tools[name].schema        # noqa: E731 — a lookup, not a function
    protocol = protocol or Protocol()
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
    offered.append(answer_schema(schema("answer"), guardrails, semantic, protocol, record))
    if guardrails.abstain:
        offered.append(schema("refuse"))
        note(record, "abstain", Position.ACTION_SPACE, "applied", "offered the refuse tool")
    offered.append(schema("clarify"))
    # Applied once over the assembled list rather than at each governed tool: the set of calls
    # that carry a purpose is one fact about the configuration, and stating it once means adding
    # a third governed tool later cannot leave `because` off it by omission.
    if protocol.purpose:
        offered = [with_purpose(s) if s["name"] in GOVERNED_TOOLS else s for s in offered]
        note(record, "purpose", Position.ACTION_SPACE, "applied",
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


def answer_schema(base: dict, guardrails, semantic, protocol=None, record=None) -> dict:
    """Add typed provenance to the answer tool when the served number must be checked.

    `value` is the number as a number, so the AFTER guardrails read what was served instead of
    parsing it back out of prose, and `source_metric` names the definition it came from — the
    same closed menu as the query tool. Both are the model's own typed claims, which are more
    reliable than anything reconstructed from the answer text.

    A prose or diagnostic answer leaves `value` unset and the numeric checks stand down rather
    than force a spec onto words. That is a deliberate hole, and the loop closes it from the
    other side: an answer that IS a number is recovered and checked even when the field is
    empty (see numbers.bare_number).

    `sources` is a LIST because a comparison has two operands and one slot could not hold them.
    While it could not, the comparison branch of `account_for` had nothing to look up and had to
    search instead — every ordered pair of the metric's values, times three relations. One run
    put sixteen `active_users` values in that pool, so ~1,440 candidate numbers, and a
    hand-composed DAU/WAU ratio matched one of them by coincidence. Naming the operands turns
    the search back into a lookup.
    """
    protocol = protocol or Protocol()
    if semantic is None or not (guardrails.governed_numbers or protocol.claims):
        return base
    props = dict(base["input_schema"]["properties"])
    if not guardrails.governed_numbers:
        # Claims without governed_numbers: the declaration is offered, the numeric checks are not.
        # This is the cell the whole restructure exists for — declaring at a LOW guardrail level,
        # where the agent is wrong often enough for a difference to show. Citations resolve
        # against handles, which any governed RESULT carries from rung 3 up, so nothing here
        # needs the R7 checks.
        return _with_claims(base, props, protocol, record)
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
    props["sources"] = {
        "type": "array", "items": {"type": "string"},
        "description": "The handle(s) of the result(s) your number comes from — every governed "
                       "result is printed with one, like [r2]. Give just the handles (['r2']). "
                       "A COMPARISON names both: a difference, ratio or percent change of r3 "
                       "against r4 is ['r3','r4']. This says WHICH queries your number came "
                       "from, so it is never guessed by matching numbers."}

    return _with_claims(base, props, protocol, record)


def _with_claims(base: dict, props: dict, protocol, record=None) -> dict:
    """The `claims` block, when the protocol asks for it.

    Separated from the provenance fields because they answer different questions and are switched
    on by different axes: `value`/`source_metric`/`sources` exist so the R7 checks can read what
    was served, and `claims` exists so every OTHER assertion in the answer is accountable. They
    shared a gate only because they arrived together."""
    # The served number is one assertion among several, and the rest have never been checked at
    # all. `claims` asks for each of them, addressed to a VALUE rather than to a result —
    # `r1:days_per_user.pct_change`, not "somewhere in r1".
    if protocol.claims:
        props["claims"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string",
                             "description": "One assertion your answer makes, in plain words."},
                    "sources": {
                        "type": "array", "items": {"type": "string"},
                        "description": "The governed value(s) this assertion rests on, as "
                                       "handle:field — e.g. r1:days_per_user.pct_change, or "
                                       "r2:paid_search for one row of a breakdown."},
                    "premises": {
                        "type": "array", "items": {"type": "string"},
                        "description": "If this assertion is a CONCLUSION drawn from earlier "
                                       "claims rather than a figure read off a result, name those "
                                       "claims instead of sources — ['c2','c3','c4']. Claims are "
                                       "numbered in the order you list them, and a conclusion may "
                                       "only cite claims before it."},
                    "value": {"type": "number",
                              "description": "The figure this assertion states, if it states one."},
                },
                "required": ["text"],
            },
            "description": "Break your answer into the separate assertions it makes — one per "
                           "figure or judgement — each naming the governed value it rests on. "
                           "An answer that reports five numbers makes five assertions.",
        }
        # REQUIRED, not optional. Left optional, 6 of 73 answers simply omitted it and nothing
        # objected — an empty field passing silently on the one rung whose entire purpose is that
        # field. An answer with nothing to declare can send one claim and no value; an answer that
        # sends none has not been measured, and "not measured" read as "nothing to measure".
        base = {**base, "input_schema": {**base["input_schema"],
                                         "required": [*base["input_schema"].get("required", []),
                                                      "claims"]}}
        note(record, "claims", Position.ACTION_SPACE, "applied",
             "answer gained a REQUIRED `claims` — each assertion names the value it rests on")

    return {**base, "input_schema": {**base["input_schema"], "properties": props}}
