"""The output guardrails on a completed answer (R7-R9), before it is served.

This module owns every check the agent runs on an answer:
  - provenance / single-metric (R7): the served number must BE one governed query result, not a
    hand-composition — read from the model's typed source_metric + declared_value.
  - output validation (R8): the returned value must be well-formed (non-empty, in range for its unit).
  - the trajectory verifier (R9): an LLM critic that INSPECTS what the analyst did (the metric
    definition, the exact SQL, the added filters) and finds a CONCRETE reason the number does not
    answer the question. It does NOT re-answer — verification is easier than generation, and a
    re-answerer false-overturns correct governed numbers. The checks are adversarial (cite the
    failing definition text or SQL clause), which resists the sycophancy a plain "is this correct?"
    judge falls into.

All three are refuse-only and asymmetric: a False verdict downgrades a confident answer to
not-correct; none can ever rescue a refusal, so they can only add safety.
"""

from __future__ import annotations

import logging

from .numbers import parse_numbers

_log = logging.getLogger(__name__)

# The trajectory verifier's mismatch kind -> a governed refusal reason (all in tools.REFUSAL_REASONS).
# The finer mismatch KIND is preserved on the stored verdict; the reason code is the coarser label.
_V_REASON = {"kind": "wrong_measure", "scope": "other",
             "definition": "no_governed_definition", "thing": "no_governed_definition",
             "segment": "no_governed_definition", "none": "other"}

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
    governed = "; ".join(governed_notes) if governed_notes else "none"
    brief = (f"metric used: {metric_name}\n"
             f"  definition (correct by construction): {md.get('description', '(no description)')}\n"
             f"  measures entity={md.get('entity')}, segment={md.get('segment')}, "
             f"aggregation={md.get('agg')}, unit={md.get('unit')}\n"
             f"  governed modifications applied (DEFINITIONAL — the layer did this, not the analyst; "
             f"do NOT treat as an invented restriction): {governed}\n"
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


# --------------------------------------------------------------------------- #
# Deterministic output checks: provenance (single-metric, R7) + validation (R8)
# --------------------------------------------------------------------------- #
def _num_match(a: float, b: float) -> bool:
    """Two reported numbers are the same value, tolerant of rounding but not of distinct
    integers (886 != 18866, and adjacent counts 371 != 372 stay distinct)."""
    return abs(a - b) <= max(0.5, 0.005 * abs(b))


def _step_values(step: dict) -> list:
    """The typed numeric results a query_metric step returned. Prefers the typed `result_values`
    the dispatcher now records; falls back to parsing the display text only for older traces
    (which had no typed field), so the checks never depend on scraping numbers out of prose/SQL."""
    v = step.get("result_values")
    if v is not None:
        return [float(x) for x in v]
    return parse_numbers(step.get("result"))


def _is_direct_governed_value(declared_value, steps: list) -> bool:
    """Single-metric test: is the served number the actual result of SOME governed query the
    model ran? If it matches no governed result, the model built it by hand (a rate x a count,
    metric A + metric B) — a composition that is out of scope for a one-metric answer."""
    for s in steps or []:
        if s.get("tool") == "query_metric" and any(_num_match(declared_value, b) for b in _step_values(s)):
            return True
    return False


def _provenance(declared_value, steps: list, source_metric, metrics):
    """Which governed metric produced the answer, its call args, and the value it returned
    — taken ONLY from the model's typed `source_metric` declaration, never inferred from the
    answer text. When that metric was queried more than once (say a breakdown and a total),
    the model's typed `declared_value` selects WHICH of ITS OWN calls produced the reported
    number, so the grain and the governed value are read from the right call. That is picking
    a call of an already-known metric, not guessing the metric — a value shared by two
    different metrics can never mislink, because the metric is declared. Returns
    (metric, args, value), or (None, None, None) when nothing verifiable was declared."""
    if source_metric not in metrics:
        return None, None, None
    calls = [s for s in (steps or []) if s.get("tool") == "query_metric"
             and (s.get("args") or {}).get("metric") == source_metric]
    if not calls:
        return None, None, None
    best = next((s for s in reversed(calls)
                 if declared_value is not None
                 and any(_num_match(declared_value, b) for b in _step_values(s))),
                calls[-1])
    governed = _step_values(best)
    return source_metric, (best.get("args") or {}), (governed[0] if governed else None)


def output_validation(metric_def: dict, value) -> tuple[bool, str, str, str]:
    """Deterministic checks on the RETURNED value, not the metric selection: a governed
    query that came back empty/null, or a value impossible for its `unit`, must not be
    served as an answer. Refuse-only. This is where the metric-selection check can't see —
    it never looks at *what came back*."""
    if value is None:
        return (False, "result_empty", "the governed query returned no value (empty/null result)",
                "the metric produced no number for this request, so there is nothing to report; refuse.")
    unit = (metric_def or {}).get("unit")
    if value < 0 and unit in ("count", "currency", "share"):
        return (False, "implausible_value", f"a {unit} value cannot be negative (got {value})",
                f"the governed result {value} is impossible for a {unit} metric; refuse.")
    if unit == "share" and value > 100:
        return (False, "implausible_value", f"a share above 100 (got {value})",
                f"the governed result {value} is out of range for a share; refuse.")
    return True, "", "", ""


def verify_answer(semantic, question: str, answer_text: str | None, steps: list,
                  source_metric: str | None = None, declared_value=None,
                  run_output_validation: bool = True, run_single_metric: bool = False,
                  verify_traj=None) -> tuple[bool, str, str, str]:
    """Run the output guardrails on a completed answer. Return (ok, reason, missing, explanation);
    ok=False means convert the answer into a refuse. Each check is toggled by its own rung so
    the deltas are measured separately: `run_single_metric` (R7, the served number must BE one
    governed result, not a hand-composition), `run_output_validation` (R8, well-formed value), and
    `verify_traj` (R9, the trajectory judge). `source_metric`/`declared_value` are the model's typed
    provenance. The checks apply to a NUMERIC answer, so prose (no `declared_value`) passes through
    untouched. Refuse-only: it can turn an answer into a refusal, never the reverse."""
    if semantic is None or not answer_text or declared_value is None:
        return True, "", "", ""

    if run_single_metric and not _is_direct_governed_value(declared_value, steps):
        # The served number is not any single governed result, so no governed DEFINITION answers
        # the question as asked (ARR = mrr x 12, an activation count from a rate). Report that root
        # cause, not a vague 'out_of_scope' — a coverage gap is one typed signal, so downstream
        # (and a future planning agent) can label it and name the metric worth defining.
        return (False, "no_governed_definition",
                "no single governed metric produces this number as asked (it was derived or combined)",
                "this number was composed by hand (a rate times a count, or two metrics added), not "
                "read from one governed metric. No governed definition covers what was asked — refuse "
                "and name the metric that would need to exist, rather than serve a hand-built figure.")

    metric, args, value = _provenance(declared_value, steps, source_metric, semantic.metrics)
    if metric is None:                     # a numeric answer we can't attribute -> measure it
        _log.info("output checks: numeric answer with no usable source_metric; not verified")
        return True, "", "", ""            # no governed metric to check against
    metric_def = semantic.metrics[metric]

    if run_output_validation:                         # R8: the returned value is empty or impossible
        ok_r, reason_r, missing_r, expl_r = output_validation(metric_def, value)
        if not ok_r:
            return False, reason_r, missing_r, expl_r

    if verify_traj is not None:            # R9: does this metric + SQL actually answer the question?
        ok_v, mismatch, reason_v = verify_traj(question, metric, metric_def, args, value, declared_value)
        if not ok_v:
            return (False, _V_REASON.get(mismatch, "other"),
                    f"verifier[{mismatch}]: {reason_v}"[:180], reason_v)

    return True, "", "", ""
