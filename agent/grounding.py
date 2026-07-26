"""What one configuration gives the agent: the prompt, the tools, and the governed layer.

Grounding is the experiment's other axis. The rung decides what the agent KNOWS — raw tables, a
star, a semantic layer, examples, a knowledge base, a metric tree — while the guardrail set
decides what it may DO about not knowing. Both are assembled here, together, because a cell is
the pair and neither half means anything alone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from semantic.semantic import SemanticLayer
from semantic.tree import MetricTree

from .guardrails import LADDER, GuardrailSet, incoherent
from .prompts import system_prompt
from .rungs import RUNG_NAMES, capabilities  # noqa: F401 — RUNG_NAMES re-exported for reports
from .tools import Toolbox

@dataclass
class Grounding:
    """Everything one configuration gives the agent: what it is told, what it may do, and the
    governed layer both are defined against."""

    rung: int
    system: str
    toolbox: Toolbox
    guardrails: GuardrailSet | None = None
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
                    guardrails: GuardrailSet | None = None) -> Grounding:
    # GuardrailSet is the one primitive; default R1 (abstention). A ladder preset is LADDER[n], an
    # ablation cell any GuardrailSet set. The prompt is assembled from the SAME set the Toolbox
    # enforces, so a cell can never describe a guardrail that is not running — that would make the
    # measurement vary with the treatment, the one thing an ablation must not do.
    g = guardrails if guardrails is not None else LADDER[1]
    # Fail here rather than build a system that cannot do what its label says. An incoherent
    # (rung, guardrails) pair still produces rows, and those rows are indistinguishable from
    # real ones once written — the measurement would vary with the treatment, which is the one
    # thing an ablation must not do.
    bad = incoherent(g, rung)
    if bad:
        raise ValueError(f"incoherent grounding: rung {rung} with {g.label()} — {bad}")
    system = system_prompt(rung, g)
    caps = capabilities(rung)
    semantic = SemanticLayer(con) if caps.semantic else None
    tree = MetricTree(semantic) if caps.tree else None
    return Grounding(rung=rung, guardrails=g, system=system, semantic=semantic,
                     toolbox=Toolbox(con, rung, semantic, tree, guardrails=g))
