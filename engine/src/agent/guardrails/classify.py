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
    surface = "|".join([_SCOPE_SYSTEM, _SCOPE_USER, json.dumps(_SCOPE_REPORT, sort_keys=True)])
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
    """Are these actually the question's own words?

    THE JUSTIFICATION IS VERIFIED, NOT TAKEN. Asked whether "how many active users on web last
    week" had chosen a reading, the judge answered yes and quoted `is_internal = false` — the
    discriminator it had been handed, which appears nowhere in the question. It suppressed the
    disclosure and the run served one reading silently, which is the failure the whole mechanism
    exists to prevent. A yes that cannot point at the question is a no. Whitespace and case are
    normalised; nothing else is, because a quote that needs interpretation is not a quote.
    """
    norm = lambda s: " ".join(str(s or "").lower().split())
    q = norm(quote)
    return bool(q) and q in norm(question)


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
