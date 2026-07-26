"""How a run ends: the typed outcome, and the vocabulary it is expressed in.

Every run exits through exactly one terminal tool, so an outcome is a field rather than a phrase
to be matched out of prose — no grader ever greps for "I cannot". The refusal vocabulary is the
same idea one level down: a refusal carries a CODE, so "why did it decline" is countable.

This module is a leaf on purpose. The vocabulary is shared by the agent, the guardrails and the
grader, and it used to live in tools.py — which meant the grading layer imported the tool module
to learn what a refusal could say. Nothing here knows about tools, models or the warehouse.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The three tools a run can END through. Every run exits by exactly one.
TERMINAL_TOOLS = ("answer", "refuse", "clarify")

# Every reason a refusal may carry. The `refuse` tool offers these as an enum, so the model
# cannot invent one, and the grader scores against the same list.
REFUSAL_REASONS = ["no_governed_definition", "out_of_coverage", "segment_undefined",
                   "no_causal_evidence", "false_premise", "wrong_measure", "wrong_grain",
                   "dimension_not_supported", "ungoverned_dimension_value",
                   "result_empty", "implausible_value", "other"]

# What the trajectory judge found, in ITS OWN terms. Assigned by the harness, never offered to
# the model — like `clarify`, and for the same reason: a second route to the same outcome is an
# ambiguity, and the refuse tool's enum is a treatment surface.
#
# These exist because the two vocabularies answer different questions. REFUSAL_REASONS says why
# a QUESTION cannot be answered from governed data; the judge says why THIS NUMBER does not
# answer it. Casting one onto the other lost most of the meaning — three of the judge's five
# findings collapsed onto no_governed_definition and a fourth onto `other` — and then the result
# was scored against the question's expected reason, which it could not express: nine of the
# twelve refusal codes were unreachable, so 59% of judge-driven refusals were graded against a
# code they were structurally incapable of producing.
VERIFIER_REASONS = ["verifier_wrong_thing", "verifier_wrong_kind", "verifier_wrong_scope",
                    "verifier_wrong_definition", "verifier_wrong_segment", "verifier_other"]


@dataclass
class Answer:
    question: str
    rung: int
    model: str
    answer: str | None
    explanation: str = ""
    outcome: str = "answer"        # answer | refuse | clarify | error
    reason: str | None = None      # refuse only: the coded reason
    missing: str | None = None     # refuse only: what the model says is missing
    source_metric: str | None = None  # answer only: the governed metric the value came from
    declared_value: float | None = None  # answer only: the served number (None = prose)
    source_result: str = ""       # the handle of the governed result the answer reports
    value_recovered: bool = False   # the number came from the answer text, not the typed field
    verifier_verdict: dict | None = None  # R9 only: the judge's verdict + the evidence it saw
    abstained: bool = False        # convenience mirror of outcome == "refuse"
    # Which output guardrail turned this answer into a refusal, when one did. The reason code
    # cannot say on its own: the judge maps several mismatch kinds onto no_governed_definition,
    # which is also governed_numbers' code.
    refused_by: str = ""
    tool_calls: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0          # prompt-cache HITS (a subset of input_tokens, billed ~10%)
    error: str | None = None
    steps: list = field(default_factory=list)
    turns: list = field(default_factory=list)   # one per model call: latency, cost, what it asked
    acts: list = field(default_factory=list)    # what the AFTER guardrails did to this answer
