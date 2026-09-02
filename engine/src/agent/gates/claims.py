"""The claims family: citations that resolve, constraints that survive, clarify
candidates that ground.

Extracted from loop.py (refactor phase 3). Every gate keeps its exact behaviour and signature —
`self` became the explicit `run` parameter, and cross-references go through the run's delegator
methods, so in-family and cross-family calls read identically. Gates return a ToolResult to hand
the answer back, or None (standing down, or after constructing into the exit call in place).
"""
from __future__ import annotations

import re                                                                   # noqa: F401

import evidence as claim_audit                                              # noqa: F401

from ..core import trace
from ..core.conversation import Conversation, ToolCall, ToolResult, Turn, Usage  # noqa: F401
from ..guardrails import Act, Position, after, before                       # noqa: F401
from ..guardrails import classify as _classify                              # noqa: F401
from ..guardrails import grounding_check as _grounding                      # noqa: F401
from ..core.numbers import bare_number, parse_numbers                            # noqa: F401
from ..core.outcomes import TERMINAL_TOOLS, Answer, declared_handles             # noqa: F401
from ..core.tool_args import AnswerArgs, ClarifyArgs, RefuseArgs                 # noqa: F401
from ._common import GRACE, MAX_CORRECTIONS                                 # noqa: F401

_COMPOSE = trace.COMPOSE
_leaf = trace.leaf
_as_number = trace.as_number
_reported = trace.reported
_scalar = trace.scalar

# How much of a broken claim's text a repair message carries back.
_REPAIR_TEXT = 200


def malformed_claims(run, exit_call: ToolCall):
    """A citation that names nothing is a MALFORMED CALL, and is handed back as one.

    This is the same treatment `decompose_change` gets for an unknown node: the harness says
    what is wrong, the model corrects, the run continues. Claims were the one thing in the
    loop with no feedback at all — a bad citation was discovered after the run, by us, and the
    model never heard about it. That is why 22% of references named a container rather than a
    number: not because the model could not do better, but because nothing ever told it.

    Only UNRESOLVED is handed back. A reference that points at nothing is objectively broken,
    the way a bad argument is. Whether a claim is mislabelled, or states a figure its evidence
    does not support, are judgements about the ANALYSIS — those stay in the audit, where they
    are measured rather than corrected away.

    Gated on `protocol.repair`, not on `protocol.claims`: asking for an account is a
    treatment and correcting one is an enforcement, and while they shared a flag no cell could
    say which of them moved a number.

    Returns a ToolResult to feed back, or None when there is nothing to correct."""
    if exit_call.name != "answer" or not run.grounding.protocol.repair:
        return None
    declared = tuple(c for c in (exit_call.args.get("claims") or []) if isinstance(c, dict))
    if not declared:
        return None
    audited = claim_audit.audit(declared, run.steps, exit_call.args.get("source_metric"),
                                **run._audit_context())
    broken = [f for f in audited["findings"] if f["unresolved"]]
    if not broken:
        return None
    # Truncated: this is here to be RECOGNISED in the final answer, not re-read. A prefix is
    # enough to tell a surviving sentence from a deleted one, and the full text is already in
    # the turn log for anyone who wants it.
    run.repairs.append({"claims": len(declared),
                         "broken": [{"text": str(f["text"] or "")[:_REPAIR_TEXT],
                                     "cites": list(f["unresolved"])} for f in broken]})
    lines = ["Your answer was not accepted: some claims cite evidence that does not exist."]
    for f in broken:
        for ref in f["unresolved"]:
            lines.append(f"  claim {f['id']} cites {ref!r} — {run._why_unresolved(ref)}")
    lines.append("Re-send the answer with each source naming ONE value, as handle:field. "
                 "Every governed result printed its citable fields on a [cite] line.")
    # A repair is the only guardrail outcome that is neither allowed nor refused, so it needs
    # its own verb. Recorded on the run rather than on a step: the thing being handed back is
    # the ANSWER, which no step owns.
    run.acts.append(Act("repair", str(Position.REPAIR), "handed back",
                         f"{sum(len(f['unresolved']) for f in broken)} citation(s) named "
                         f"nothing; correction {run.claim_retries} of 2").as_dict())
    return ToolResult("\n".join(lines), is_error=True)


def dropped_constraint(run, exit_call):
    """Hand back an answer whose number came from a call that abandoned a restriction the run
    had already asked for.

    WIDENING IS THE CHEAPEST WAY OUT OF A TOOL ERROR, and that is the whole reason this exists.
    Fixing a rejected dimension name needs information the agent does not have; removing the
    filter always works, and the broader query returns a number that looks entirely reasonable.
    The gradient points at answering a different question, and until now nothing pointed back.

    NEITHER SET COMES FROM THE QUESTION. Both are the agent's own calls: what it asked for on
    some attempt, against what the call it served actually carried. So there is no wording to
    parse and the verdict is the same every time for the same trace.

    Keys are compared on their last segment, so `platform` and `activity__platform` are the same
    restriction differently spelled — otherwise correcting a name would look like dropping one.
    A key matching no dimension in the layer is ignored: `is_test_account` names nothing here,
    and an agent cannot be faulted for abandoning a filter that never existed.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not g.constraint_regression:
        return None
    semantic = run.grounding.semantic
    if semantic is None:
        return None
    known = set()
    for metric in getattr(semantic, "metrics", ()):
        try:
            known |= {_leaf(d) for d in semantic.allowed_filters(metric)}
        except Exception:                                               # noqa: BLE001
            continue
    asked, served = set(), set()
    for step in run.steps:
        if step.get("tool") != "query_metric":
            continue
        keys = {_leaf(k) for k in (step.get("args") or {}).get("filters") or {}}
        asked |= keys
        if not step.get("error") and not step.get("blocked_by"):
            served |= keys
    abandoned = sorted((asked - served) & known)
    if not abandoned:
        return None
    run.repairs.append({"dropped": abandoned})
    run.acts.append(Act("constraint_regression", str(Position.REPAIR), "handed back",
                         f"{', '.join(abandoned)} asked for and then dropped; "
                         f"correction {run.claim_retries} of 2").as_dict())
    return ToolResult(
        "Your answer was not accepted: an earlier call asked to restrict this number by "
        + ", ".join(f"`{a}`" for a in abandoned)
        + ", and the call your number came from carries no such restriction — so it answers a "
          "broader question than the one asked. Re-run the governed query with that "
          "restriction, spelling the dimension exactly as `list_metrics` prints it, and answer "
          "from that result. If the layer genuinely cannot express it, `refuse` instead of "
          "widening.", is_error=True)


def ungrounded_candidates(run, exit_call):
    """Hand back a clarification whose options do not each ground to a real object.

    A clarification offers the user a choice between governed readings of the question. Under
    the grounding protocol each option names the object it is computed from, and this verifies
    that object EXISTS — a metric, a table, or a column, in any layer. An option whose
    grounding resolves to nothing is dropped, because it is a reading the system cannot deliver
    however the user answers.

    The count of survivors decides the terminal, and that is the point: two or more grounded
    readings ARE a contest, so the clarification stands. Fewer than two is not — nothing
    grounds it (refuse `uninstrumented`) or exactly one does (answer from it). This is what
    turns the CSAT menu — NPS, CSAT, a rating, none of which the warehouse records — back into
    the refusal it always was, without the mechanism ever judging whether a grounding is the
    RIGHT one for the concept. That relevance judgement stays the model's; existence is all the
    machine decides.
    """
    g = run.grounding.guardrails
    if exit_call.name != "clarify" or not getattr(g, "grounded_candidates", False):
        return None
    semantic = run.grounding.semantic
    con = getattr(run.grounding.toolbox, "con", None)
    schema = getattr(run.grounding.toolbox, "schema", None)
    survived, dropped = [], []
    for cand in ClarifyArgs.of(exit_call.args).candidates:
        # A candidate is a {reading, grounding} pair under this guardrail; tolerate a bare
        # string (its own text is then both the reading and the grounding) so a schema slip
        # degrades to a check rather than a crash.
        reading = cand.get("reading") if isinstance(cand, dict) else str(cand)
        ref = cand.get("grounding") if isinstance(cand, dict) else str(cand)
        (survived if _grounding.resolve_grounding(ref, semantic, con, schema)
         else dropped).append((reading, ref))
    if len(survived) >= 2:
        return None
    run.repairs.append({"ungrounded": [ref for _r, ref in dropped]})
    run.acts.append(Act("grounded_candidates", str(Position.REPAIR), "handed back",
                         f"{len(dropped)} option(s) grounded to nothing, {len(survived)} "
                         f"survived; correction {run.claim_retries} of 2").as_dict())
    lines = ["Your clarification was not accepted: each option you offer the user must ground "
             "to a real object (a metric, a table, or a column) that already exists."]
    lines += [f"  dropped {reading!r} — grounding {ref!r} resolves to nothing in any layer"
              for reading, ref in dropped]
    if not survived:
        lines.append("No option grounds. Nothing in the warehouse measures what was asked, so "
                     "there is no choice to offer — `refuse` with reason `uninstrumented`.")
    else:
        reading, ref = survived[0]
        lines.append(f"Only one option grounds ({ref}), so this is not a contest between "
                     f"definitions. `answer` from it, or `refuse` if it does not truly answer "
                     f"the question.")
    return ToolResult("\n".join(lines), is_error=True)
