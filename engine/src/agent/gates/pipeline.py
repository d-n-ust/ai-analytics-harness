"""The gate pipeline as DATA — the composition law is this list, not a comment.

Findings §51/§53 established the ordering invariant the hard way: verifiers (which hand an answer
back) must run before construct-capable gates (which augment the final serve), or a later
hand-back destroys an earlier gate's construction; and the one SUPPLY gate — the mechanism filling
the typed value slot from the answer's own figure — must run first, because every later gate reads
the slot it fills. The invariant is enforced by test, not by prose: phases in this list must be
SUPPLY* VERIFY* CONSTRUCT*, in that order.

A gate is a function (run, exit_call) -> ToolResult | None: a ToolResult hands the answer back to
the loop (bounded by the shared correction budget); None stands down — or returns after
constructing into the exit call in place, which is what the CONSTRUCT phase is for.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import claims, contract, disclosure, measure, segments

SUPPLY, VERIFY, CONSTRUCT = "supply", "verify", "construct"


@dataclass(frozen=True)
class Gate:
    name: str
    phase: str
    fn: Callable


PIPELINE = (
    Gate("missing_value_slot",   SUPPLY,    contract.missing_value_slot),
    Gate("malformed_claims",     VERIFY,    claims.malformed_claims),
    Gate("dropped_constraint",   VERIFY,    claims.dropped_constraint),
    Gate("ungrounded_candidates", VERIFY,   claims.ungrounded_candidates),
    Gate("direction_vs_evidence", VERIFY,   contract.direction_vs_evidence),
    Gate("underived_figure",     VERIFY,    contract.underived_figure),
    Gate("segment_gate",         VERIFY,    segments.segment_gate),
    Gate("answerability_gate",   VERIFY,    measure.answerability_gate),
    Gate("substituted_measure",  VERIFY,    measure.substituted_measure),
    # Construct-capable gates LAST: undisclosed_rival can still hand back (the binding check),
    # but its constructions — like applied_segment's and substituted_window's — must attach to
    # the final serve and never be discarded by a later hand-back.
    Gate("undisclosed_rival",    CONSTRUCT, disclosure.undisclosed_rival),
    Gate("applied_segment",      CONSTRUCT, segments.applied_segment),
    Gate("substituted_window",   CONSTRUCT, contract.substituted_window),
)


def run_gates(run, exit_call):
    """Fold the exit call through the pipeline: the first hand-back wins; constructions apply in
    place and the fold continues. Returns the correction to send back, or None to serve."""
    for gate in PIPELINE:
        result = gate.fn(run, exit_call)
        if result is not None:
            return result
    return None
