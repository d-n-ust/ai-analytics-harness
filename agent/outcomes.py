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

# Every reason a refusal may carry, and what each one MEANS. The `refuse` tool offers the keys as
# an enum, so the model cannot invent one, and the grader scores against the same list.
#
# The meanings are stated here because the enum used to ship as twelve bare strings with no
# descriptions at all. Asked to pick one, the model guessed: across 180 correct refusals it named
# a different code than the question expected 49% of the time, and `other` — the catch-all — was
# chosen 26 times over a specific code that existed and fitted. A vocabulary the model has to
# infer from identifiers is not a typed protocol; it is a spelling test.
#
# Two of these describe what came BACK rather than why the question is unanswerable, and that
# distinction is load-bearing: `result_empty` is the honest answer when nothing diagnosed the
# cause, and the WRONG answer when something could have. Which is available depends on the
# guardrails, so it is spelled out in the descriptions rather than left for the model to weigh.
REASON_MEANINGS: dict[str, str] = {
    "no_governed_definition":
        "no governed metric defines what was asked (ARR, churn rate, an engagement score)",
    "out_of_coverage":
        "the metric exists but the period asked for falls outside the data's coverage window",
    "segment_undefined":
        "the group asked about (whales, churned users, free tier) is not a governed segment",
    "no_causal_evidence":
        "the question asks WHY or WHETHER X caused Y and no governed causal evidence links them",
    "false_premise":
        "the question asserts something untrue — a change that did not happen, an event that "
        "never occurred. Put the correction in `missing`",
    "wrong_measure":
        "a metric exists for this thing but measures a different quantity than the one asked for",
    "wrong_grain":
        "the metric exists but not at the time grain or level of detail the question needs",
    "dimension_not_supported":
        "the metric cannot be broken down or filtered by the dimension named at all",
    "ungoverned_dimension_value":
        "the dimension exists, but the VALUE named is not one of its governed members "
        "(Mexico when only 8 countries are covered)",
    "result_empty":
        "the query ran and came back with nothing. Use this ONLY when you cannot say why — if "
        "you know the period is uncovered or the filter value is not a governed member, give "
        "THAT reason instead, because it is the one that can be acted on",
    "implausible_value":
        "a number came back that cannot be right for its unit (a share above 100, a negative count)",
    "other":
        "none of the above fits. Prefer a specific reason: `other` cannot be counted, routed or "
        "acted on, so reach for it only when nothing else is true",
}

REFUSAL_REASONS = list(REASON_MEANINGS)

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


def declared_handles(args: dict) -> tuple:
    """The `sources` an answer declared, as clean handles — `['[r2]', 'r3']` -> `('r2', 'r3')`.

    One reader for one field: the AFTER guardrails see the raw tool arguments and the loop sees
    them again when it builds the Answer, and two copies of "what counts as a handle" would drift
    the way the provenance check once did across three files.

    Accepts a bare string as well as a list, because a model asked for an array will sometimes
    send `"r2"` or `"r2, r3"`, and refusing a well-meant answer over its punctuation would measure
    the schema rather than the analysis. `source_result` is read as a fallback because rows and
    replies written before this field was plural carry that name. Empty entries drop out, so
    "declared nothing" and "declared junk" arrive downstream as the same empty tuple."""
    value = (args or {}).get("sources")
    if value in (None, "", [], ()):
        value = (args or {}).get("source_result")
    if isinstance(value, str):
        value = value.replace(",", " ").split()
    return tuple(h for h in (str(v).strip().strip("[]") for v in (value or ())) if h)


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
    # The handle(s) of the governed result(s) the answer reports. A list because a comparison
    # has two operands. Stored rows written before this was plural carry `source_result`, a
    # single string; readers of archived runs accept both, the way DECOMPOSE_TOOLS does.
    sources: tuple = ()
    value_recovered: bool = False   # the number came from the answer text, not the typed field
    # Did the answer tool CARRY a typed `value` field (governed_numbers, R7+)? When it did,
    # `declared_value` is the model's own statement of what it served and nothing needs to read
    # the prose; when it did not, the prose is all there is. Recorded rather than inferred: the
    # two cases are indistinguishable from `declared_value` alone, since it is also populated by
    # recovery from the answer text.
    typed_value: bool = False
    # What the answer broke itself into, and what the audit found. Recorded on every run where
    # the schema offered `claims`; the audit never changes the outcome on this rung, so a row
    # carries the measurement without the measurement having moved the thing measured.
    claims: tuple = ()
    claim_audit: dict | None = None
    # How many times the answer was handed back for citing something that does not
    # exist. A run that needed a second go is not the same as one that got it right.
    claim_retries: int = 0
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
