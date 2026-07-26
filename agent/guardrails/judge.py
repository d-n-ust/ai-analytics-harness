"""The LLM critic the trajectory_verify guardrail runs.

Kept apart from after.py because it is the only guardrail machinery in the repo that calls a
model, and therefore the only one whose verdict is a probability rather than a proof. Everything
else at position AFTER is deterministic and provable; this is an opinion, and an opinion has to
be scored against labels before it can be trusted (evals/components/verifier_audit.py).

It INSPECTS rather than re-answers: it is shown exactly what the analyst computed and asked for a
concrete reason the number does not answer the question. Verification is easier than generation,
and a re-answerer false-overturns correct governed numbers.
"""

from __future__ import annotations

import hashlib

from ..conversation import Conversation

_VERIFY_SYSTEM = (
    "You verify an analytics answer. You are NOT asked to re-answer the question — you are shown "
    "exactly what the analyst computed, and your job is to find a CONCRETE reason the computed "
    "number does NOT answer the question as asked. Report answers_question=true ONLY if you cannot "
    "find one. Ground EVERY judgement in the metric DEFINITION you are given (its description, what "
    "it measures, and its unit) — never in assumptions about the domain. Run these five checks:\n"
    "1. THING — does what the metric measures, per its definition, match the thing the question asks "
    "about? If the question is about one entity and the metric measures a different one, that is a "
    "thing mismatch.\n"
    "2. KIND — does the metric's unit match the KIND of number the question asks for? 'how many / the "
    "count of' needs a COUNT; 'how much / the total' needs an AMOUNT (a count, or a summed "
    "quantity/currency); 'what rate / what %/ per-unit / average' needs a RATE or RATIO. A rate or "
    "ratio reported for a 'how many' question is WRONG (kind).\n"
    "3. SCOPE — look ONLY at the analyst's ADDED filters (shown as 'analyst added'). For a TOTAL or "
    "overall figure that list must be empty; a filter there that the question did not name means the "
    "number is a subset, not the total. IGNORE the metric's own built-in filters and how it is "
    "computed internally — those are part of the definition and correct by construction. A time "
    "window is a legitimate scope, never a violation.\n"
    "4. DEFINITION — does the metric's PURPOSE (its description) match the question's intent? For "
    "example, a point-in-time or 'current' metric does not answer an 'all-time / in total / ever' "
    "question. Judge the metric by its description and what it measures, NEVER by how it is computed "
    "internally (a CASE, a division, a built-in segment filter are the correct definition, not a "
    "fault).\n"
    "5. SEGMENT — the metric's `segment` names WHO it covers (all, active, paying, power, "
    "active_subscription). Compare it to the segment the question asks about. If the question asks "
    "about EVERYONE ('total', 'all', 'in total', 'ever', 'how many X do we have / are there') but the "
    "metric's segment is a subset that requires activity or a holding (active, paying, power, "
    "active_subscription), the metric covers a NARROWER segment and does NOT answer the question — "
    "flag it (mismatch=thing). This is the one case where a correct built-in segment still fails: the "
    "metric is built for a different, narrower question (active users is not the user total; paying "
    "users is not all users). Report this as mismatch=segment. If the question names no broader "
    "segment, or its segment matches the metric's, this passes — do not invent a mismatch.\n\n"
    "GOVERNED MODIFICATIONS (shown as 'governed modifications applied') are done by the LAYER, not "
    "invented by the analyst, and are correct by construction — never flag them:\n"
    "- A governed segment that restricts the rows IS the right way to answer a question about that "
    "segment (e.g. a 'real acquisition' segment that drops test channels answers a question about "
    "real acquisition — this is NOT an unrequested filter).\n"
    "- A governed coverage window: if the question names a period that extends before it, the "
    "in-coverage portion IS the correct answer. The out-of-coverage months are pre-launch/unavailable "
    "data; excluding them is REQUIRED, so do NOT flag the answer for 'not covering' those months.\n\n"
    "Cite the specific definition text or the analyst's added filter that fails. Do not invent "
    "problems, and never object to the metric's internal computation or a governed modification. If "
    "all five checks pass, the answer stands."
)

# The evidence the judge is shown, as a named template rather than an inline f-string — so
# the fingerprint below can hash it. A judge's behaviour is set by its instructions AND by
# what it is shown; changing either invalidates a validation, so both must be fingerprinted.
_EVIDENCE = (
    "metric used: {metric}\n"
    "  definition (correct by construction): {description}\n"
    "  measures entity={entity}, segment={segment}, aggregation={agg}, unit={unit}\n"
    "  governed modifications applied (DEFINITIONAL — the layer did this, not the analyst; "
    "do NOT treat as an invented restriction): {governed}\n"
    "  analyst added (check these for scope): {applied_filters}\n"
    "  time window: {time_window}\n"
    "  full SQL (for reference; its built-in clauses are definitional, not the analyst's): {sql}\n"
    "query result: {result_value}\n"
    "analyst's claimed answer: {claim_value}"
)
_USER = "QUESTION:\n  {question}\n\nWHAT THE ANALYST COMPUTED:\n{evidence}"

_REPORT = {
    "name": "report_verdict",
    "description": "Report whether the computed number answers the question as asked.",
    "input_schema": {"type": "object", "properties": {
        "answers_question": {"type": "boolean",
                             "description": "true ONLY if the number answers the question as asked"},
        "mismatch": {"type": "string",
                     "enum": ["none", "thing", "kind", "scope", "definition", "segment"],
                     "description": "which check failed (none if it passes)"},
        "reason": {"type": "string",
                   "description": "one concrete sentence citing the failing definition text or SQL "
                                  "clause (or, if it passes, why)"}},
        "required": ["answers_question", "mismatch", "reason"]}}


def prompt_fingerprint() -> str:
    """A short, stable hash of the verifier's behaviour-defining surface — its system prompt, the
    mismatch enum, AND the evidence template it judges from. It changes iff the judge's spec
    changes, so a stored validation can be flagged STALE the moment any of them is edited (as
    Workstream C did). The evidence belongs in here: a judge shown different evidence is a
    different judge, even word-for-word identical instructions."""
    enum = _REPORT["input_schema"]["properties"]["mismatch"]["enum"]
    surface = "|".join([_VERIFY_SYSTEM, ",".join(enum), _EVIDENCE, _USER])
    return hashlib.sha256(surface.encode()).hexdigest()[:12]


def verify_trajectory(model, question: str, metric_name: str, metric_def: dict,
                      sql: str, result_value, claim_value, applied_filters=None,
                      time_window=None, governed_notes=None) -> tuple[bool, str, str]:
    """Inspect one answer's trajectory. Returns (answers_question, mismatch_kind, reason).
    answers_question=False means the served number does not answer the question -> downgrade.
    `applied_filters` is what the ANALYST added for this query (not the metric's own definition),
    so the scope check judges the analyst's choices, not the definition's built-in clauses.
    `governed_notes` are governed modifications the layer applied (a named segment, a coverage
    window) — DEFINITIONAL, not the analyst's invention — so a governed narrowing (excluding a
    test channel, dropping pre-launch data) is not mistaken for a scope error."""
    md = metric_def or {}
    brief = _EVIDENCE.format(
        metric=metric_name, description=md.get("description", "(no description)"),
        entity=md.get("entity"), segment=md.get("segment"),
        agg=md.get("agg"), unit=md.get("unit"),
        governed="; ".join(governed_notes) if governed_notes else "none",
        applied_filters=applied_filters or "none",
        time_window=time_window or "all time",
        sql=sql, result_value=result_value, claim_value=claim_value)
    user = _USER.format(question=question, evidence=brief)
    turn = model.respond(Conversation.opening(_VERIFY_SYSTEM, user), [_REPORT],
                         force_tool="report_verdict", temperature=0)
    for call in turn.tool_calls:
        if call.name == "report_verdict":
            v = call.args
            return bool(v.get("answers_question", True)), v.get("mismatch", "none"), v.get("reason", "")
    # No verdict is not a veto: the judge is refuse-only, so silence leaves the answer standing.
    return True, "none", "verifier produced no verdict"


