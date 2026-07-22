"""Assemble what the agent gets at each rung: the system prompt and the toolbox.

The six rungs are additive context. The model and the questions never change; only
what this returns does. Rungs 4 and 5 deliver overlapping business knowledge two
different ways — verified example queries (concrete, scoped) then free-text rules —
so the experiment can compare them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .semantic import SemanticLayer
from .tools import Toolbox
from .tree import MetricTree

_ROOT = Path(__file__).resolve().parent.parent
_VERIFIED = _ROOT / "grounding" / "rung4_verified" / "verified_queries.yml"
_KB = _ROOT / "grounding" / "rung5_knowledge" / "knowledge_base.md"

RUNG_NAMES = {
    1: "messy data", 2: "star schema", 3: "semantic layer",
    4: "+ verified examples", 5: "+ knowledge base", 6: "+ metric tree",
}

_BASE = (
    "You are a data analyst for a habit-tracking app. Today is 2026-07-16; "
    "data is complete through 2026-07-12 (the last full ISO week, Monday-Sunday). "
    "Answer the user's business question using the tools provided.\n\n"
    "Rules:\n"
    "- Always compute numbers with the tools. Never guess, round from memory, or estimate a number.\n"
    "- Explore with get_schema / describe_table before writing SQL if you are unsure.\n"
)

# The reliability ladder's prompt component: what the agent is told about ending a
# task. R0 has no refusal channel; R1 adds it; R2 prices it; R3 offers the checks.
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
_RRUNG_PRICE = ("\n- Scoring: a correct answer scores +1, a refusal 0, a wrong answer -4. "
                "A wrong answer costs four refusals.")
_RRUNG_CHECKS = ("\n- Before answering or refusing, you may verify answerability with the check_* "
                 "tools: they consult the governed catalog, coverage windows, population "
                 "definitions, and causal edges.")
# R4+ (gate) and R5+ (fence) are structural: these lines only *describe* the enforced
# environment so the agent doesn't waste turns — the guarantee is in the tooling, not
# the prompt. Removing these lines would not let a fabrication through.
_RRUNG_ENFORCE = ("\n- Governance is enforced by the system: a request for an undefined metric or "
                  "for data outside coverage is blocked and returns no number — you cannot retrieve "
                  "what the governed layer refuses.")
_RRUNG_FENCE = ("\n- Raw SQL is not available. All data must come through governed metrics; if a "
                "question cannot be answered that way, refuse.")
# R6-R8: the output-verification family, split so each step's effect is measured on its
# own. Like the gate, these are structural — the checks run regardless of what the model
# does; the prompt lines only tell it so it doesn't waste turns.
# R6 — value resolution (a query-time guard, sibling of the gate/fence):
_RRUNG_RESOLVE = ("\n- Filter values are matched to governed members: name a segment in plain terms "
                  "('iOS', 'the annual plan') and it is resolved to the governed value; a value that "
                  "matches no governed member is rejected rather than returning an empty result.")
# R7 — spec decomposition (the answer's metric must match the question):
_RRUNG_SPEC = ("\n- Answers are checked before they are served: the metric behind your number must "
               "match what the question asks for — the same entity, population, measure, and grain. "
               "A valid metric that answers a slightly different question (active users for the user "
               "total, value moments for the habit count) is rejected; if no governed metric matches "
               "what was asked, refuse rather than report a near-miss.\n"
               "- When your answer is a number from a governed metric, name that metric in the "
               "answer's `source_metric` field, so the check knows exactly which definition produced it.")
# R8 — result-sanity (the returned value must be well-formed):
_RRUNG_SANITY = ("\n- A served number is checked for a well-formed result: an empty or null result, or "
                 "a value impossible for its unit (a share above 100, a negative count), is rejected "
                 "instead of being reported.")

_RUNG_NOTES = {
    1: ("\n\nThe tables are the raw application database: cryptic names, inconsistent "
        "capitalisation and encodings (e.g. platform stored as 'ios'/'iOS'/'IOS'), integer "
        "status codes, and columns whose meaning you must infer. Explore carefully."),
    2: ("\n\nThe data has been modelled into a clean star schema: dimension tables (dim_*) and "
        "fact tables (fct_*) with clear names, typed columns, and normalised values."),
    3: ("\n\nA semantic layer of governed metrics is available via list_metrics and query_metric. "
        "Prefer governed metrics for defined business measures (value moments, active users, MRR, "
        "power users, activation, etc.) so the definition, threshold, and population are always "
        "correct. You may still use run_sql for anything the metrics don't cover."),
    6: ("\n\nA metric tree is available. For diagnostic questions - why did a metric move, what is "
        "driving a change - call explain_change to decompose the movement through the tree, and "
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


@dataclass
class Grounding:
    rung: int
    rrung: int
    system: str
    toolbox: Toolbox


def build_grounding(con, rung: int, rrung: int = 1) -> Grounding:
    system = _BASE + _RRUNG_TERMINAL[min(rrung, 1)]
    if rrung >= 2:
        system += _RRUNG_PRICE
    if rrung >= 3:
        system += _RRUNG_CHECKS
    if rrung >= 4:
        system += _RRUNG_ENFORCE
    if rrung >= 5:
        system += _RRUNG_FENCE
    if rrung >= 6:
        system += _RRUNG_RESOLVE
    if rrung >= 7:
        system += _RRUNG_SPEC
    if rrung >= 8:
        system += _RRUNG_SANITY
    system += _RUNG_NOTES[1] if rung == 1 else _RUNG_NOTES[2]  # rungs 2-6 sit on the star
    if rung >= 3:
        system += _RUNG_NOTES[3]
    if rung >= 4:
        system += _verified_block()
    if rung >= 5:
        system += _knowledge_block()
    if rung >= 6:
        system += _RUNG_NOTES[6]

    semantic = SemanticLayer(con) if rung >= 3 else None
    tree = MetricTree(semantic) if rung >= 6 else None
    return Grounding(rung=rung, rrung=rrung, system=system,
                     toolbox=Toolbox(con, rung, semantic, tree, rrung))
