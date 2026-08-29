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


# --- `value_membership`: does the question name a value outside the governed vocabulary? --------- #
#
# THE NIL PATH FOR A DIMENSION VALUE. A question that names a value with no governed referent — "how
# much did we spend on TikTok ads", where the channels are content_seo / paid_search / partnerships
# / referral — carries a FALSE EXISTENTIAL PRESUPPOSITION: it presupposes a channel called TikTok.
# The agent cannot bind the value, so it relaxes the constraint that failed and answers the universal
# set: it drops the channel filter and serves total marketing spend, 61,233, as the TikTok figure.
#
# Three fields have named exactly this — false-presupposition QA (CREPE), value-linking
# unanswerability in text-to-SQL, and NIL prediction in entity linking — and they converge on one
# rule: binding a mention to a closed vocabulary must have an explicit NO-REFERENT outcome, or the
# system force-binds to the nearest candidate. This supplies that outcome.
#
# THE DIVISION, as everywhere in this module: the model reads the question and proposes which tokens
# are categorical VALUES (a channel, a region, a plan), quoting each; the mechanism decides governed
# or not, by membership against the layer's published members. A value is governed iff it matches
# some member of some dimension, so a real value the model mis-attributes to the wrong dimension is
# still recognised as governed and does not fire. It fires only on a quoted value that is in the
# question and matches NO governed member anywhere.
_VALUE_SYSTEM = (
    "You are given an analytics question and the complete governed vocabulary of a data warehouse: "
    "every categorical dimension and its allowed values (channels, regions, countries, platforms, "
    "plans, statuses).\n\n"
    "List every value the question names that is meant as one of these categorical values — a "
    "specific channel, region, country, platform, plan or status to filter or break down by. "
    "Whether or not it appears in the allowed lists. Quote each exactly as it appears in the "
    "question.\n\n"
    "Do NOT list metrics, dates, numbers, or ordinary words. Only values that name a member of a "
    "categorical dimension. If the question names none, return an empty list.")

_VALUE_USER = "Question: {question}\n\nGoverned vocabulary:\n{vocab}"

_VALUE_REPORT = {
    "name": "report_values",
    "description": "The categorical dimension-values the question names, each quoted from it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string", "description": "copied exactly from the question"},
                        "reads_as": {"type": "string",
                                     "description": "the kind of value: channel, region, plan, …"},
                    },
                    "required": ["quote"],
                },
            },
        },
        "required": ["values"],
    },
}


def _norm(s: str) -> str:
    """Fold spelling variants that mean the same member: case, and the space/underscore/hyphen a
    catalogue writes one way and a person another (`paid search` == `paid_search`)."""
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def question_names_ungoverned_value(model, question: str, members: dict) -> list:
    """[{value, reads_as}] for each value the question names that is in NO governed dimension.

    `members` is {dimension -> [governed values]}. A quoted value counts as ungoverned only when it
    is verifiably in the question AND matches no member of any dimension — so an incidental word, or
    a value attributed to the wrong dimension, cannot fire. Empty list on any failure: a check that
    did not run must not invent a refusal.
    """
    governed = {_norm(v) for vals in members.values() for v in vals}
    vocab = "\n".join(f"  {d}: {', '.join(map(str, vals))}" for d, vals in sorted(members.items()))
    try:
        turn = model.respond(Conversation.opening(_VALUE_SYSTEM,
                                                  _VALUE_USER.format(question=question, vocab=vocab)),
                             [_VALUE_REPORT], force_tool="report_values", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return []
    named = next((c.args.get("values") for c in turn.tool_calls if c.name == "report_values"), None)
    out = []
    for item in named or []:
        quote = str((item or {}).get("quote") or "").strip()
        if not quote or _norm(quote) in governed:
            continue                                     # governed, or empty — nothing to report
        if _norm(quote) not in _norm(question):
            continue                                     # unverified: the model must quote the question
        out.append({"value": quote, "reads_as": str((item or {}).get("reads_as") or "").strip()})
    return out
