"""How a run ends: the typed outcome, and the vocabulary it is expressed in.

Every run exits through exactly one terminal tool, so an outcome is a field rather than a phrase
to be matched out of prose — no grader ever greps for "I cannot". The refusal vocabulary is the
same idea one level down: a refusal carries a CODE, so "why did it decline" is countable.

This module is a leaf on purpose. The vocabulary is shared by the agent, the guardrails and the
grader, and it used to live in tools.py — which meant the grading layer imported the tool module
to learn what a refusal could say. Nothing here knows about tools, models or the warehouse.
"""

from __future__ import annotations

from dataclasses import field

from pydantic import SkipValidation, field_validator
from pydantic.dataclasses import dataclass

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
    "uninstrumented":
        "the question asks to measure something the warehouse does not instrument AT ALL — no "
        "metric, table, or column, in any layer, records it (customer satisfaction, when nothing "
        "captures a survey, a rating, or sentiment). Stronger than no_governed_definition: that is "
        "a metric not yet defined over data that exists; this is data that does not exist to define "
        "one over",
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

# Every reason a CLARIFICATION may carry, and what each one MEANS. A peer list rather than an
# extension of the refusal vocabulary, because the two answer opposite questions: a refusal says
# why nothing here answers, a clarification says what is here MORE THAN ONCE. Casting the second
# onto the first is the mistake that made `reason="clarify"` a placeholder for a year.
#
# WHY THE CODES ROUTE. The first two describe the LAYER and the rest describe the QUESTION, and
# that split is the whole reason the vocabulary exists. A question left underspecified is answered
# once and gone. A concept the layer defines twice comes back for every user who asks it, until a
# person decides — so it belongs on someone's desk, not only in the conversation.
#
# FOUR CODES, not the eight the taxonomy supports. Splitting period from segment from grain is a
# refinement worth making when there is traffic to make it on; shipping it before there is any is
# how a vocabulary the model has to guess at gets built. `REASON_MEANINGS` is the warning: twelve
# refusal codes shipped as bare identifiers and the model named the wrong one 49% of the time.
CLARIFY_MEANINGS: dict[str, str] = {
    "competing_definitions":
        "two or more GOVERNED definitions answer this question and they return different numbers. "
        "Name them in `candidates`, and say in `question` what differs between them",
    "undefined_term":
        "the question names a term the layer does not define at all, and more than one governed "
        "definition could stand in for it. Name the ones that could",
    "underspecified_request":
        "the question leaves out something the answer depends on — the period, the population, the "
        "level of detail, or what to compare against",
    "other":
        "none of the above fits. Prefer a specific code: `other` cannot be counted or routed, so "
        "reach for it only when nothing else is true",
}

CLARIFY_REASONS = list(CLARIFY_MEANINGS)

# Which codes describe the LAYER rather than the question. A clarification carrying one of these
# will recur for every user who asks that question until a human decides between the definitions,
# so it is a governance signal and not only a conversational turn. Kept here beside the codes so a
# reader of either finds the other, and so nothing downstream has to restate the split.
DEFINITION_AMBIGUITY = frozenset({"competing_definitions", "undefined_term"})

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


# The four ways a run can END, as a typed field rather than a phrase to match. The three terminal
# TOOLS, plus `error` — the non-tool exit the loop records when no terminal call was made (a run
# that gave up, exhausted its budget, or hit a persistent provider refusal).
OUTCOMES = (*TERMINAL_TOOLS, "error")


@dataclass
class Answer:
    """The typed result of one run. A validated (Pydantic) dataclass: it stays a real dataclass, so
    `dataclasses.asdict` still renders it for `agent.as_row` (the trace path) and the harness runner
    still reads it field-by-field, while construction now type-checks the outcome. It is NOT the
    on-disk contract — the stored row is hand-assembled in evals/runner.py — so validating here
    cannot move a published number; it only catches a loop that built a malformed Answer."""

    question: str
    rung: int
    model: str
    answer: str | None
    explanation: str = ""
    outcome: str = "answer"        # answer | refuse | clarify | error
    # SkipValidation on the three fields that carry RAW model output. The loop passes `reason`,
    # `missing` and `source_metric` straight through from tool_args (typed `Any` there on purpose,
    # because the boundary recovers rather than rejects), so a hallucinated refuse — `reason`
    # arriving as `["out_of_coverage"]` instead of the string — must be STORED and graded as a
    # mismatch, exactly as the stdlib dataclass did. Enforcing `str` here would raise a
    # ValidationError inside _record/_served, and run_agent catches only ProviderError, so it would
    # escape and kill the row (and a sweep with it) — the opposite of the typed-outcome guarantee.
    # The documented type stays `str | None`; only its enforcement is waived, and only on these three.
    # The coded reason a DECLINE carries. Refusals draw from REFUSAL_REASONS, clarifications from
    # CLARIFY_REASONS; `outcome` says which vocabulary applies, so one field serves both without
    # the two enums having to merge. Before the clarify tool carried a code this held the literal
    # string "clarify" — a non-member of the only vocabulary it claimed to hold.
    reason: SkipValidation[str | None] = None
    missing: SkipValidation[str | None] = None     # refuse only: what the model says is missing
    # clarify only: the governed definitions the agent says are in play. Named by the MODEL, which
    # is what makes them a measurement — it can name one that does not exist, or miss one that
    # does, and both are checkable against the catalogue with no gold answer. What each one RETURNS
    # is resolved by the harness rather than restated by the model, because asking for figures it
    # already holds only adds transcription errors.
    candidates: tuple = ()
    source_metric: SkipValidation[str | None] = None  # answer only: the governed metric the value came from
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
    # What each of those handbacks was given, so the repair can be told from a deletion: the
    # claim count and the broken claims' text going in, against `claims` above coming out.
    # Without it a repaired answer and a truncated one are the same stored row.
    repairs: tuple = ()
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
    # Everything the model was SHOWN, when the run asked for it (`run_agent(record_context=True)`);
    # None otherwise, which is every run of the frozen grid. `steps` records what the agent DID and
    # truncates each result at _TRACE_LIMIT; this records what it READ, whole. An experiment whose
    # treatment is the context needs the second, and cannot get it from the first.
    context: object = None

    @field_validator("outcome")
    @classmethod
    def _outcome_is_typed(cls, value: str) -> str:
        """A run ends as exactly one of OUTCOMES; anything else is a bug in the loop that built the
        Answer, not a value worth storing. Cheap to check here, where every Answer is born."""
        if value not in OUTCOMES:
            raise ValueError(f"outcome={value!r}; expected one of {list(OUTCOMES)}")
        return value
