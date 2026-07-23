"""The trajectory verifier (check #2: does the query answer the resolved question?).

Unlike the recompute judge, this does NOT re-answer the question — that is generation, and a
model that re-derives MRR is often worse than the governed metric, so it false-overturns correct
answers. Instead the verifier INSPECTS what the analyst actually did: it is handed the question,
the resolved metric definition, the exact SQL, the query result, and the claimed number, and asked
to find a CONCRETE reason the number does not answer the question. Verification is easier than
generation, so a good checker beats a re-answerer even when both use the same model.

It is refuse-only and asymmetric: a False verdict downgrades a confident answer to not-correct; it
never rescues a refusal. The checks are concrete and adversarial (cite the failing definition text
or SQL clause), which resists the sycophancy a plain "is this correct?" judge falls into.
"""

from __future__ import annotations

_VERIFY_SYSTEM = (
    "You verify an analytics answer. You are NOT asked to re-answer the question — you are shown "
    "exactly what the analyst computed, and your job is to find a CONCRETE reason the computed "
    "number does NOT answer the question as asked. Report answers_question=true ONLY if you cannot "
    "find one. Ground EVERY judgement in the metric DEFINITION you are given (its description, what "
    "it measures, and its unit) — never in assumptions about the domain. Run these four checks:\n"
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
    "internally (a CASE, a division, a built-in population filter are the correct definition, not a "
    "fault).\n\n"
    "Cite the specific definition text or the analyst's added filter that fails. Do not invent "
    "problems, and never object to the metric's internal computation. If all four checks pass, the "
    "answer stands."
)

_REPORT = {
    "name": "report_verdict",
    "description": "Report whether the computed number answers the question as asked.",
    "input_schema": {"type": "object", "properties": {
        "answers_question": {"type": "boolean",
                             "description": "true ONLY if the number answers the question as asked"},
        "mismatch": {"type": "string", "enum": ["none", "thing", "kind", "scope", "definition"],
                     "description": "which check failed (none if it passes)"},
        "reason": {"type": "string",
                   "description": "one concrete sentence citing the failing definition text or SQL "
                                  "clause (or, if it passes, why)"}},
        "required": ["answers_question", "mismatch", "reason"]}}


def verify_trajectory(model, question: str, metric_name: str, metric_def: dict,
                      sql: str, result_value, claim_value, applied_filters=None,
                      time_window=None) -> tuple[bool, str, str]:
    """Inspect one answer's trajectory. Returns (answers_question, mismatch_kind, reason).
    answers_question=False means the served number does not answer the question -> downgrade.
    `applied_filters` is what the ANALYST added for this query (not the metric's own definition),
    so the scope check judges the analyst's choices, not the definition's built-in clauses."""
    md = metric_def or {}
    brief = (f"metric used: {metric_name}\n"
             f"  definition (correct by construction): {md.get('description', '(no description)')}\n"
             f"  measures entity={md.get('entity')}, population={md.get('population')}, "
             f"aggregation={md.get('agg')}, unit={md.get('unit')}\n"
             f"  analyst added (check these for scope): {applied_filters or 'none'}\n"
             f"  time window: {time_window or 'all time'}\n"
             f"  full SQL (for reference; its built-in clauses are definitional, not the analyst's): {sql}\n"
             f"query result: {result_value}\n"
             f"analyst's claimed answer: {claim_value}")
    user = f"QUESTION:\n  {question}\n\nWHAT THE ANALYST COMPUTED:\n{brief}"
    resp = model.create(_VERIFY_SYSTEM, [{"role": "user", "content": user}],
                        [_REPORT], force_tool="report_verdict", temperature=0)
    for b in getattr(resp, "content", []):
        if getattr(b, "type", None) == "tool_use" and b.name == "report_verdict":
            inp = b.input or {}
            return bool(inp.get("answers_question", True)), inp.get("mismatch", "none"), inp.get("reason", "")
    return True, "none", "verifier produced no verdict"
