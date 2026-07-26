"""Assemble what the agent gets at each rung: the system prompt and the toolbox.

The six rungs are additive context. The model and the questions never change; only
what this returns does. Rungs 4 and 5 deliver overlapping business knowledge two
different ways — verified example queries (concrete, scoped) then free-text rules —
so the experiment can compare them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from semantic.semantic import SemanticLayer
from semantic.tree import MetricTree

from .guardrails import LADDER, Guardrails, incoherent
from .tools import Toolbox

_ROOT = Path(__file__).resolve().parent.parent
_VERIFIED = _ROOT / "context" / "verified_queries.yml"
_KB = _ROOT / "context" / "knowledge_base.md"

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
# task. R0 (abstain off) has no refusal channel; R1 adds the typed refuse tool. Each
# later control appends its own prompt line in build_grounding, gated by its flag.
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
_RRUNG_CHECKS = ("\n- Before answering or refusing, you may verify answerability with the check_* "
                 "tools: they consult the governed catalog, coverage windows, segment "
                 "definitions, and causal edges.")
# gate (R3) and the fence / tool_restriction (R4) are structural: these lines only
# *describe* the enforced environment so the agent doesn't waste turns — the guarantee
# is in the tooling, not the prompt. Removing these lines would not let a fabrication through.
_RRUNG_ENFORCE = ("\n- Governance is enforced by the system: a request for an undefined metric or "
                  "for data outside coverage is blocked and returns no number — you cannot retrieve "
                  "what the governed layer refuses.")
_RRUNG_TOOL_RESTRICTION = ("\n- Raw SQL is not available. All data must come through governed metrics; if a "
                "question cannot be answered that way, refuse.")
# resolve (R5) then the output family — transparency (R6), single_metric (R7),
# output_validation (R8) — split so each step's effect is measured on its own. Like the
# gate, these are structural: the checks run regardless of what the model does; the
# prompt lines only tell it so it doesn't waste turns.
# resolve (R5) — value resolution (a query-time guard, sibling of the gate/fence):
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
# transparency (R6) + single_metric (R7) — the served number is shown, and constrained to one governed result.
_RRUNG_TRANSPARENCY = ("\n- Every governed result now shows you a [scope] line (what segment and time "
                       "window it actually covers) and the exact [sql]. Read them: if the scope is not "
                       "what the question asked for, fix the query or refuse — never report a number "
                       "whose scope doesn't match the question.")
_RRUNG_SINGLE_METRIC = ("\n- Answer with exactly ONE governed metric's own value. Do not build the answer "
                        "by hand from several numbers (no rate times a count, no metric A plus metric B). "
                        "If answering would need a metric that doesn't exist, refuse "
                        "(no_governed_definition) rather than derive it.")
# trajectory_verify (R9) — the verifier:
_RRUNG_VERIFIER = ("\n- After you answer, a verifier inspects the metric you used, its definition, the "
                   "exact SQL, and the filters you added, and checks they truly answer the question: the "
                   "right thing, the right KIND of number (a count for 'how many', an amount for 'how "
                   "much', a rate for 'what rate / average / per user'), and the right scope (no filter "
                   "the question did not ask for). If the metric answers a different question, your answer "
                   "is rejected — so choose the metric that matches what was asked, or refuse.")

_RUNG_NOTES = {
    1: ("\n\nThe tables are the raw application database: cryptic names, inconsistent "
        "capitalisation and encodings (e.g. platform stored as 'ios'/'iOS'/'IOS'), integer "
        "status codes, and columns whose meaning you must infer. Explore carefully."),
    2: ("\n\nThe data has been modelled into a clean star schema: dimension tables (dim_*) and "
        "fact tables (fct_*) with clear names, typed columns, and normalised values."),
    3: ("\n\nA semantic layer of governed metrics is available via list_metrics and query_metric. "
        "Prefer governed metrics for defined business measures (value moments, active users, MRR, "
        "power users, activation, etc.) so the definition, threshold, and segment are always "
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
    """Everything one configuration gives the agent: what it is told, what it may do, and the
    governed layer both are defined against."""

    rung: int
    system: str
    toolbox: Toolbox
    guardrails: Guardrails | None = None
    semantic: SemanticLayer | None = None

    def fingerprint(self) -> str:
        """A short, stable hash of everything the model is shown: the assembled system prompt and
        the exact tool specs (names, descriptions, enums, required fields).

        The tool specs are as much a treatment as the prompt — a reworded description or a
        widened enum changes the agent's behaviour just as surely — yet nothing else records
        them. Two runs whose fingerprints differ are not comparable however alike their labels
        read, and a refactor that was meant to leave the model's view untouched proves it by
        leaving this unchanged."""
        surface = self.system + "\n" + json.dumps(self.toolbox.specs(), sort_keys=True)
        return hashlib.sha256(surface.encode()).hexdigest()[:12]


def build_grounding(con, rung: int,
                    guardrails: Guardrails | None = None) -> Grounding:
    # Guardrails is the one primitive; default R1 (abstention). A ladder preset is LADDER[n], an
    # ablation cell any Guardrails set. The prompt is assembled from the SAME set the Toolbox
    # enforces, so a cell can never describe a control that is not running — that would make the
    # measurement vary with the treatment, the one thing an ablation must not do.
    g = guardrails if guardrails is not None else LADDER[1]
    # Fail here rather than build a system that cannot do what its label says. An incoherent
    # (rung, guardrails) pair still produces rows, and those rows are indistinguishable from
    # real ones once written — the measurement would vary with the treatment, which is the one
    # thing an ablation must not do.
    bad = incoherent(g, rung)
    if bad:
        raise ValueError(f"incoherent grounding: rung {rung} with {g.label()} — {bad}")
    system = _BASE + _RRUNG_TERMINAL[1 if g.abstain else 0]
    if g.check_tools:
        system += _RRUNG_CHECKS
    if g.gate:
        system += _RRUNG_ENFORCE
    if g.tool_restriction:
        system += _RRUNG_TOOL_RESTRICTION
    if g.resolve:
        system += _RRUNG_RESOLVE
    if g.transparency:
        system += _RRUNG_TRANSPARENCY
    if g.single_metric:
        system += _RRUNG_PROVENANCE + _RRUNG_SINGLE_METRIC
    if g.output_validation:
        system += _RRUNG_OUTPUT_VALIDATION
    if g.trajectory_verify:
        system += _RRUNG_VERIFIER
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
    return Grounding(rung=rung, guardrails=g, system=system, semantic=semantic,
                     toolbox=Toolbox(con, rung, semantic, tree, guardrails=g))
