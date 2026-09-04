"""Does this SQL compute the quantity the question named?

NOT A VERIFIER, A MATCHER. `judge.py` asks an open question — is there a concrete reason this number
does not hold up — and answers it with an opinion. That works on the governed path, where the
metric definition and the compiled SQL give it something to hold. A hand-written query has neither,
which is why `trajectory_verify` is incoherent without `governed_numbers`.

So this asks a closed question instead, once per PRIMITIVE, in experiment 04's vocabulary:

    measure   what is counted or summed        "time spent"        vs  COUNT(*)
    entity    what each row stands for         "a product feature" vs  GROUP BY source
    segment   which rows are included          "users in Americas" vs  no filter
    window    which period                     "last week"         vs  completed_date range

The decomposition is the point. "Does this SQL answer this question" is one opinion and cannot be
scored; four typed rows can each be labelled, and a run that gets the window right and the measure
wrong says so instead of returning a verdict.

TWO CALLS, BECAUSE THEY ARE TWO TASKS. The first READS: for each primitive, what did the question
name and what does the SQL do, in the matcher's own words, citing a column. The second COMPARES: are
those two short phrases the same quantity? Asked as one call it labelled the worst case in the suite
`match` while its own prose read "asks time spent in a product feature / sql counts value_moments
(events)" — the description was right and the label contradicted it. Reading and comparing are
different jobs and the second one goes wrong when it has the SQL and the schema in front of it to be
distracted by.

EVERY CLAIM CITES A COLUMN, AND THE CITATION IS CHECKED. A mismatch must name the column in the SQL
that carries the primitive, and that column must actually be in the SQL. An `absent` claim must name
the column that SHOULD have carried it, and that column must exist in the schema and NOT in the
SQL. A claim that fails its check is dropped, not reported. This is the same rule the scope
classifier needed: the model is good at the judgement and will manufacture a justification for it.

It reports; it does not refuse. What a caller does with a verified mismatch is a separate decision,
and this returns findings so that decision can be made — and measured — somewhere else.
"""

from __future__ import annotations

import hashlib
import json
import re

from ..core.conversation import Conversation

PRIMITIVES = ("measure", "entity", "segment", "window")

_SYSTEM = (
    "You read an analytics question and the SQL that was run to answer it, and describe them side "
    "by side, one aspect at a time. You are NOT deciding whether they agree — another step does "
    "that. Describe each side plainly and let the comparison happen elsewhere.\n\n"
    "Report one finding per aspect:\n"
    "  measure  what is counted, summed or averaged\n"
    "  entity   what each row of the result stands for\n"
    "  segment  which rows are included or excluded\n"
    "  window   which time period\n\n"
    "For each: `asks_for` is what the QUESTION names, in the asker's terms. `sql_does` is what the "
    "QUERY does, in the query's terms. Write `asks_for` empty when the question does not specify "
    "that aspect at all, which is common and is not a fault.\n\n"
    "EVERY finding must cite a column: the column IN THE SQL that carries the aspect, or — when "
    "the question asked for something the SQL does not express — the column in the SCHEMA that "
    "should have carried it. A citation you cannot point at is worse than no finding: it will be "
    "discarded.")

# The comparison, on its own, with neither the SQL nor the schema in front of it. Everything it
# could be distracted by has already been read out by the call above.
_COMPARE_SYSTEM = (
    "Two descriptions of one aspect of an analytics request: what the person asked for, and what "
    "the query did. Do they describe the SAME quantity?\n\n"
    "`same` when the query expresses what was asked, even if worded differently or computed by a "
    "longer route. `different` when it expresses something else — another measure, another "
    "grouping, another period, a population the request did not ask for.\n"
    "`missing` when the request asked for something and the query side does not express it.\n"
    "`not_asked` when the request did not name this aspect at all.\n\n"
    "A longer or more roundabout way of computing the right thing is `same`. Only report "
    "`different` when a reader would receive a different number because of it.")

_COMPARE_USER = ("Aspect: {primitive}\n"
                 "The request asked for : {asks_for}\n"
                 "The query did         : {sql_does}")

_COMPARE_REPORT = {
    "name": "report_same",
    "description": "Do the two descriptions name the same quantity?",
    "input_schema": {"type": "object",
                     "properties": {"verdict": {"type": "string",
                                                "enum": ["same", "different", "missing",
                                                         "not_asked"]}},
                     "required": ["verdict"]},
}

_USER = ("Question: {question}\n\n"
         "SQL that was run:\n{sql}\n\n"
         "Result columns: {columns}\n\n"
         "Warehouse schema:\n{schema}")

_REPORT = {
    "name": "report_primitives",
    "description": "One finding per aspect of the question, each citing a column.",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "primitive": {"type": "string", "enum": list(PRIMITIVES)},
                        "asks_for": {"type": "string",
                                     "description": "what the question named, or empty"},
                        "sql_does": {"type": "string", "description": "what the SQL does instead"},
                        "column": {"type": "string", "description": "the cited column"},
                    },
                    "required": ["primitive", "sql_does"],
                },
            },
        },
        "required": ["findings"],
    },
}


def prompt_fingerprint() -> str:
    """Hashes this matcher's behaviour-defining surface, independently of judge.py and classify.py,
    so a stored finding is marked stale by the prompt that produced it and by no other."""
    return hashlib.sha256("|".join(
        [_SYSTEM, _USER, json.dumps(_REPORT, sort_keys=True),
         _COMPARE_SYSTEM, _COMPARE_USER, json.dumps(_COMPARE_REPORT, sort_keys=True),
         _UNITS_SYSTEM, _UNITS_USER, json.dumps(_UNITS_REPORT, sort_keys=True),
         _UNITS_COMPARE_SYSTEM, _UNITS_COMPARE_USER,
         json.dumps(_UNITS_COMPARE_REPORT, sort_keys=True)]).encode()).hexdigest()[:12]


def _names(text: str) -> set:
    """Bare identifiers in a blob of SQL or schema, lowercased. Deliberately crude: this decides
    whether a cited column is PRESENT, which needs no parse, and a parser would fail closed on
    dialects this harness does not own."""
    return {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text or "")}


def _verified(finding: dict, sql: str, schema: str) -> bool:
    """Can this finding point at what it claims? The cited column must be somewhere real — in the
    SQL when the query expresses the aspect, in the schema when the claim is that it should have.
    A membership test over identifiers is all that separates a grounded claim from an invented one.
    """
    leaf = str(finding.get("column") or "").strip().rsplit(".", 1)[-1].lower()
    return bool(leaf) and (leaf in _names(sql) or leaf in _names(schema))


def _same(model, primitive: str, asks_for: str, sql_does: str) -> str:
    """The second call: are these two phrases the same quantity? Defaults to `same`, which is the
    lenient reading — a comparison that did not arrive must not manufacture a fault."""
    if not str(asks_for or "").strip():
        return "not_asked"
    try:
        turn = model.respond(
            Conversation.opening(_COMPARE_SYSTEM,
                                 _COMPARE_USER.format(primitive=primitive, asks_for=asks_for,
                                                      sql_does=sql_does or "(nothing)")),
            [_COMPARE_REPORT], force_tool="report_same", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return "same"
    for call in turn.tool_calls:
        if call.name == "report_same":
            v = str(call.args.get("verdict") or "").strip().lower()
            return v if v in ("same", "different", "missing", "not_asked") else "same"
    return "same"


def match_primitives(model, question: str, sql: str, columns, schema: str,
                     dictionary: str = "") -> dict:
    """{findings, faults, dropped} — every finding that survives its citation check, the subset
    that reports a fault, and how many claims were discarded as ungrounded.

    `dictionary` is what the warehouse says its own tables MEAN. Without it the matcher guesses at
    the grain of a fact table and reports the guess as a fault: three of four false positives in the
    first run were "counts rows in fct_value_moments" flagged against "habits completed", which are
    the same thing and nothing in a column list says so.
    """
    user = _USER.format(question=question, sql=sql,
                        columns=", ".join(str(c) for c in (columns or [])) or "(none recorded)",
                        schema=schema + (f"\n\nWhat these tables mean:\n{dictionary}"
                                         if dictionary else ""))
    try:
        turn = model.respond(Conversation.opening(_SYSTEM, user), [_REPORT],
                             force_tool="report_primitives", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return {"findings": [], "faults": [], "dropped": 0, "error": True}
    raw = []
    for call in turn.tool_calls:
        if call.name == "report_primitives":
            raw = [f for f in (call.args.get("findings") or []) if isinstance(f, dict)]
    kept = [f for f in raw if _verified(f, sql, schema)]
    for f in kept:
        f["verdict"] = _same(model, f.get("primitive"), f.get("asks_for"), f.get("sql_does"))
    return {"findings": kept,
            "faults": [f for f in kept if f.get("verdict") in ("different", "missing")],
            "dropped": len(raw) - len(kept)}


# --- the units check: does the ANSWER report the quantity the question named? ------------------ #
#
# ONE PRIMITIVE, CHECKED AGAINST THE ANSWER INSTEAD OF THE SQL, and the narrowing is the point. The
# four-primitive matcher above has to know what a fact table means and reports its guesses as
# faults. This compares two pieces of NATURAL LANGUAGE — what the question named and what the answer
# delivered — and needs no warehouse knowledge at all:
#
#     asked     "which product feature did users spend the most TIME in"
#     delivered "widget — 1,306 VALUE MOMENTS"
#
# Time against a count. Visible in the two strings alone.
#
# WHAT IT CANNOT DO, stated so nobody mistakes it for a verifier: it catches substitution of the
# QUANTITY, not error in the computation. "How many active users last week" answered 886 when 277
# was correct passes cleanly, because the quantity is right and only the number is wrong. Narrowness
# is what makes it usable — the open version of this question is what made `trajectory_verify` refuse
# four correct answers in one batch.
#
# Two calls, because reading and comparing are different jobs: splitting them took the matcher above
# from 1 of 5 to 3 of 5. Both sides cite a span, and both spans are checked. Defaults to `same` on
# any failure: a comparison that did not arrive must not manufacture a fault.
_UNITS_SYSTEM = (
    "Read an analytics question and the answer that was given, and name the QUANTITY on each side. "
    "Do not judge whether they agree — another step does that. Do not judge whether the number is "
    "correct; you cannot know that and it is not what you are for.\n\n"
    "`asked` is the quantity the question names, in its own words: a duration, a count of "
    "something, an amount of money, a rate.\n"
    "`delivered` is the quantity the answer reports, in the answer's own words.\n\n"
    "Quote a span from each side, copied exactly. A span you cannot point at will be discarded.")

_UNITS_USER = "Question: {question}\n\nAnswer given:\n{answer}"

_UNITS_REPORT = {
    "name": "report_quantities",
    "description": "Name the quantity each side names, with a quoted span from each.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asked": {"type": "string"},
            "asked_quote": {"type": "string", "description": "copied exactly from the question"},
            "delivered": {"type": "string"},
            "delivered_quote": {"type": "string", "description": "copied exactly from the answer"},
        },
        "required": ["asked", "delivered"],
    },
}

_UNITS_COMPARE_SYSTEM = (
    "Two quantities: the one an analytics question asked for, and the one the answer reported. Are "
    "they the SAME KIND of quantity?\n\n"
    "`same` when the answer reports what was asked, however tersely or differently worded. A bare "
    "number is `same` if it is the right kind of thing — an answer does not have to restate the "
    "question.\n"
    "`different` only when a reader would receive a different KIND of number: a count where a "
    "duration was asked for, a total where a rate was asked for, one thing measured in place of "
    "another.\n\n"
    "When in doubt, `same`. A false alarm costs more than a miss here.")

_UNITS_COMPARE_USER = "The question asked for : {asked}\nThe answer reported    : {delivered}"

_UNITS_COMPARE_REPORT = {
    "name": "report_units",
    "description": "Are the two quantities the same kind?",
    "input_schema": {"type": "object",
                     "properties": {"verdict": {"type": "string", "enum": ["same", "different"]},
                                    "why": {"type": "string"}},
                     "required": ["verdict"]},
}


def units_match(model, question: str, answer: str) -> dict:
    """{same, asked, delivered, grounded, why} — did the answer report the quantity that was asked
    for? `grounded` is false when either side's span could not be found, and an ungrounded reading
    is never allowed to produce a `different`.

    RUN THIS ON SERVED ANSWERS ONLY. A refusal delivers no quantity, so comparing one against the
    question asks whether a sentence is a duration and gets a `different` for a correct refusal —
    two of the three refusals in the first measurement, against zero false alarms on twelve served
    answers. The caller decides; this stays a pure comparison and does not read `outcome`.
    """
    blank = {"same": True, "asked": "", "delivered": "", "grounded": False, "why": ""}
    try:
        turn = model.respond(Conversation.opening(_UNITS_SYSTEM,
                                                  _UNITS_USER.format(question=question, answer=answer)),
                             [_UNITS_REPORT], force_tool="report_quantities", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return blank
    read = next((c.args for c in turn.tool_calls if c.name == "report_quantities"), None)
    if not read:
        return blank
    def norm(s):
        return " ".join(str(s or "").lower().split())
    grounded = (norm(read.get("asked_quote")) in norm(question)
                and norm(read.get("delivered_quote")) in norm(answer)
                and bool(norm(read.get("asked_quote"))) and bool(norm(read.get("delivered_quote"))))
    out = {"same": True, "asked": read.get("asked", ""), "delivered": read.get("delivered", ""),
           "grounded": grounded, "why": ""}
    if not grounded:
        return out
    try:
        turn = model.respond(
            Conversation.opening(_UNITS_COMPARE_SYSTEM,
                                 _UNITS_COMPARE_USER.format(asked=out["asked"],
                                                            delivered=out["delivered"])),
            [_UNITS_COMPARE_REPORT], force_tool="report_units", temperature=0)
    except Exception:                                                       # noqa: BLE001
        return out
    for call in turn.tool_calls:
        if call.name == "report_units":
            out["same"] = str(call.args.get("verdict")).strip().lower() != "different"
            out["why"] = str(call.args.get("why") or "")
    return out
