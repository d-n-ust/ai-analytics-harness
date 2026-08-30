"""Focused model calls that CATEGORISE A REQUEST, before any answer exists.

Separate from judge.py, which adjudicates work already done. The two differ on every axis that
decides where code lives: this reads the question, that reads the answer and the trace; this
returns a category, that returns a verdict; this runs to decide whether a check APPLIES, that runs
to decide whether an answer SURVIVES. And when this is wrong the reader gets a redundant sentence or
loses a disclosure, where a wrong verdict from the judge can overturn a correct governed number.

They also version independently, which is the reason they cannot share a file's fingerprint. Each
module hashes its own behaviour-defining surface so a stored row can be marked stale by the prompt
that actually produced it.

EVERY CLASSIFIER HERE MUST CITE, AND THE CITATION IS CHECKED. Asked whether "how many active users
on web last week" had already chosen between two definitions, the first version answered yes and
quoted `is_internal = false` — the discriminator it had been handed, which appears nowhere in the
question. It suppressed the disclosure and the run served one reading silently. The model is good at
the judgement and will manufacture a justification for it, so the justification is verified rather
than taken. That is the whole division this module exists to hold: the model makes the call nothing
mechanical can make, and a mechanism decides whether to believe it.
"""

from __future__ import annotations

import hashlib
import json

from ..conversation import Conversation


def prompt_fingerprint() -> str:
    """A short, stable hash of every behaviour-defining surface in this module — system prompts,
    user templates, and the whole report schemas. It changes iff a classifier's spec changes, so a
    stored row can be flagged stale. Deliberately NOT shared with judge.py: rewording a classifier
    must not invalidate a verifier result, or the other way round."""
    surface = "|".join([_SCOPE_SYSTEM, _SCOPE_USER, json.dumps(_SCOPE_REPORT, sort_keys=True),
                        _MEASURE_SYSTEM, _MEASURE_USER, json.dumps(_MEASURE_REPORT, sort_keys=True)])
    return hashlib.sha256(surface.encode()).hexdigest()[:12]


# --- `scope_classifier`: did the request already choose between two definitions? ---------------- #
#
# ITS OWN CALL, ON ITS OWN SHORT PROMPT, for the same reason `classify_value_role` is: this is a
# judgement about LANGUAGE and nothing mechanical can make it. Two governed definitions of one
# concept produce byte-identical tool calls whether or not the user said which they meant, so no
# check that refuses to read the question can tell those cases apart. Measured: the same call for
# "how many active users on web last week" and "how many active users EXCLUDING INTERNAL AND TEST
# ACCOUNTS on web last week".
#
# WHERE IT SITS IS THE POINT. The model contributes the judgement; the machinery still decides what
# ships. `ambiguity_disclosure` firing stays mechanical — index, execute both, compare — because a
# trigger that varies by model has no guarantee in it. Only the question "was this already
# resolved?" is delegated, and its failure mode is bounded: get it wrong and the reader receives a
# redundant sentence or loses a disclosure. Both are governed numbers. Nothing here can produce a
# figure.
#
# Defaults to `no` on anything unexpected, which is the strict reading: a judgement that did not
# arrive must not be the one that suppresses a disclosure.
_SCOPE_SYSTEM = (
    "You decide one thing about an analytics question: did the person asking already say which of "
    "two governed definitions they wanted?\n\n"
    "Answer `yes` only when the question NAMES the distinction between them — in the asker's own "
    "words, not the metric's name. A question that merely mentions the concept, or that narrows "
    "something else (a platform, a period, a region), has NOT chosen.\n"
    "Answer `no` when the question is silent about the distinction, however specific it is in "
    "other respects.")

_SCOPE_USER = (
    "Question: {question}\n\n"
    "Two governed definitions both answer it:\n"
    "  - {mine}: {mine_desc}\n"
    "  - {theirs}: {theirs_desc}\n"
    "What separates them: {discriminator}\n\n"
    "Did the question already say which of the two it wanted?")

_SCOPE_REPORT = {
    "name": "report_scope",
    "description": "Report whether the question already chose between the two definitions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "chose": {"type": "string", "enum": ["yes", "no"]},
            "quote": {"type": "string",
                      "description": "When yes, the words FROM THE QUESTION that chose, copied "
                                     "exactly. Not the definition's wording and not the "
                                     "discriminator. Empty when no."},
        },
        "required": ["chose"],
    },
}


def _quoted_from(question: str, quote: str) -> bool:
    """Are these the question's own words, AND a SPECIFIC span rather than the whole question?

    THE JUSTIFICATION IS VERIFIED, NOT TAKEN, and it fails two ways. Asked whether "how many active
    users on web last week" had chosen a reading, the judge answered yes and quoted
    `is_internal = false` — the discriminator it was handed, which appears nowhere in the question.
    A yes that cannot point at the question is a no.

    The second way is the mirror, and it defeated the first guard: asked whether "total monthly
    recurring revenue" chose between `mrr` and `gross_mrr`, the judge answered yes and quoted the
    WHOLE QUESTION. That passes "is it in the question" trivially, and it suppressed the disclosure,
    so the run served one reading of a contested metric silently. A quote that is the whole question
    isolates no distinction — it is what the model produces when the question named none and it
    grabbed everything. A real scope quote is a phrase ("excluding internal and test accounts"),
    materially shorter than the question. So a quote covering most of the question is not a quote.

    Erring strict is the safe direction: a wrongly-rejected quote costs a redundant disclosure; a
    wrongly-accepted one loses the disclosure entirely, which is the silent failure. Whitespace and
    case are normalised; nothing else is, because a quote that needs interpretation is not a quote.
    """
    norm = lambda s: " ".join(str(s or "").lower().split())
    q, whole = norm(quote), norm(question)
    if not q or q not in whole:
        return False
    qw, ww = len(q.split()), len(whole.split())
    return qw <= 0.8 * ww


def question_chose_scope(model, question: str, mine: str, mine_desc: str,
                         theirs: str, theirs_desc: str, discriminator: str) -> tuple:
    """(chose, quote) — did the request itself pick one of two governed readings?

    A `yes` survives only if its quote is verifiably in the question. That keeps the division the
    guardrail is built on: the model makes the judgement no mechanism can make, and a mechanism
    decides whether to believe it.
    """
    user = _SCOPE_USER.format(question=question, mine=mine, mine_desc=mine_desc or "(no description)",
                              theirs=theirs, theirs_desc=theirs_desc or "(no description)",
                              discriminator=discriminator or "their scope")
    try:
        turn = model.respond(Conversation.opening(_SCOPE_SYSTEM, user), [_SCOPE_REPORT],
                             force_tool="report_scope", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return False, ""
    for call in turn.tool_calls:
        if call.name == "report_scope":
            quote = str(call.args.get("quote") or "").strip()
            chose = str(call.args.get("chose")).strip().lower() == "yes"
            if chose and not _quoted_from(question, quote):
                return False, f"unverified quote {quote!r}"
            return chose, quote
    return False, ""


# --- measure check (the `grounded_measure` guardrail): did the served number measure the -------- #
# --- quantity the question asked for? ----------------------------------------------------------- #
#
# The substitution failure is on the answer path, one level below the clarify grounding: "which
# category do users spend the most TIME on" answered with a COUNT of completions. The dimension
# (category) grounds, so a concept-level check passes; the swap is in the MEASURE, and it is
# invisible to the reader because a per-category number looks responsive whatever it counts.
#
# Nothing mechanical reads "a count is not a duration" without becoming the brittle equality gate
# this design rejects. So the model judges its OWN served answer against the question, and — as with
# the scope classifier — the justification is verified rather than taken: a `proxy`/`unmeasured`
# verdict survives only if the words it says the question asked for are actually in the question.
# The routing that follows (serve / disclose / refuse) is the guardrail's, and is the dial the
# experiment turns; this only supplies the one judgement about language.
#
# Defaults to `measures` — SERVE — on anything unexpected, the non-rigid reading: a judgement that
# did not arrive must not be the one that refuses an answer the reader could have used.
_MEASURE_SYSTEM = (
    "You check ONE thing about an analytics answer: did the number it reports measure the quantity "
    "the question asked for, or a different quantity standing in for it?\n\n"
    "Report:\n"
    "- `measures`: the number IS the quantity asked for (a count answering 'how many', spend "
    "answering 'how much did we spend').\n"
    "- `proxy`: the number is a RELATED but different quantity, offered in place of the one asked "
    "for — completions reported for a question about time spent, app-opens for engagement.\n"
    "- `unmeasured`: the quantity asked for is not captured in this data at all, and something "
    "else was reported instead.\n\n"
    "Judge the QUANTITY only — never the filters, the period, or the grouping. Copy the words from "
    "the QUESTION that name the quantity asked for.")

_MEASURE_USER = (
    "Question: {question}\n\n"
    "The answer given: {answer}\n\n"
    "Did the number reported measure the quantity the question asked for?")

_MEASURE_REPORT = {
    "name": "report_measure",
    "description": "Report whether the answer measured the quantity the question asked for.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["measures", "proxy", "unmeasured"]},
            "asked": {"type": "string",
                      "description": "The words FROM THE QUESTION naming the quantity asked for, "
                                     "copied exactly. Empty only when verdict is `measures`."},
            "served": {"type": "string",
                       "description": "What the reported number actually measures, in a few "
                                      "words (e.g. 'count of completed habits')."},
        },
        "required": ["verdict"],
    },
}


def answer_measures_asked(model, question: str, answer: str) -> tuple:
    """(verdict, asked, served) — did the served number measure the quantity the question asked
    for, a proxy for it, or something the data does not capture?

    A `proxy`/`unmeasured` verdict survives only if `asked` is verifiably the question's own words;
    otherwise it is downgraded to `measures`, so the check cannot refuse an answer on a quantity it
    cannot point at in the question. Same division as the scope classifier: the model makes the
    judgement, the mechanism decides whether to believe it, and the safe default is to serve.
    """
    user = _MEASURE_USER.format(question=question, answer=answer or "(no text)")
    try:
        turn = model.respond(Conversation.opening(_MEASURE_SYSTEM, user), [_MEASURE_REPORT],
                             force_tool="report_measure", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return "measures", "", ""
    for call in turn.tool_calls:
        if call.name == "report_measure":
            verdict = str(call.args.get("verdict") or "measures").strip().lower()
            asked = str(call.args.get("asked") or "").strip()
            served = str(call.args.get("served") or "").strip()
            if verdict in ("proxy", "unmeasured") and not _quoted_from(question, asked):
                return "measures", "", served       # unverified claim of substitution -> serve
            return verdict, asked, served
    return "measures", "", ""
