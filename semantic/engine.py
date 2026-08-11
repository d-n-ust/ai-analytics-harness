"""What a semantic layer must provide, so the engine behind it becomes a study variable.

Experiment 02 produced a finding about RENDERING — segments appeared in a global list that never
said which metric offered them. That is a property of this repository's renderer, not of semantic
layers, and it makes a fair objection: *you measured your own file format.* Answering it means
running the same study against a real engine, which means the engine cannot be hard-wired.

THE INTERFACE SPLITS IN TWO, AND ONLY ONE HALF IS PORTABLE.

    agent surface     what the model reads and calls — a catalogue, a query, three checks, and
                      the two lookups that BUILD THE TOOL SCHEMA. Any semantic layer can serve it.
                      The last two were found by running the agent, not by reading call sites:
                      the schema narrows `metric` to the catalogue and offers `segment` only when
                      the layer declares any, so the schema is part of the treatment surface.
    governance        what the GUARDRAILS read — coverage windows, governed segment names,
                      dimension members, additivity, redundant-filter detection. These encode
                      decisions this project makes about a layer. MetricFlow has none of them:
                      no coverage window, no named segments, no additivity declaration.

So `MetricEngine` is the agent surface only. The governance half stays on `SemanticLayer`, because
it is not a semantic-layer feature that MetricFlow happens to lack — it is a governance model this
harness adds on top of one.

CAPABILITIES ARE DECLARED, NOT DISCOVERED. An engine states what it cannot do, and a study that
needs it is refused when it loads rather than crashing somewhere inside a paid run. A guardrail
that calls `coverage_violations` on an engine with no coverage window is not a bug to handle at the
call site; it is a combination that should never have been assembled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["Capabilities", "MetricEngine", "check_compatible"]


@dataclass(frozen=True)
class Capabilities:
    """What an engine can answer. Every field defaults to the thing a plain metric layer has."""

    name: str
    catalogue: bool = True      # can render the metric list the agent reads
    query: bool = True          # can compute a metric
    coverage: bool = False      # knows a data-coverage window, so `in_coverage` means something
    segments: bool = False      # has NAMED, declared segments rather than raw predicates
    members: bool = False       # can resolve a dimension member string to a governed value
    additivity: bool = False    # declares whether a measure may be summed over time

    def missing(self, needed: tuple) -> tuple:
        return tuple(n for n in needed if not getattr(self, n))


@runtime_checkable
class MetricEngine(Protocol):
    """The agent surface: seven methods.

    Deliberately not the whole of `SemanticLayer`: widening this to fifteen methods would mean no
    engine but ours could ever implement it, which defeats the point of having a protocol.
    """

    @property
    def capabilities(self) -> Capabilities: ...

    @property
    def metrics(self) -> dict:
        """Metric name -> declaration. Read for the tool schema's enum and by the checks."""

    def list_metrics_text(self) -> str:
        """The catalogue as the model reads it. THE treatment surface for every layer study."""

    def query_with_sql(self, name: str, **kw) -> tuple:
        """`(sql, columns, rows)` — the compiled SQL travels with the answer so the model can be
        shown what was computed rather than asked to trust a number."""

    def metric_exists(self, term: str) -> tuple:
        """`(exists, explanation)` for a term the model named."""

    def in_coverage(self, start=None, end=None, region=None, country=None) -> tuple:
        """`(covered, explanation)`. An engine without a coverage window must declare
        `coverage=False` rather than returning a cheerful True it cannot support."""

    def segment_defined(self, term: str) -> tuple:
        """`(defined, explanation)` for a named population."""

    def segment_names(self) -> list:
        """The governed segments this layer offers, for the tool schema's enum. An engine with
        none returns empty, and the `segment` argument is then not offered at all."""

    def allowed_filters(self, metric: str) -> set:
        """The dimensions a metric may be filtered by."""


# Which capabilities each guardrail reads. Named here rather than discovered by watching a run
# fail, so an incompatible pairing is caught when a study loads.
GUARDRAIL_NEEDS = {
    "coverage_check": ("coverage",),
    "resolve": ("members",),
    "output_validation": ("additivity",),
}


# Which capability each answerability TOOL needs. Tools are offered by RUNG, not by guardrail, so
# an engine lacking a capability must have the tool WITHDRAWN rather than left to raise mid-run.
# Found by running the agent on MetricFlow: it was handed `check_coverage`, called it, and the
# engine correctly refused — which is a crash where it should have been an absence.
TOOL_NEEDS = {
    "check_coverage": ("coverage",),
}


def tools_unavailable(engine_caps: Capabilities) -> set:
    """Answerability tools this engine cannot serve, and which must not be offered.

    Withdrawing the tool is the honest surface, not a workaround: a layer with no coverage window
    genuinely cannot answer "is this period covered", and an agent shown the tool anyway would be
    told a question is answerable that is not.
    """
    return {tool for tool, needed in TOOL_NEEDS.items() if engine_caps.missing(needed)}


def check_compatible(engine_caps: Capabilities, guardrails, where: str = "") -> None:
    """Refuse a study whose guardrails need something its engine does not have.

    The alternative is a guardrail silently passing because the engine returned a default, which
    would look like a clean run and would be measuring nothing.
    """
    problems = []
    for name, needed in GUARDRAIL_NEEDS.items():
        if not getattr(guardrails, name, False):
            continue
        gaps = engine_caps.missing(needed)
        if gaps:
            problems.append(f"guardrail `{name}` needs {', '.join(gaps)}, "
                            f"which the {engine_caps.name} engine does not provide")
    if problems:
        raise SystemExit(
            (f"{where}: " if where else "")
            + f"the {engine_caps.name} engine cannot support this guardrail level.\n  "
            + "\n  ".join(problems)
            + "\n\nEither lower the guardrails for this study, or run it on the harness engine.")
