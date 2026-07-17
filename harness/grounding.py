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
    "- When you are confident, call final_answer with the value and a one-line explanation.\n"
    "- If the data cannot answer the question reliably, call final_answer and say so rather "
    "than inventing a number. A truthful 'I can't' beats a confident wrong answer."
)

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
    system: str
    toolbox: Toolbox


def build_grounding(con, rung: int) -> Grounding:
    system = _BASE
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
    return Grounding(rung=rung, system=system, toolbox=Toolbox(con, rung, semantic, tree))
