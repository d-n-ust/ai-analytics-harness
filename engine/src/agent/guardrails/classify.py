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
                        _MEASURE_SYSTEM, _MEASURE_USER, json.dumps(_MEASURE_REPORT, sort_keys=True),
                        _SEGMENT_SYSTEM, _SEGMENT_USER, json.dumps(_SEGMENT_REPORT, sort_keys=True),
                        _GROUND_SYSTEM, _GROUND_USER, json.dumps(_GROUND_REPORT, sort_keys=True),
                        _ANSWERABILITY_SYSTEM, _ANSWERABILITY_USER, json.dumps(_ANSWERABILITY_REPORT, sort_keys=True),
                        _RESOLVE_SYSTEM, _RESOLVE_USER, json.dumps(_RESOLVE_REPORT, sort_keys=True),
                        _DISCLOSE_SYSTEM, _DISCLOSE_USER, json.dumps(_DISCLOSE_REPORT, sort_keys=True)])
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


# --- `metric_brief` self-check (segment slot): does the question name a governed segment the ----- #
# --- serving call omitted? ---------------------------------------------------------------------- #
#
# The four-slots segment miss on the answer path: "spend on paid search" served the all-channel
# total because the serving call carried no channel filter. `dropped_constraint` cannot see it —
# nothing was dropped, the filter was never applied — so this reads the QUESTION. The division is
# the one `ungrounded_candidates` draws: the MODEL judges which governed value the question restricts
# to (relevance, and the synonym mapping — "paid search" -> `paid_search`, "SEO" -> `content_seo`,
# using the descriptions), and the MECHANISM verifies that value EXISTS among the governed members
# (`applied_segment` in loop.py does the membership check and the applied/omitted comparison).
#
# A segment the question names that is NOT governed — "TikTok", a channel the layer does not have —
# is returned as none here: that is the refuse case, and forcing a filter for a value that does not
# exist would be the opposite of the fix. Defaults to none on anything unexpected, the safe reading:
# a judgement that did not arrive must not add a filter the agent did not ask for.
_SEGMENT_SYSTEM = (
    "You decide one thing about an analytics question: does it restrict the answer to ONE specific "
    "value of a governed segment dimension?\n\n"
    "You are given the governed dimensions and their allowed values. When the question restricts to "
    "a segment, report: the exact PHRASE from the question that names it ('paid search', 'TikTok', "
    "'the monthly plan'); the DIMENSION it belongs to, spelled entity__dimension, EVEN IF no listed "
    "value matches; and the matching VALUE in exact governed spelling — mapping the wording onto it "
    "('paid search' -> paid_search, 'the monthly plan' -> monthly, 'SEO' -> content_seo when a "
    "value covers SEO).\n\n"
    "Leave VALUE empty when the phrase clearly names a segment OF THAT DIMENSION but none of the "
    "listed values matches it — a channel, plan, region, or platform the layer does not have "
    "(e.g. 'TikTok' is a marketing channel, but not one of the listed channels: dimension "
    "spend_row__channel, value empty). Do NOT map it onto the nearest different value.\n\n"
    "Report restricts=false only when the question asks for the overall total with no such "
    "restriction. Judge only the segment restriction, never the metric, period, or grouping.")

_SEGMENT_USER = (
    "Governed segment dimensions and their allowed values:\n{vocab}\n\n"
    "Question: {question}\n\n"
    "Does the question restrict the answer to one specific value of one of these dimensions?")

_SEGMENT_REPORT = {
    "name": "report_segment",
    "description": "Report the governed segment the question restricts to, or none.",
    "input_schema": {
        "type": "object",
        "properties": {
            "restricts": {"type": "boolean",
                          "description": "True if the question names one specific segment value "
                                         "(governed or not); false for the overall total."},
            "phrase": {"type": "string",
                       "description": "The exact words from the question naming the segment, e.g. "
                                      "'paid search', 'TikTok'. Empty when restricts is false."},
            "dimension": {"type": "string",
                          "description": "The governed dimension the phrase belongs to, spelled "
                                         "entity__dimension, EVEN IF no listed value matches it."},
            "value": {"type": "string",
                      "description": "The matching governed value, exact spelling from the lists. "
                                     "EMPTY when the phrase names a segment of that dimension but no "
                                     "listed value matches (do not map onto a different value)."},
        },
        "required": ["restricts"],
    },
}


def segment_named(model, question: str, vocab: dict) -> tuple:
    """(restricts, phrase, dimension, value) for the segment the question restricts to.

    Feeds two guards in loop.py: `segment_gate` (refuse when a named segment does not link) and
    `applied_segment` (apply a linked segment the served call ignored). This is only the language
    step; the anchoring and existence verification live in the caller.

    `vocab` is {dimension -> [governed values]}. The model does the language step — is a segment
    named, what phrase, which dimension, and which value if any — reporting the DIMENSION even when
    no value matches, and an EMPTY value rather than the nearest different one. The CALLER verifies:
    that `value` is really a member of `vocab[dimension]` (existence) and that it is lexically
    anchored in `phrase` (so a substitution onto a real-but-wrong value is rejected). Relevance is
    the model's, existence and anchoring are the machine's. Defaults to (False, '', '', '') on any
    error, so the check never invents a restriction the question did not make.
    """
    if not vocab:
        return False, "", "", ""
    listing = "\n".join(f"  {d}: {', '.join(vals)}" for d, vals in sorted(vocab.items()))
    user = _SEGMENT_USER.format(vocab=listing, question=question)
    try:
        turn = model.respond(Conversation.opening(_SEGMENT_SYSTEM, user), [_SEGMENT_REPORT],
                             force_tool="report_segment", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return False, "", "", ""
    for call in turn.tool_calls:
        if call.name == "report_segment":
            if not call.args.get("restricts"):
                return False, "", "", ""
            phrase = str(call.args.get("phrase") or "").strip()
            dim = str(call.args.get("dimension") or "").strip()
            value = str(call.args.get("value") or "").strip()
            return True, phrase, dim, value
    return False, "", "", ""


# --- `segment_gate` grounding resolver: does every concept in the question ground to the -------- #
# --- ontology? ---------------------------------------------------------------------------------- #
#
# The full-ontology answer to the substitution the narrow segment resolver could not handle. Given
# the WHOLE ontology (metrics with definitions, segment dimensions with values), the model resolves
# every concept the question names — by MEANING, its superpower: "platform not recorded" is the
# `unknown` value, "real acquisition channels" is the `acquisition_spend` metric, "TikTok" is
# nothing. The division is the project's standing one, applied correctly this time: the model owns
# SEMANTIC FIT (which lexical rules kept getting wrong), the caller verifies only EXISTENCE (the
# named grounding is real, or the NIL is genuinely absent). Defaults to answerable=true on any
# doubt, so the gate refuses only what is clearly ungrounded and never a question it could not read.
_GROUND_SYSTEM = (
    "You resolve an analytics question against a governed ontology of metrics and segment "
    "dimensions. Decide whether EVERY concept the question names has a referent in the ontology.\n\n"
    "A concept is the measure or metric the question asks for, or a segment it restricts to — a "
    "channel, plan, region, platform, status, and so on. Map each onto the ontology by MEANING, not "
    "just wording: 'devices where the platform is not recorded' is the platform value 'unknown'; "
    "'real acquisition channels' is the acquisition_spend metric; 'the monthly plan' is plan "
    "'monthly'.\n\n"
    "Report answerable=false ONLY when the question names a metric or a segment value the ontology "
    "clearly does NOT contain — a channel it has no value for (TikTok, Facebook), a plan it lacks "
    "(enterprise), a measure it does not define. Then name that ungrounded concept, and if it is a "
    "segment, the dimension it would belong to.\n\n"
    "When every concept grounds, or when you are unsure, report answerable=true. The default is to "
    "let the agent proceed; refuse only what is clearly absent from the ontology.")

_GROUND_USER = (
    "{ontology}\n\n"
    "Question: {question}\n\n"
    "Does every concept the question names have a referent in this ontology?")

_GROUND_REPORT = {
    "name": "report_grounding",
    "description": "Report whether every concept in the question grounds to the ontology.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answerable": {"type": "boolean",
                           "description": "True if every concept grounds, OR if you are unsure."},
            "ungrounded_concept": {"type": "string",
                                   "description": "The phrase from the question that has no referent "
                                                  "in the ontology. Empty when answerable is true."},
            "dimension": {"type": "string",
                          "description": "If the ungrounded concept is a segment, the dimension it "
                                         "would belong to, spelled entity__dimension. Empty for a "
                                         "metric-level miss or when answerable."},
        },
        "required": ["answerable"],
    },
}


def ground_question(model, question: str, ontology: str) -> tuple:
    """(answerable, ungrounded_concept, dimension) — does every concept in the question ground to
    the ontology?

    The model does the semantic linking (its superpower), reporting an ungrounded concept by MEANING
    rather than by spelling; the caller verifies EXISTENCE (the NIL is genuinely absent) but does not
    re-judge the semantics. Defaults to (True, '', '') on any error, so a judgement that did not
    arrive can never be the one that refuses an answerable question.
    """
    user = _GROUND_USER.format(ontology=ontology, question=question)
    try:
        turn = model.respond(Conversation.opening(_GROUND_SYSTEM, user), [_GROUND_REPORT],
                             force_tool="report_grounding", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return True, "", ""
    for call in turn.tool_calls:
        if call.name == "report_grounding":
            answerable = bool(call.args.get("answerable", True))
            concept = str(call.args.get("ungrounded_concept") or "").strip()
            dim = str(call.args.get("dimension") or "").strip()
            return answerable, concept, dim
    return True, "", ""


# --- three-way answerability (transparent policy): governed / computable / uninstrumented ------- #
#
# The measure the question asks for can stand in three places, and the right behaviour differs for
# each: a GOVERNED metric is answered from the semantic layer; a measure with no governed metric but
# the DATA to compute it is computed and its definition disclosed (or clarified); a measure the data
# does not capture is refused as uninstrumented. The model does the semantic mapping over BOTH the
# governed metrics and the data schema — the schema states its own grains and its own absences ("no
# screen taxonomy", "no duration") — and names the basis or the gap so the mechanism can act on it.
_ANSWERABILITY_SYSTEM = (
    "You classify how an analytics question's MEASURE can be answered, given a semantic layer of "
    "GOVERNED METRICS and the DATA SCHEMA beneath it. Judge the measure the question asks for (the "
    "quantity), not its segment or period.\n\n"
    "Report one of:\n"
    "- `governed`: the measure maps, by meaning, to a governed metric — OR to a RATIO or per-unit "
    "COMBINATION of governed metrics (X per Y where both are governed): 'habits per active user' is "
    "value_moments per active_users, 'spend per signup' is marketing_spend per new_signups, 'revenue "
    "per paying user' is mrr per paying_users. A composition of governed measures is still governed. "
    "Prefer this whenever governed metrics — alone or combined as a ratio — answer the question.\n"
    "- `computable`: NO governed metric or ratio of governed metrics fits, but the data schema has "
    "the tables and columns to compute the measure from raw data (name the basis). This needs logic "
    "BEYOND combining governed metrics — a cohort/retention calculation, a bespoke construct — "
    "e.g. 90-day retention from signup cohorts joined to activity.\n"
    "- `uninstrumented`: NO governed metric AND the schema lacks the data — a measure the tables do "
    "not capture (duration when only counts exist, a screen when there is no screen taxonomy, "
    "headcount when there is no employee table). Name what is missing.\n\n"
    "The schema states its own grains and its own ABSENCES; trust them. When a governed metric fits, "
    "answer `governed`; when unsure between computable and uninstrumented, prefer `uninstrumented` "
    "(do not claim data that is not shown).")

_ANSWERABILITY_USER = (
    "GOVERNED METRICS:\n{ontology}\n\n"
    "DATA SCHEMA (the tables beneath the metrics, with their grains and what they capture):\n"
    "{schema}\n\n"
    "Question: {question}\n\n"
    "How can the measure this question asks for be answered?")

_ANSWERABILITY_REPORT = {
    "name": "report_answerability",
    "description": "Classify how the question's measure can be answered.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["governed", "computable", "uninstrumented"]},
            "measure": {"type": "string",
                        "description": "The measure/quantity the question asks for, in a few words."},
            "governed_metric": {"type": "string",
                                "description": "The governed metric it maps to. Only when verdict "
                                               "is `governed`."},
            "basis": {"type": "string",
                      "description": "The tables/columns that support computing it, and in one "
                                     "phrase how. Only when verdict is `computable`."},
            "missing": {"type": "string",
                        "description": "The data the schema lacks. Only when verdict is "
                                       "`uninstrumented`."},
        },
        "required": ["verdict"],
    },
}


def classify_answerability(model, question: str, ontology: str, schema: str) -> dict:
    # The judgement behind the `answerability_gate` guardrail (loop.py routes on the verdict).
    """{verdict, measure, governed_metric, basis, missing} — is the question's measure governed,
    computable from the data, or uninstrumented?

    The model maps the measure by meaning over the governed metrics AND the data schema (which
    carries its own grains and absences); the caller acts on the verdict — answer, compute-and-
    disclose or clarify, or refuse. Defaults to `uninstrumented` on any error, the safe reading: a
    judgement that did not arrive must not license computing a number the data may not support.
    """
    user = _ANSWERABILITY_USER.format(ontology=ontology, schema=schema, question=question)
    try:
        turn = model.respond(Conversation.opening(_ANSWERABILITY_SYSTEM, user),
                             [_ANSWERABILITY_REPORT], force_tool="report_answerability", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return {"verdict": "uninstrumented", "measure": "", "missing": "(classifier error)"}
    for call in turn.tool_calls:
        if call.name == "report_answerability":
            v = str(call.args.get("verdict") or "uninstrumented").strip().lower()
            if v not in ("governed", "computable", "uninstrumented"):
                v = "uninstrumented"
            return {"verdict": v,
                    "measure": str(call.args.get("measure") or "").strip(),
                    "governed_metric": str(call.args.get("governed_metric") or "").strip(),
                    "basis": str(call.args.get("basis") or "").strip(),
                    "missing": str(call.args.get("missing") or "").strip()}
    return {"verdict": "uninstrumented", "measure": "", "missing": ""}


# --- graph-based answerability: the model decomposes, the ontology VERIFIES ---------------------- #
#
# The successor to classify_answerability. There, one model call judged BOTH interpretation AND
# existence, reading existence off a schema text that carried hand-written absences ("no screen",
# "no duration") — a model judgement of a fact, over an enumerated complement. Here the model does
# ONLY interpretation: it decomposes the measure into ingredient nodes against the closed-world marts
# graph, and MartsOntology.verify() decides existence and joinability deterministically. The model
# can no longer call a measure computable from data that is not there, nor uninstrumented from data
# that is; a decomposition that names a node the graph lacks is refused rather than believed.
_RESOLVE_SYSTEM = (
    "You resolve an analytics question against a CLOSED-WORLD marts ontology that lists everything "
    "the warehouse captures. Decide how the MEASURE the question asks for is answered, IN THIS "
    "ORDER, and cite the graph.\n\n"
    "Judge ONLY the measure — the quantity — NOT its segment (channel, plan, region, platform, "
    "status) or its time period. A governed metric stays GOVERNED when the question filters or dates "
    "it: 'active users in APAC' is metric.active_users, 'paying users on the monthly plan' is "
    "metric.paying_users, 'paid search spend' is metric.marketing_spend, 'MRR this year' is "
    "metric.mrr. Do NOT look for a segment value as a node, and do NOT decompose a measure a governed "
    "metric already covers — whether a named segment value exists is a different question, not yours.\n\n"
    "1. governed — a governed metric fits the measure directly, OR the measure is a RATIO or per-unit "
    "COMBINATION of governed metrics ('habits per active user' is value_moments per active_users, "
    "'spend per signup' is marketing_spend per new_signups). Report kind='governed' and "
    "metric=metric.<name>. Prefer this whenever a governed metric — alone, filtered, or as a ratio — "
    "covers the measure.\n"
    "2. computable — no governed metric fits, but the measure can be DERIVED from attributes and "
    "measures IN the graph, joined via the relationships. DECOMPOSE it and list the ingredient nodes "
    "(entity.attribute / entity.measure); you may cite join keys, they are real columns. List each "
    "ingredient as the BARE node id (e.g. user.signup_date), nothing after it. Example: 90-day "
    "retention decomposes to user.signup_date, activity.active_date, user.channel.\n"
    "3. uninstrumented — the measure needs an ingredient NOT in this complete graph. Because the "
    "graph is complete, a concept absent from it does not exist: 'minutes in app' needs a duration "
    "measure and there is none (only event counts); 'top screen' needs a screen attribute and there "
    "is none; 'revenue per employee' needs a headcount and there is no employee entity. Name the "
    "absent thing in `missing`.\n\n"
    "Interpretation is yours; only real nodes count — every ingredient is checked against the graph.")

_RESOLVE_USER = (
    "{ontology}\n\n"
    "Question: {question}\n\n"
    "How is the measure this question asks for answered? Cite the graph.")

_RESOLVE_REPORT = {
    "name": "resolve",
    "description": "Decompose the question's measure against the ontology.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["governed", "computable", "uninstrumented"]},
            "measure": {"type": "string",
                        "description": "The measure/quantity the question asks for, in a few words."},
            "metric": {"type": "string",
                       "description": "The governed metric it maps to, metric.<name>. Only when "
                                      "kind is `governed`."},
            "ingredients": {"type": "array", "items": {"type": "string"},
                            "description": "The graph nodes (entity.attribute / entity.measure) the "
                                           "measure is derived from. Only when kind is `computable`."},
            "missing": {"type": "string",
                        "description": "The concept absent from the graph. Only when kind is "
                                       "`uninstrumented`."},
        },
        "required": ["kind"],
    },
}


def resolve_measure(model, question: str, ontology_render: str) -> dict:
    """{kind, measure, metric, ingredients, missing} — the model's DECOMPOSITION of the question's
    measure against the closed-world graph. The model does only the interpretation; the caller hands
    kind/metric/ingredients to MartsOntology.verify(), which decides the verdict. Defaults to
    kind='uninstrumented' on any error — a decomposition that did not arrive must not license a
    served number.
    """
    user = _RESOLVE_USER.format(ontology=ontology_render, question=question)
    try:
        turn = model.respond(Conversation.opening(_RESOLVE_SYSTEM, user), [_RESOLVE_REPORT],
                             force_tool="resolve", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return {"kind": "uninstrumented", "measure": "", "metric": "", "ingredients": [],
                "missing": "(resolver error)"}
    for call in turn.tool_calls:
        if call.name == "resolve":
            kind = str(call.args.get("kind") or "uninstrumented").strip().lower()
            if kind not in ("governed", "computable", "uninstrumented"):
                kind = "uninstrumented"
            return {"kind": kind,
                    "measure": str(call.args.get("measure") or "").strip(),
                    "metric": str(call.args.get("metric") or "").strip(),
                    "ingredients": [str(i).strip() for i in (call.args.get("ingredients") or [])],
                    "missing": str(call.args.get("missing") or "").strip()}
    return {"kind": "uninstrumented", "measure": "", "metric": "", "ingredients": [], "missing": ""}


def answerability_via_graph(model, question: str, ontology) -> dict:
    """classify_answerability's SHAPE, decided by the graph: {verdict, measure, governed_metric,
    basis, missing}. The model decomposes (resolve_measure); the ontology's verify() decides the
    verdict; the two vocabularies are reconciled here (`instrumented` -> `governed`) so this is a
    drop-in for classify_answerability wherever a graph is available. `ontology` is any object with
    render() and verify() — no import of the ontology package is needed here.
    """
    r = resolve_measure(model, question, ontology.render())
    verdict, detail = ontology.verify(r["kind"], metric=r["metric"], ingredients=r["ingredients"])
    mapped = {"instrumented": "governed", "computable": "computable",
              "uninstrumented": "uninstrumented"}[verdict]
    return {"verdict": mapped,
            "measure": r["measure"],
            "governed_metric": r["metric"] if mapped == "governed" else "",
            "basis": detail if mapped == "computable" else "",
            "missing": r["missing"] or (detail if mapped == "uninstrumented" else "")}


# --- disclosure of a computed non-governed metric (transparent policy) --------------------------- #
#
# The transparent policy lets the agent COMPUTE a measure that has no governed metric — retention,
# a custom ratio — but only if it says so: the number is trustworthy exactly to the extent the
# reader can see the definition it rests on. This is the single check the disclosure requirement
# rests on: did the answer STATE how it computed the number, or did it serve a bare result. It does
# not judge whether the definition is the RIGHT one (that is the reader's, or a clarify's) — only
# whether one is shown. Defaults to disclosed=true, so a judgement that did not arrive never
# suppresses an answer the reader could have used; the gate only hands back a CLEARLY bare number.
_DISCLOSE_SYSTEM = (
    "You check ONE thing about an analytics answer that computed a measure with no governed "
    "metric: does it STATE THE DEFINITION it used — how the number was arrived at, in plain terms "
    "(e.g. 'retention here means a cohort active on or after day 90, excluding internal accounts')?"
    "\n\nReport disclosed=true when the answer states the definition or method it computed by, "
    "even briefly. Report disclosed=false only when it gives a bare number or a bare result (a "
    "channel, a figure) with NO statement of how it was defined or computed. Judge only whether a "
    "definition is shown, not whether it is the right one.")

_DISCLOSE_USER = (
    "Question: {question}\n\n"
    "The answer given: {answer}\n\n"
    "Does the answer state the definition or method it used to compute the number?")

_DISCLOSE_REPORT = {
    "name": "report_disclosure",
    "description": "Report whether the answer states the definition it computed by.",
    "input_schema": {
        "type": "object",
        "properties": {"disclosed": {"type": "boolean"}},
        "required": ["disclosed"],
    },
}


def answer_discloses_definition(model, question: str, answer: str) -> bool:
    """Did the answer state the definition it computed a non-governed measure by? Defaults to True
    on any error, so the disclosure gate refuses only a clearly bare result."""
    user = _DISCLOSE_USER.format(question=question, answer=answer or "(no text)")
    try:
        turn = model.respond(Conversation.opening(_DISCLOSE_SYSTEM, user), [_DISCLOSE_REPORT],
                             force_tool="report_disclosure", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return True
    for call in turn.tool_calls:
        if call.name == "report_disclosure":
            return bool(call.args.get("disclosed", True))
    return True
