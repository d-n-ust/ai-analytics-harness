"""The segment family: does the question restrict to a governed segment, was it applied,
and the shared resolver both guards read.

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


def _resolve_segment(run):
    """The shared segment resolver behind `segment_gate` and `applied_segment`.

    The model names the segment the question restricts to (phrase, dimension, and value if one
    matches); the mechanism decides `linked` — the value is a real member AND is lexically
    anchored in the phrase. One model call, one verification, read by both guards: the gate acts
    when a segment is named but does NOT link (refuse), the application check acts when it DOES
    link but the served call ignored it. Returns None when no segment is named."""
    semantic = run.grounding.semantic
    if semantic is None or not hasattr(semantic, "segment_vocabulary"):
        return None
    vocab = semantic.segment_vocabulary()
    restricts, phrase, dim, value = _classify.segment_named(run.model, run.question, vocab)
    if not restricts or not phrase:
        return None
    members = list(vocab.get(dim, ()))
    # ONE SPAN OF WORDS FEEDS ONE DECISION. When the scope classifier has already consumed a
    # quote as the METRIC choice ("Counting subscriptions that were later refunded" names
    # gross_mrr), the same words are not ALSO a segment restriction — reading them twice made
    # the segment layer apply status='refunded' to an answer the binding check had just
    # verified, overriding 2,754 with the refunded-only 68.9. Deterministic: the named phrase
    # overlapping the consumed quote stands the segment machinery down.
    chose = run._scope_verdict[0] if run._scope_verdict else False
    quote = (run._scope_verdict[2] if run._scope_verdict else "") or ""
    if chose and phrase and (phrase.lower() in quote.lower() or quote.lower() in phrase.lower()):
        run.acts.append(Act("metric_brief", str(Position.REPAIR), "allowed",
                             f"segment phrase {phrase!r} is inside the scope quote that chose "
                             f"the metric — a definition discriminator, not a filter").as_dict())
        return None
    # Membership-only: the model's proposal is trusted for SEMANTIC fit (its superpower) and
    # verified only for EXISTENCE — the value must be a real member. A lexical anchor test here
    # false-refused a correct semantic link ("platform not recorded" -> `unknown`), so it is gone.
    linked = bool(value) and value in set(members)
    return {"phrase": phrase, "dim": dim, "value": value, "members": members, "linked": linked}


def _grounds_literally(run, concept: str, semantic) -> bool:
    """Existence backstop for the grounding resolver: True when the concept LITERALLY matches a
    governed value or metric name (shares a content token). The resolver owns semantic grounding;
    this only stops a refusal when the concept is obviously present ("monthly" wrongly reported
    ungrounded still matches the `monthly` value), so a model slip cannot refuse a real segment.
    It says nothing about semantic-only links, which the resolver already answered by grounding."""
    toks = {t for t in re.findall(r"[a-z0-9]+", str(concept).lower())
            if t not in {"the", "a", "an", "of", "on", "in", "for", "and", "not", "no"}}
    if not toks:
        return False
    pools = [str(v).replace("_", " ") for vals in semantic.segment_vocabulary().values()
             for v in vals] + [m.replace("_", " ") for m in semantic.metrics]
    return any(toks & set(re.findall(r"[a-z0-9]+", pool.lower())) for pool in pools)


def segment_gate(run, exit_call):
    """Refuse an answer whose question names a concept the ONTOLOGY does not contain.

    The full-ontology grounding gate. The substitution the ontology tool could not stop —
    "spend on TikTok ads" served `paid_search`'s number — is a grounding failure: "TikTok" has
    no referent in the layer, so the question is unanswerable. `classify.ground_question` gives
    the model the whole ontology and asks whether every concept grounds, resolving by MEANING
    ('not recorded' -> `unknown`, 'real acquisition channels' -> the `acquisition_spend` metric,
    'TikTok' -> nothing). The model owns the semantics; this verifies only that the concept it
    calls ungrounded is genuinely absent (`_grounds_literally`) before refusing on its word, and
    names the governed siblings so the refusal is legible.

    Fires only when a concept does not ground AND a number was served; an answerable question, a
    grounded concept, or a refusal is untouched, and the resolver defaults to answerable on any
    doubt — so a false refusal needs both a clear grounding miss and a served number."""
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "segment_gate", False):
        return None
    semantic = run.grounding.semantic
    if semantic is None or not hasattr(semantic, "ontology_text"):
        return None
    answerable, concept, dim = _classify.ground_question(
        run.model, run.question, semantic.ontology_text())
    if answerable or not concept or run._grounds_literally(concept, semantic):
        return None
    # Scope to a VALUE-level miss: the concept names a value of a real segment dimension the
    # layer lacks (TikTok as a channel), which `ungoverned_dimension_value` describes. An
    # ungrounded METRIC or MEASURE (dim empty — "time per category", "CSAT") is an absent-measure
    # miss that `grounded_measure` owns and refuses as `uninstrumented`; the gate steering it to
    # `ungoverned_dimension_value` only mis-types a refusal that is already correct.
    vocab = semantic.segment_vocabulary()
    if dim not in vocab:
        return None
    members = list(vocab.get(dim, ()))
    sibling = (f" The governed values of {dim} are: {', '.join(members)}." if members else "")
    run.repairs.append({"ungrounded_concept": {"concept": concept, "dim": dim}})
    run.acts.append(Act("segment_gate", str(Position.REPAIR), "handed back",
                         f"question names {concept!r}, which does not ground to the ontology; "
                         f"correction {run.claim_retries} of 2").as_dict())
    return ToolResult(
        "Your answer was not accepted: the question names something this data does not contain.\n"
        f"{concept!r} has no referent in the governed ontology — no metric and no dimension value "
        f"matches it.{sibling} It is not in the data, so `refuse` with reason "
        f"`ungoverned_dimension_value` rather than serve a number computed for a different "
        f"concept.", is_error=True)


def applied_segment(run, exit_call):
    """Hand back an answer whose serving call OMITTED a governed segment the QUESTION named.

    The four-slots segment miss on the answer path: "spend on paid search" served the
    all-channel total because the call carried no channel filter. `dropped_constraint` cannot
    see it — nothing was dropped, the filter was never applied — so this reads the question.

    The division is `ungrounded_candidates`': the MODEL judges which governed value the question
    restricts to (`classify.segment_named`, mapping "paid search" onto `paid_search`), and the
    MECHANISM verifies that value EXISTS among the metric's governed members before acting, then
    checks the serving call applied it. A named segment that grounds to nothing — "TikTok", no
    such channel — is left alone: that is the refuse case, carried by the brief's own "refuse if
    absent" line, not turned into a filter for a value the layer lacks.

    Its own guardrail (`applied_segment`): the enforcement that a named segment was applied,
    independent of whether the `metric_brief` block is delivering context. Fires only when the
    question names a real governed segment AND the number served ignored it.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "applied_segment", False):
        return None
    r = run._resolve_segment()
    # Only a LINKED segment (a real member, lexically anchored) can be one the answer should
    # have applied; an unlinked one is the refuse case that `segment_gate` owns, not this.
    if r is None or not r["linked"]:
        return None
    dim, value = r["dim"], r["value"]
    leaf, want = dim.split("__")[-1], str(value).lower()
    served = None
    for metric, args in run._governed_calls():
        served = served or (metric, args)             # a call to correct if none carries it
        for k, v in (args.get("filters") or {}).items():
            if str(k).split("__")[-1] == leaf and str(v).lower() == want:
                return None                                   # the segment was applied -> serve
    run.repairs.append({"applied_segment": {"dimension": dim, "value": value}})
    # The LLM already IDENTIFIED the segment (language) and it grounds to a real member;
    # APPLYING it to the governed call is mechanical, so the mechanism does it rather than trust
    # the model to re-query — it dropped the filter once and, told to re-query, re-served the
    # same total. Insert the grounded filter into the served call and recompute the governed
    # value, and hand that exact number back to state. Refusing would decline a value that IS
    # computable (the false-premise lesson); serving the unfiltered total is the silent error.
    corrected = run._segment_value(served, dim, value) if served else None
    run.acts.append(Act("metric_brief", str(Position.REPAIR), "handed back",
                         f"question restricts to {dim}={value!r}, served number applied no such "
                         f"filter; supplied the {value!r} slice = {corrected}; "
                         f"correction {run.claim_retries} of 2").as_dict())
    if corrected is not None:
        return ToolResult(
            f"Your answer was not accepted: the question restricts to {value!r} ({dim}), but the "
            f"number you served is the UNFILTERED total across all values. Applying that governed "
            f"segment filter, the {value!r} slice of the metric is {corrected}. Answer with "
            f"{corrected} for the {value!r} segment.", is_error=True)
    return ToolResult(   # could not recompute the slice -> the plain instruction, or refuse
        "Your answer was not accepted: the question restricts to a specific segment.\n"
        f"The question names {value!r} ({dim}, a governed value), but the number you served came "
        f"from a call with no such filter — it reports the unfiltered total across all values. "
        f"Re-query with filters={{'{dim}': '{value}'}} and answer that slice, or `refuse` if the "
        f"segment truly cannot be isolated.", is_error=True)


def _segment_value(run, served, dim, value):
    """The governed metric's value with the grounded segment filter APPLIED — the mechanical step
    the model dropped. Re-runs the served call with filters[dim]=value and returns the scalar, or
    None if it does not recompute to a single number (the mechanism supplies a fact or steps
    back, never a guess). Rounded like a served figure so the handed-back number reads cleanly."""
    metric, args = served
    filtered = dict(args)
    filtered["filters"] = {**(args.get("filters") or {}), dim: value}
    try:
        vals = before.value_of(run.grounding.semantic, filtered, metric)
    except Exception:                                                   # noqa: BLE001
        return None
    if isinstance(vals, dict) and len(vals) == 1:
        (v,) = vals.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return round(v, 4)
    return None
