"""The evidence layer: what an answer committed to, and whether each commitment holds.

The third axis of the harness. `agent/rungs.py` varies what the agent KNOWS; `agent/guardrails/`
varies what it MAY DO; this reads what it DECLARED and resolves every declaration against the
trace it was built from. See docs/ARCHITECTURE.md for why that is a third thing rather than a
guardrail, and docs/TRUST-MODEL.md for what it is eventually meant to compute.

**This package decides nothing.** `audit()` returns findings and never refuses; nothing here
returns a Verdict, blocks a call, or downgrades an answer. That is a structural property, not a
current limitation:

  - it is what separates an instrument from a judge, and the moment a check here could refuse,
    the number it produces would stop being a measurement of the agent and start being a
    measurement of itself;
  - it is what makes the numbers publishable — a component that renders no verdict can be handed
    to a reader who does not trust us;
  - it is why every metric here needs no gold. Coverage and silent-error rate exist only because
    we wrote the answers too; `bound`, `unresolved` and `derived` are lookups against the
    certified model, so they compute on a client's question where no answer key will ever exist.

Guardrails may consult this package. It must never import from `agent/` — that direction is the
whole point, and `agent/guardrails/after.py` holds the one crossing, in the permitted direction.
"""

from __future__ import annotations

from .claims import (
    BAD_PREMISE,
    CORRELATIONAL,
    EXACT,
    MISLABELLED,
    MIXED_SUPPORT,
    UNRESOLVED,
    UNSOURCED,
    VALUE_MISMATCH,
    audit,
    cited_metric,
    claim_id,
)
from .chain import Chain, Link, Node, chain_of, premise_id
from .render import measurement_text
from .values import num_match

__all__ = ["BAD_PREMISE", "CORRELATIONAL", "EXACT", "MISLABELLED", "MIXED_SUPPORT", "UNRESOLVED", "UNSOURCED",
           "VALUE_MISMATCH", "Chain", "Link", "Node", "audit", "chain_of", "cited_metric",
           "claim_id", "measurement_text", "num_match", "premise_id"]
