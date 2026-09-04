"""The system prompt: every line the agent is told, and how they are assembled.

Text only. What the agent may DO is the guardrails' business and what it can REACH is the
warehouse's; this module decides what it is told about either. Splitting it out matters because
the prompt is a treatment variable — a reworded line changes the experiment — and a file that is
nothing but treatment text is a file whose diff is always worth reading.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..core.protocol import ROLE, Protocol
from ..core.rungs import capabilities

# Resolved inside this package, not from the repo root. The files are package data and must
# travel with the wheel; reaching a level up found them from a checkout and found nothing at
# all from site-packages, which surfaced as a missing-file error at prompt-assembly time.
# The rung data files live at the agent package root (agent/context/), one level above this
# module since the runtime/ move.
_HERE = Path(__file__).resolve().parent.parent
_VERIFIED = _HERE / "context" / "verified_queries.yml"
_KB = _HERE / "context" / "knowledge_base.md"

_BASE = (
    "You are a data analyst for a habit-tracking app. Today is 2026-07-16; "
    "data is complete through 2026-07-12 (the last full ISO week, Monday-Sunday). "
    "Answer the user's business question using the tools provided.\n\n"
    "Rules:\n"
    "- Always compute numbers with the tools. Never guess, round from memory, or estimate a number.\n"
    "- Explore with get_schema / describe_table before writing SQL if you are unsure.\n"
)

# The reliability ladder's prompt component: what the agent is told about ending a
# task. R0 (abstain off) has no refusal channel; R1 adds the typed refuse tool. Each
# later guardrail appends its own prompt line in build_grounding, gated by its flag.
_RRUNG_TERMINAL = {
    0: ("- End with the `answer` tool: the value plus a one-line explanation. If the question "
        "is too ambiguous to attempt, end with `clarify`."),
    1: ("- End with exactly one terminal tool: `answer` when the data supports a reliable answer; "
        "`refuse` when it does not — give the coded reason and name what is missing; `clarify` when "
        "the question is too ambiguous to answer either way.\n"
        "- If a question assumes something untrue — a change that didn't happen, an event that never "
        "occurred — do not accept the premise and answer around it: `refuse` with reason "
        "`false_premise`, and put the correction in `missing` (e.g. \"it didn't fall — it rose to 227\").\n"
        "- A truthful refusal beats a confident wrong answer."),
}

# The same two lines with every mention of `clarify` removed, for the arm where the tool is not
# offered. Written out rather than assembled from parts: the strings above are the exact prompt
# every published cell was run under, they are pinned by tests/test_surface.py across 24 cells, and
# rebuilding them from fragments risks moving a space and re-fingerprinting the archive to prove a
# tidiness point. Two literals, and the diff between each pair is one clause.
_RRUNG_TERMINAL_NO_CLARIFY = {
    0: "- End with the `answer` tool: the value plus a one-line explanation.",
    1: ("- End with exactly one terminal tool: `answer` when the data supports a reliable answer; "
        "`refuse` when it does not — give the coded reason and name what is missing.\n"
        "- If a question assumes something untrue — a change that didn't happen, an event that never "
        "occurred — do not accept the premise and answer around it: `refuse` with reason "
        "`false_premise`, and put the correction in `missing` (e.g. \"it didn't fall — it rose to 227\").\n"
        "- A truthful refusal beats a confident wrong answer."),
}

# WHAT THE OTHER LINES NEVER SAID. Both of the originals describe clarification as what to do when
# the agent is stuck — "too ambiguous to attempt", "too ambiguous to answer either way". That is a
# fact about the agent's state. The rule is a fact about the data model, and an agent that can read
# a catalogue does not have to feel stuck to apply it: refuse when NOTHING answers the question,
# clarify when MORE THAN ONE thing does.
#
# This is a prompt-only rung, and this repository already knows what those tend to be worth: R6
# enforced nothing and contributed nothing. It is worth running for the same reason — a null here
# is a result about whether telling a model the rule is enough.
_RRUNG_TYPED_CLARIFY = (
    "\n- `clarify` is not a last resort. Refuse when NOTHING in the governed layer answers the "
    "question; clarify when MORE THAN ONE definition answers it and they would give different "
    "numbers.\n"
    "- When you clarify, name the governed metrics in `candidates` and ask about what DIFFERS "
    "between them, in the user's own words — not about which metric name to pick. Someone outside "
    "the data team has to be able to answer your question.")

# `ambiguity_check` is structural, like the coverage check and the tool restriction: this line only
# DESCRIBES the enforced environment so the agent does not spend a turn discovering it. Removing the
# sentence would not let a contested metric through — the block is in guardrails/before.py.
_RRUNG_AMBIGUITY = (
    "\n- Governance is enforced on AMBIGUITY too: a governed metric that shares its concept with "
    "another governed definition is blocked, and the block names the competing definition and what "
    "separates them. When that happens, do not pick one and do not average them — end with "
    "`clarify` and ask about the difference the block named.")

_RRUNG_SCOPE_DECLARATION = (
    "\n- If a governed query is blocked for ambiguity AND the user's question already said which "
    "reading it wanted, retry the call with `resolved_scope` set to the discriminator the block "
    "named, word for word. If the question did not say, do not invent one — clarify instead.")

# `ambiguity_disclosure` blocks nothing, so unlike the two above this line is the whole mechanism
# on the model's side: the extra figure arrives in the tool result and this says what to do with it.
_RRUNG_AMBIGUITY_DISCLOSURE = (
    "\n- A governed result may carry an `[also]` line naming a second governed definition of the "
    "same concept and the different number it returns. When it does and the question did not say "
    "which reading it wanted, answer with BOTH figures and name what separates them. Do not pick "
    "one silently, and do not average them.")

_RRUNG_DISCLOSURE_CHECK = (
    "\n- Naming both figures is CHECKED, not trusted: an answer that reports one reading of a "
    "contested concept and omits the other is handed back to you once, with both numbers, to send "
    "again.")

# `filter_vocabulary` and `constraint_regression` are structural, like the coverage check: the
# lines below describe the environment so the agent does not spend turns discovering it.
_RRUNG_FILTER_VOCABULARY = (
    "\n- `filters` and `group_by` accept only this layer's own dimension names, spelled exactly as "
    "`list_metrics` prints them. A name that is not on that list cannot be sent.")

# `scope_classifier` changes nothing the agent must do — it only decides whether the sentence above
# is enforced on this question — so it gets no line of its own. Named here because the registry
# requires every guardrail to be traceable to the files that implement it.
_RRUNG_CONSTRAINT_REGRESSION = (
    "\n- If a call fails, FIX it rather than widening it. An answer whose number comes from a call "
    "that dropped a restriction an earlier call asked for is handed back: answering a broader "
    "question than the one asked is a wrong answer, not a partial one.")

_RRUNG_CHECKS = ("\n- Before answering or refusing, you may verify answerability with the check_* "
                 "tools: they consult the governed catalog, coverage windows, segment "
                 "definitions, and causal edges.")
# The coverage check (R3) and the tool restriction (R4) are structural: these lines only
# *describe* the enforced environment so the agent doesn't waste turns — the guarantee
# is in the tooling, not the prompt. Removing these lines would not let a fabrication through.
_RRUNG_ENFORCE = ("\n- Governance is enforced by the system: a request for an undefined metric or "
                  "for data outside coverage is blocked and returns no number — you cannot retrieve "
                  "what the governed layer refuses.")
_RRUNG_TOOL_RESTRICTION = ("\n- Raw SQL is not available. All data must come through governed metrics; if a "
                "question cannot be answered that way, refuse.")
# resolve (R5) then the output family — transparency (R6), governed_numbers (R7),
# output_validation (R8) — split so each step's effect is measured on its own. Like the
# coverage check, these are structural: the guardrails run regardless of what the model does; the
# prompt lines only tell it so it doesn't waste turns.
# resolve (R5) — value resolution (a query-time guard, sibling of the coverage check/tool restriction):
_RRUNG_RESOLVE = ("\n- Filter values are matched to governed members: name a segment in plain terms "
                  "('iOS', 'the annual plan') and it is resolved to the governed value; a value that "
                  "matches no governed member is rejected rather than returning an empty result.")
# The typed provenance fields — read by every output check that inspects the served number:
_RRUNG_PROVENANCE = ("\n- When your answer is a single number, put that number in the answer's `value` "
                     "field, and if it came from a governed metric name that metric in `source_metric`, "
                     "so the check reads exactly what you served and which definition produced it. A "
                     "non-numeric answer (an assessment, a driver) leaves `value` out and is not checked.")
# R8 — output validation (the returned value must be well-formed):
_RRUNG_OUTPUT_VALIDATION = ("\n- A served number is checked for a well-formed result: an empty or null result, or "
                 "a value impossible for its unit (a share above 100, a negative count), is rejected "
                 "instead of being reported.")
# transparency (R6) + governed_numbers (R7) — the served number is shown, and must be governed.
_RRUNG_TRANSPARENCY = ("\n- Every governed result now shows you a [scope] line (what segment and time "
                       "window it actually covers) and the exact [sql]. Read them: if the scope is not "
                       "what the question asked for, fix the query or refuse — never report a number "
                       "whose scope doesn't match the question.")
_RRUNG_GOVERNED_NUMBERS = ("\n- The number you serve must be a governed result, or a comparison of TWO "
                           "results of the SAME metric — its change, ratio or percent change between two "
                           "periods or scopes. You may compare governed numbers; you may not compose new "
                           "ones. Combining DIFFERENT metrics (a rate times a count, metric A over metric "
                           "B) invents a measure nothing defines: if answering would need a metric that "
                           "doesn't exist, refuse (no_governed_definition) rather than derive it.")
# trajectory_verify (R9) — the verifier:
_RRUNG_VERIFIER = ("\n- After you answer, a verifier inspects the metric you used, its definition, the "
                   "exact SQL, and the filters you added, and checks they truly answer the question: the "
                   "right thing, the right KIND of number (a count for 'how many', an amount for 'how "
                   "much', a rate for 'what rate / average / per user'), and the right scope (no filter "
                   "the question did not ask for). If the metric answers a different question, your answer "
                   "is rejected — so choose the metric that matches what was asked, or refuse.")
# protocol.purpose — the only line here that asks for something rather than describing what
# the system will do. It requests a record, not a behaviour: the guardrail cannot enforce it, and
# how often the model complies is exactly what the rung is there to measure.
_RRUNG_PURPOSE = ("\n- Each governed call takes an optional `because`: one line, in plain words, on "
                  "what you are trying to establish with it (\"check whether the drop is uniform "
                  "across regions or concentrated in one\"). Write the sub-question you are "
                  "answering, not a label for the call. It does not change the result — it records "
                  "how you got to the answer, so a reader can follow your reasoning.")
# protocol.claims — asks for a record, like `purpose`, and for the same reason: the
# guardrail cannot enforce a decomposition the model declines to give, and how well the model
# breaks its own answer apart is what this rung exists to measure.
_RRUNG_CLAIMS = ("\n- The answer takes a `claims` list: one entry per assertion your answer makes, "
                 "each naming the governed value it rests on. Every governed result prints a "
                 "handle and its fields, so cite the VALUE — `r1:days_per_user.pct_change`, or "
                 "`r2:paid_search` for one row of a breakdown — not just the result. If your "
                 "answer reports five figures and draws one conclusion, that is six claims. A "
                 "claim that is a CONCLUSION — \"X is the primary driver\", \"Y did not cause it\" "
                 "— sets `premises` naming the earlier claims it follows from, instead of "
                 "`sources`. Saying days_per_user is the primary driver means comparing the three "
                 "contribution shares, so those three claims are its premises. It does not change "
                 "your answer.")
# protocol.rendered — the model stops writing measurements. Stated as a mechanism, because it is
# one: the field is simply not there to fill.
_RRUNG_RENDERED = ("\n- You do NOT write the wording of a claim that cites data. Name the values in "
                   "`sources` and leave `text` empty; the sentence is written from those values "
                   "and reads exactly as they do. `text` is for a CONCLUSION only — so anything "
                   "you write there is reasoning, and must name the claims it follows from in "
                   "`premises`. A claim never carries both.")
# protocol.repair — a mechanism line, like every guardrail above and unlike the two declaration
# lines: it describes what the system will do, so it has no role/rule variant. The framing
# treatment is about how an ACCOUNT is asked for, not about how a check is announced.
_RRUNG_CITATION_REPAIR = ("\n- A claim citing something that does not exist is handed back to you "
                          "with the fault named, the same way a call with a bad argument is, and "
                          "you get to fix it. Cite one value per source and this never fires.")

# --- the framing experiment -------------------------------------------------------------- #
# The lines above tell the model, twice and in as many words, that declaring "does not change
# your answer". Then we measured how much it cared: 88% adoption, 43% of reasoning answers
# declaring a conclusion, and declarations the first thing dropped when a closing turn rushes it.
# That is the prompt working as written, not a fact about the model.
#
# The alternative says being checkable IS the job. Nothing about the MECHANISM changes — the audit
# still records and never refuses — because inert-in-the-check and unimportant-in-the-role are
# different claims, and the design conflated them. Which framing is live is a treatment, so it is
# read once per run and stamped on every row.
_ROLE_PURPOSE = ("\n- Each governed call takes an optional `because`: one line, in plain words, on "
                 "what you are trying to establish with it (\"check whether the drop is uniform "
                 "across regions or concentrated in one\"). Write the sub-question you are "
                 "answering, not a label for the call — it is the record of how you reached the "
                 "answer, and a reader who was not here has nothing else to follow.")

_ROLE_CLAIMS = ("\n- Being checkable is part of the job, not paperwork after it. An answer is the "
                "number AND the account of it: the separate statements you are making, and which "
                "governed value each one rests on. A figure a reader cannot trace back is not an "
                "answer, however right it happens to be."
                "\n- So give the `claims` list with every answer: one entry per assertion. Cite the "
                "VALUE, not the result — `r1:days_per_user.pct_change`, or `r2:paid_search` for one "
                "row of a breakdown; every governed result prints its citable fields on a [cite] "
                "line. A result that returns no numbers — what the tree says about a causal edge, "
                "whether a segment is defined — is cited by its handle alone (`r2`), and it is "
                "evidence like any other: it is what makes a refusal a governed finding rather "
                "than an opinion."
                "\n- A CONCLUSION rests on other claims, not on data: set `premises` to the earlier "
                "claims it follows from. \"Days per user is the primary driver\" IS a comparison of "
                "the three contribution shares — writing it as one more figure hides the reasoning "
                "that makes it true, and a reader cannot check what is hidden."
                # The prompt described exactly one layer, and then 83% of answers came back as flat
                # lists with the conclusion asserted alongside the measurements. The hand-built
                # reference graphs need TWO layers on every one of three questions, so a model
                # producing one was doing what it was told.
                "\n- Conclusions build on conclusions. Your final answer is itself a claim, and its "
                "premises are usually the comparison you just made plus the fact you set out to "
                "explain — not the raw figures again. So a diagnostic answer typically looks like: "
                "measurements citing values, then a comparison across those measurements, then the "
                "answer to the question resting on that comparison. Three levels of evidence, not "
                "a list with a verdict at the bottom.")


_RUNG_NOTES = {
    1: ("\n\nThe tables are the raw application database: cryptic names, inconsistent "
        "capitalisation and encodings (e.g. platform stored as 'ios'/'iOS'/'IOS'), integer "
        "status codes, and columns whose meaning you must infer. Explore carefully."),
    2: ("\n\nThe data has been modelled into a clean star schema: dimension tables (dim_*) and "
        "fact tables (fct_*) with clear names, typed columns, and normalised values."),
    # No metric names here. The parenthetical used to list five of the fifteen ("value moments,
    # active users, MRR, power users, activation"), which made the prompt a second, stale copy of
    # the catalogue: it survived any change to the layer, so an experiment that renamed or stripped
    # those metrics still handed the model their names. The catalogue is the one place they live.
    3: ("\n\nA semantic layer of governed metrics is available via list_metrics and query_metric. "
        "Prefer governed metrics for defined business measures so the definition, threshold, and "
        "segment are always correct. You may still use run_sql for anything the metrics don't cover."),
    6: ("\n\nA metric tree is available. For diagnostic questions - why did a metric move, what is "
        "driving a change - call decompose_change to attribute the movement to the metrics that compose it, and "
        "get_metric_tree to see its structure. The decomposition's numbers are computed for you: "
        "narrate them and their evidence, and do not invent contributions or causes the tree "
        "does not carry."),
}


def _verified_block() -> str:
    vq = yaml.safe_load(_VERIFIED.read_text())["verified_queries"]
    lines = ["\n\n--- VERIFIED EXAMPLE QUERIES (approved question->query pairs; follow these patterns) ---"]
    for ex in vq:
        lines.append(f"\nQ: {ex['q']}\n   -> {ex['call']}"
                     + (f"\n   ({ex['why']})" if ex.get("why") else ""))
    return "\n".join(lines)


def _knowledge_block() -> str:
    return ("\n\n--- KNOWLEDGE BASE (business rules and context; apply where relevant) ---\n"
            + _KB.read_text())




def system_prompt(rung: int, g, protocol: Protocol | None = None) -> str:
    """Assemble what the agent is told, from the rung it is grounded at, the guardrails it runs
    under, and the protocol it declares by.

    Each guardrail contributes a line describing itself. Those lines are not the guardrail — the
    structural ones hold whether or not the model reads them — but a model that does not know
    raw SQL is gone will waste turns discovering it. The set that writes the prompt is the SAME
    set the runtime enforces, so a cell can never describe a guardrail that is not running."""
    protocol = protocol or Protocol()
    terminal = _RRUNG_TERMINAL if g.clarify else _RRUNG_TERMINAL_NO_CLARIFY
    system = _BASE + terminal[1 if g.abstain else 0]
    if g.typed_clarify:
        system += _RRUNG_TYPED_CLARIFY
    if g.ambiguity_check:
        system += _RRUNG_AMBIGUITY
    if g.scope_declaration:
        system += _RRUNG_SCOPE_DECLARATION
    if g.ambiguity_disclosure:
        system += _RRUNG_AMBIGUITY_DISCLOSURE
    if g.filter_vocabulary:
        system += _RRUNG_FILTER_VOCABULARY
    if g.disclosure_check:
        system += _RRUNG_DISCLOSURE_CHECK
    if g.constraint_regression:
        system += _RRUNG_CONSTRAINT_REGRESSION
    if g.check_tools:
        system += _RRUNG_CHECKS
    if g.coverage_check:
        system += _RRUNG_ENFORCE
    if g.tool_restriction:
        system += _RRUNG_TOOL_RESTRICTION
    if g.resolve:
        system += _RRUNG_RESOLVE
    if g.transparency:
        system += _RRUNG_TRANSPARENCY
    if g.governed_numbers:
        system += _RRUNG_PROVENANCE + _RRUNG_GOVERNED_NUMBERS
    if g.output_validation:
        system += _RRUNG_OUTPUT_VALIDATION
    if g.trajectory_verify:
        system += _RRUNG_VERIFIER
    role = protocol.framing == ROLE
    if protocol.purpose:
        system += _ROLE_PURPOSE if role else _RRUNG_PURPOSE
    if protocol.claims:
        system += _ROLE_CLAIMS if role else _RRUNG_CLAIMS
    if protocol.rendered:
        system += _RRUNG_RENDERED
    if protocol.repair:
        system += _RRUNG_CITATION_REPAIR
    # Asked of the rung's capabilities, never derived from its number: rung 7 holds the tree
    # without the two advisory blocks, so `rung >= n` says nothing about what the agent has.
    caps = capabilities(rung)
    system += _RUNG_NOTES[2] if caps.star else _RUNG_NOTES[1]
    if caps.semantic:
        system += _RUNG_NOTES[3]
    if caps.examples:
        system += _verified_block()
    if caps.knowledge:
        system += _knowledge_block()
    if caps.tree:
        system += _RUNG_NOTES[6]
    return system
