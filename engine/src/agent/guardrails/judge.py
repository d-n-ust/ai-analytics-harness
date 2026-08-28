"""The LLM critic the trajectory_verify guardrail runs.

Kept apart from after.py because its verdict is a probability rather than a proof: everything else
at position AFTER is deterministic and provable, while this is an opinion, and an opinion has to be
scored against labels before it can be trusted (evals/components/verifier_audit.py).

It is not the only model call in the guardrails — `classify.py` holds the ones that categorise a
REQUEST rather than adjudicate an answer. The two are kept apart because they version
independently: `prompt_fingerprint` here exists to mark a stored verdict stale the moment the
judge's spec changes, and folding an unrelated prompt into that hash would invalidate every stored
verifier result whenever the other one was reworded.

It INSPECTS rather than re-answers: it is shown exactly what the analyst computed and asked for a
concrete reason the number does not hold up. Verification is easier than generation, and a
re-answerer false-overturns correct governed numbers.

It runs as TWO calls, because it asks two questions that need different evidence:

  1. what is this number DOING in the answer — the figure the question asked for, or a fact cited
     in support of a claim the sentence makes?
  2. given that, does it hold up?

They were one call first, with the checks carrying "skip these three if it is evidence". A
question's grammar constrains the unit and segment of an ANSWER and neither of a supporting
figure, so those checks cannot transfer — but stating that as exceptions inside a prompt built
for the other case produced incoherent verdicts (mismatch=none returned alongside a rejection,
and mismatch=segment returned after being told to skip segment). Two short unconditional prompts
are more reliable than one branching one, and they leave the tuned five-check path exactly as it
was for the lookups it was tuned on. The extra call is small and only fires when there is an
answer sentence to classify.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from ..conversation import Conversation

# The judge's STANCE — the one paragraph that tells it what it is looking for. It is separated
# from the five checks because it is the only part under test: the asymmetric wording resists
# sycophancy (a plain "is this correct?" judge agrees with whatever it is shown) but "find a
# reason to reject, and pass only if you fail" is a known over-rejection instruction, and this
# judge fires on 52% of the answers it sees. Which effect dominates is measurable, so it is a
# treatment with two levels rather than a decision made in prose.
#
# Both levels say "SUPPORT the answer the analyst gave" rather than "answer the question". The
# older wording pre-decided the role: told to check the number against the question, the judge
# could only read the number AS the answer, which is the right test for a lookup and the wrong one
# for "why did it drop?". "Supports the answer given" is the single frame that covers both — when
# the number IS the answer, supporting it means being it.
_STANCE = {
    # Shipped in every published run to date.
    "skeptical": (
        "You verify an analytics answer. You are NOT asked to re-answer the question — you are shown "
        "exactly what the analyst computed, and your job is to find a CONCRETE reason the computed "
        "number does NOT support the answer the analyst gave. Report answers_question=true ONLY if "
        "you cannot find one. "),
    # Same task, no thumb on the scale: it is asked to decide, not to hunt.
    "even_handed": (
        "You verify an analytics answer. You are NOT asked to re-answer the question — you are shown "
        "exactly what the analyst computed, and your job is to decide whether that number supports "
        "the answer the analyst gave. Report answers_question=false only when you can point to a "
        "CONCRETE mismatch, and answers_question=true when the number does support it. Neither "
        "verdict is the safe default. "),
}

# CALL ONE: what is the number doing in the answer?
#
# The judge decides this rather than the answering model declaring it. A self-declared role would
# be unfalsifiable and a one-word exit from the strict test; the judge's is scoreable against
# labels exactly as `mismatch` is.
#
# It reads the ANSWER, not the metric, because that is where the distinction lives — the same
# metric on the same question is the answer in one reply and a cited fact in another.
_ROLE_SYSTEM = (
    "Decide what one number is DOING in an analyst's answer. Report exactly one role.\n\n"
    "the_answer — the question asks for a figure, and this number IS that figure.\n"
    "  'How many paying users do we have?' → 'We have 371 paying users.'  (371 is the_answer)\n"
    "evidence — the question asks for an explanation, a diagnosis, a judgement or a direction, and "
    "the number is one fact cited in support. The SENTENCE is the answer; the number backs it up.\n"
    "  'Why did value moments drop?' → 'Frequency fell: days per user went 2.72 → 2.27.'  "
    "(2.27 is evidence)\n"
    "  'Is the app healthy?' → 'Moderately — 3785 habits completed last week.'  (3785 is evidence)\n\n"
    "Decide from what the ANSWER does, not from what the metric is. If the substance of the answer "
    "IS a figure, the role is the_answer. If the substance is a statement and the figure only backs "
    "it up, the role is evidence."
)

_ROLE_REPORT = {
    "name": "report_role",
    "description": "Report what the number is doing in the analyst's answer.",
    "input_schema": {"type": "object", "properties": {
        "value_role": {"type": "string", "enum": ["the_answer", "evidence"],
                       "description": "the_answer if the number is the figure the question asked "
                                      "for; evidence if it is a fact cited to support a claim"}},
        "required": ["value_role"]}}

_ROLE_USER = ("QUESTION:\n  {question}\n\nTHE ANALYST'S ANSWER:\n  {claim_text}\n\n"
              "THE NUMBER IN QUESTION: {claim_value}")

# How to grade a claim about CAUSE. Shared by both roles, because a lookup answer can name a
# driver too, and read against the causal record the tree supplies in the evidence block.
#
# The two edge kinds differ in KIND, not degree, and the tree states which is which. An identity
# edge is arithmetic: the parent IS the product of its children, the shares sum to 1, and naming
# the largest as the driver is a computed fact. An influence edge is a correlation the layer
# chose to record along with the evidence for and against it — the one in this tree carries
# "co-moved in one anomaly week only; across normal weeks the correlation is ~0".
#
# Without this the judge saw a metric, its SQL and the analyst's filters, and nothing about which
# drivers exist. "The drop was driven by frequency" (exact) and "driven by EMEA" (a slice, not a
# node) were indistinguishable to it.
_CAUSAL = (
    "CLAIMS ABOUT CAUSE. When the analyst names a driver, grade it against the causal evidence "
    "shown above — that is what the governed tree encodes, and nothing else is encoded:\n"
    "- an IDENTITY child is exact arithmetic; the parent IS the product of its children and the "
    "shares sum to 1. Naming one as the driver is GOVERNED and needs no further evidence. Accept "
    "it, and do not ask the analyst to prove what the tree computed.\n"
    "- an INFLUENCE child is correlational. It may be offered as a LIKELY driver together with "
    "its confidence and evidence. Asserted as a proven cause — 'X caused Y', with no hedge — that "
    "is a mismatch (definition), and say which edge was overstated.\n"
    "- a driver that appears in NEITHER list is ungoverned. A region, platform or channel is a "
    "breakdown showing WHERE a change landed, not a driver OF it: 'the fall was driven by EMEA' "
    "names a slice, not a lever, and the tree encodes no such edge. That is a mismatch (thing).\n"
    "- if no causal evidence is shown above, the analyst did not decompose through the tree. Judge "
    "the number as usual and do not invent a causal requirement.\n"
)

# CALL TWO, evidence branch. Two checks, not five, and both read against the SENTENCE. The other
# three compare the metric with the QUESTION's wording, which is meaningful only when the number
# is the answer to it: no metric's purpose "matches the intent" of "why did it drop?", and no
# segment is "the segment the question asks about" when the question asks for an explanation.
# Applied to a supporting figure they reject every diagnostic answer by construction — which is
# what they did, to all 19 of them.
_CHECKS_EVIDENCE = (
    "This number is EVIDENCE: the analyst's SENTENCE is the answer, and the number is one fact "
    "cited to back it up.\n\n"
    "YOUR SUBJECT IS ONE NUMBER. Find the phrase in the sentence that states the declared number "
    "above — that phrase, and only that phrase, is what you check. A good answer cites several "
    "figures; each of the others came from its own governed query, which you have NOT been shown. "
    "Read them as context, never as your subject. If the only fault you can name lives in another "
    "figure, there is no fault to report.\n\n"
    "Two checks, both grounded in the metric DEFINITION you are given:\n"
    "1. THING — does this metric measure what that phrase says this number is, and is that "
    "relevant to the claim? Citing paying users as the cause of a marketing-spend jump is a THING "
    "mismatch. Citing a completed-habit count in support of 'the app looks healthy' is NOT — a "
    "count is a perfectly good fact to cite for a qualitative claim.\n"
    "2. SCOPE — look ONLY at the analyst's ADDED filters (shown as 'analyst added'). A filter the "
    "sentence does not mention means a subset is offered as though it were the whole. The metric's "
    "own built-in clauses, its segment, its time window and any governed modifications are "
    "DEFINITIONAL and correct by construction — never flag them.\n\n"
    "MISDESCRIBED (thing) and SILENTLY NARROWED (scope) are the ONLY two faults a cited figure can "
    "have. A rejection must name one of them; if you cannot name one, report mismatch=none and the "
    "answer stands. That is the expected outcome for a sound citation — do not manufacture a fault "
    "to have something to report. None of the following is a fault:\n"
    "- the figure is only PART of the argument, or would not settle the question on its own. "
    "Evidence is cited alongside other evidence; sufficiency is not your subject.\n"
    "- the figure covers a DIFFERENT POPULATION from another figure in the answer. Different "
    "metrics have different populations by definition, and setting them side by side is what "
    "analysis is. You have not been shown the other figures' queries and cannot rule on them.\n"
    "- the UNIT. 'Why did X fall?' and 'is the app healthy?' constrain the unit of an ANSWER, never "
    "of a supporting figure.\n"
    "- the metric's PURPOSE against the question. No metric's purpose matches the intent of 'why "
    "did it drop?'; that is not a fault in the metric.\n"
    "- the metric's SEGMENT against the question. A question asking for an explanation names no "
    "segment to compare against.\n"
    "- whether the analyst's CONCLUSION is right. You check how this number is used, not the "
    "quality of the analysis.\n\n"
    "When you do reject, cite the definition text or the added filter that fails.\n\n"
     + _CAUSAL
)

# CALL TWO, the_answer branch — the five checks, unchanged from every published run.
_CHECKS_ANSWER = (
    "Ground EVERY judgement in the metric DEFINITION you are given (its description, what "
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
    "all five checks pass, the answer stands.\n\n"
    + _CAUSAL
)


def stance_name() -> str:
    """Which stance this process runs. A treatment variable, so it is read once and recorded on
    every row rather than left to whatever the environment happened to hold."""
    name = os.environ.get("VERIFIER_STANCE", "skeptical")
    if name not in _STANCE:
        raise ValueError(f"VERIFIER_STANCE={name!r}; expected one of {sorted(_STANCE)}")
    return name


def verify_system(value_role: str = "the_answer") -> str:
    """The judge's instructions for one role. The stance is shared — it is the treatment under
    test, and splitting it per role would confound it with the role."""
    return _STANCE[stance_name()] + (_CHECKS_EVIDENCE if value_role == "evidence"
                                     else _CHECKS_ANSWER)

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
    # NOT "the analyst's claimed answer". That label asserted the conclusion of the very question
    # the judge is now asked first — shown a number introduced as the answer, it classified the
    # number as the answer every time, including for 'is the app healthy?'.
    "the number the analyst declared: {claim_value}\n"
    "what the analyst actually served (THIS is the answer; the number above is one figure "
    "inside it): {claim_text}\n"
    "CAUSAL EVIDENCE THE GOVERNED TREE CARRIES:\n{causal_record}"
)
_USER = "QUESTION:\n  {question}\n\nWHAT THE ANALYST COMPUTED:\n{evidence}"

_REPORT = {
    "name": "report_verdict",
    "description": "Report whether the computed number holds up in the answer the analyst gave.",
    "input_schema": {"type": "object", "properties": {
        "answers_question": {"type": "boolean",
                             "description": "true ONLY if the number holds up: for the_answer, it "
                                            "IS the figure the question asked for; for evidence, "
                                            "it is a sound and relevant fact for the claim made"},
        "mismatch": {"type": "string",
                     "enum": ["none", "thing", "kind", "scope", "definition", "segment"],
                     "description": "which check failed (none if it passes)"},
        "reason": {"type": "string",
                   "description": "one concrete sentence citing the failing definition text or SQL "
                                  "clause (or, if it passes, why)"}},
        "required": ["answers_question", "mismatch", "reason"]}}


def prompt_fingerprint() -> str:
    """A short, stable hash of the verifier's behaviour-defining surface — its system prompt, the
    WHOLE verdict schema, and the evidence template it judges from. It changes iff the judge's
    spec changes, so a stored validation can be flagged STALE the moment any of them is edited (as
    Workstream C did). The evidence belongs in here: a judge shown different evidence is a
    different judge, even word-for-word identical instructions.

    Schemas are hashed whole rather than by picking out the mismatch enum. Naming one field meant
    every field added later was silently outside the fingerprint. Both roles' instructions and the
    role classifier are in here for the same reason: each is a prompt that decides a verdict."""
    surface = "|".join([verify_system("the_answer"), verify_system("evidence"), _ROLE_SYSTEM,
                        _CAUSAL,
                        json.dumps(_REPORT, sort_keys=True),
                        json.dumps(_ROLE_REPORT, sort_keys=True),
                        _EVIDENCE, _USER, _ROLE_USER])
    return hashlib.sha256(surface.encode()).hexdigest()[:12]


def classify_value_role(model, question: str, claim_text: str, claim_value) -> str:
    """Is this number the figure the question asked for, or a fact cited to support a claim?

    Its own call, on its own short prompt. Folded into the verifier's prompt as a conditional it
    was unreliable — the model returned mismatch codes it had just been told to skip, and once
    returned mismatch=none alongside a rejection.

    Defaults to `the_answer`, which is the strict test: a classification that did not arrive must
    not be the lenient one.
    """
    user = _ROLE_USER.format(question=question, claim_text=claim_text, claim_value=claim_value)
    turn = model.respond(Conversation.opening(_ROLE_SYSTEM, user), [_ROLE_REPORT],
                         force_tool="report_role", temperature=0)
    for call in turn.tool_calls:
        if call.name == "report_role":
            role = call.args.get("value_role")
            if role in ("the_answer", "evidence"):
                return role
    return "the_answer"


@dataclass(frozen=True)
class Judgement:
    """One verdict from the judge.

    A named type rather than a widening tuple: `value_role` is a fourth thing it decides, and
    every caller unpacked the first three positionally. `the_answer` is the default because it is
    the strict test — a judgement that failed to arrive should not be the lenient one.
    """

    answers_question: bool
    mismatch: str = "none"
    reason: str = ""
    value_role: str = "the_answer"


def verify_trajectory(model, question: str, metric_name: str, metric_def: dict,
                      sql: str, result_value, claim_value, applied_filters=None,
                      time_window=None, governed_notes=None,
                      claim_text: str | None = None,
                      causal_record: str = "") -> Judgement:
    """Inspect one answer's trajectory.
    answers_question=False means the served number does not answer the question -> downgrade.
    `applied_filters` is what the ANALYST added for this query (not the metric's own definition),
    so the scope check judges the analyst's choices, not the definition's built-in clauses.
    `governed_notes` are governed modifications the layer applied (a named segment, a coverage
    window) — DEFINITIONAL, not the analyst's invention — so a governed narrowing (excluding a
    test channel, dropping pre-launch data) is not mistaken for a scope error.

    `claim_text` is the sentence the analyst actually served. It decides which test runs: shown a
    bare number against a question, the only thing a judge can ask is "is this number the answer",
    so on 'what caused the drop?' it read 3785 as a proposed cause, found a count is not a cause,
    and rejected. Absent (a synthetic trajectory with no answer behind it), the role classifier is
    skipped and the strict the_answer checks run — the behaviour every published run had."""
    md = metric_def or {}
    said = " ".join((claim_text or "").split())
    role = classify_value_role(model, question, said, claim_value) if said else "the_answer"
    brief = _EVIDENCE.format(
        metric=metric_name, description=md.get("description", "(no description)"),
        entity=md.get("entity"), segment=md.get("segment"),
        agg=md.get("agg"), unit=md.get("unit"),
        governed="; ".join(governed_notes) if governed_notes else "none",
        applied_filters=applied_filters or "none",
        time_window=time_window or "all time",
        sql=sql, result_value=result_value, claim_value=claim_value,
        claim_text=said or "(not recorded)",
        causal_record=causal_record or "  (the analyst did not decompose through the tree)")
    user = _USER.format(question=question, evidence=brief)
    turn = model.respond(Conversation.opening(verify_system(role), user), [_REPORT],
                         force_tool="report_verdict", temperature=0)
    for call in turn.tool_calls:
        if call.name == "report_verdict":
            v = call.args
            mismatch = v.get("mismatch", "none")
            # A rejection has to name the check that failed — that is the judge's whole contract,
            # and the mismatch code is what the refusal reason is built from downstream. It does
            # return "none" alongside a rejection (it did so on an answer whose two checks it had
            # just walked through and passed), which is not a verdict this codebase can represent.
            # Read as what it says rather than what it decided: no failing check named, no failure.
            allowed = bool(v.get("answers_question", True)) or mismatch == "none"
            return Judgement(allowed, mismatch, v.get("reason", ""), role)
    # No verdict is not a veto: the judge is refuse-only, so silence leaves the answer standing.
    return Judgement(True, "none", "verifier produced no verdict", role)
