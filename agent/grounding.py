"""What one configuration gives the agent: the prompt, the tools, and the governed layer.

Grounding is the experiment's other axis. The rung decides what the agent KNOWS — raw tables, a
star, a semantic layer, examples, a knowledge base, a metric tree — while the guardrail set
decides what it may DO about not knowing. Both are assembled here, together, because a cell is
the pair and neither half means anything alone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from semantic.engine import check_compatible
from semantic.semantic import SemanticLayer
from semantic.tree import MetricTree

from .guardrails import LADDER, GuardrailSet, incoherent
from .prompts import system_prompt
from .protocol import Protocol
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
    protocol: Protocol = field(default_factory=Protocol)

    def fingerprint(self) -> str:
        """A short, stable hash of everything the model is shown: the assembled system prompt, the
        exact tool specs (names, descriptions, enums, required fields), and the governed catalogue.

        The tool specs are as much a treatment as the prompt — a reworded description or a
        widened enum changes the agent's behaviour just as surely — yet nothing else records
        them. Two runs whose fingerprints differ are not comparable however alike their labels
        read, and a refactor that was meant to leave the model's view untouched proves it by
        leaving this unchanged.

        The catalogue belongs here for the same reason and was missing. It reaches the model as a
        `list_metrics` RESULT rather than through the prompt or a spec, so a run on a different
        semantic layer — or the same layer rendered differently — used to hash identically to its
        own control. Any experiment whose treatment IS the layer was silently unfingerprinted, and
        the guarantee above was false in exactly the case it exists to protect.

        The WAREHOUSE SCHEMA belongs here for the identical reason, and was missing for the
        identical reason: it also arrives as a tool result rather than through the prompt. A study
        comparing documented tables against undocumented ones hashed the same in both arms — the
        treatment was the schema text, and the fingerprint could not see it. Caught by the guard
        that exists to catch it, one surface later than it should have been."""
        from warehouse.warehouse import schema_text

        surface = self.system + "\n" + json.dumps(self.toolbox.specs(), sort_keys=True)
        if self.semantic is not None:
            surface += "\n" + self.semantic.list_metrics_text()
        con = getattr(self.toolbox, "con", None)
        if con is not None:
            # The arm's SCHEMA must be passed, or this reads the shared warehouse and misses the
            # treatment entirely. It did: two arms differing only in their table comments hashed
            # identically, because comments live in the arm's own schema and this asked about none.
            surface += "\n" + schema_text(con, self.rung, getattr(self.toolbox, "schema", None))
        return hashlib.sha256(surface.encode()).hexdigest()[:12]


def _build_layer(con, engine: str, spec_path):
    """The layer, from the named engine. Unknown names fail here rather than as an AttributeError
    somewhere inside a paid run."""
    if engine == "harness":
        return SemanticLayer(con, **({"spec_path": spec_path} if spec_path else {}))
    if engine == "metricflow":
        if spec_path is None:
            raise SystemExit("engine `metricflow` needs a spec_path: a DIRECTORY of MetricFlow YAML")
        from semantic.metricflow_engine import MetricFlowLayer
        return MetricFlowLayer(con, spec_path)
    raise SystemExit(f"unknown engine {engine!r}; expected 'harness' or 'metricflow'")


def build_grounding(con, rung: int, guardrails: GuardrailSet | None = None,
                    protocol: Protocol | None = None, spec_path=None,
                    engine: str = "harness", catalogue_format: str = "prose",
                    catalogue_fields: tuple = (), schema: str | None = None,
                    semantic_layer: bool | None = None) -> Grounding:
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
    # The protocol is a peer of the guardrail set, not a part of it: it says what the answer must
    # DECLARE, where the set says what the agent may DO. Both feed the same prompt, so both are
    # covered by fingerprint() without either needing to know about the other.
    p = protocol if protocol is not None else Protocol()
    system = system_prompt(rung, g, p)
    caps = capabilities(rung)
    # `spec_path` is the semantic-maturity experiment's treatment: WHICH governed layer the agent
    # is given. It defaults to the shipped one, so every existing caller keeps its behaviour.
    # WHICH ENGINE serves that layer is now a study variable too. `harness` is this project's own
    # YAML and governance model; `metricflow` is dbt MetricFlow reading a directory of its YAML.
    # The agent is unchanged either way — it calls one interface (semantic/engine.py) — which is
    # the point: a difference between engines is then a difference in what the layer SHOWS,
    # not in what the agent was built to do.
    # WHETHER there is a governed layer is normally the rung's business. An arm may say so
    # directly (`environment: {semantic: ...}`), which is what lets two arms sharing a warehouse
    # differ ONLY in the catalogue — and lets the difference be visible in the arm file rather than
    # implied by a rung number.
    wants_layer = caps.semantic if semantic_layer is None else semantic_layer
    semantic = _build_layer(con, engine, spec_path) if wants_layer else None
    if semantic is not None and catalogue_format:
        # The catalogue's FORMAT is a treatment in its own right — the one thing in the prompt that
        # varies without varying what the layer says. It reaches the fingerprint through
        # `list_metrics_text`, so two format arms hash differently, as they must.
        semantic.catalogue_format = catalogue_format
    if semantic is not None and catalogue_fields:
        # Optional facts this arm surfaces. The layer computes them either way; this
        # decides whether they reach the model.
        semantic.catalogue_fields = tuple(catalogue_fields)
    if semantic is not None:
        check_compatible(semantic.capabilities, g, f"rung {rung} / {g.label()}")
    tree = MetricTree(semantic) if caps.tree else None
    return Grounding(rung=rung, guardrails=g, protocol=p, system=system, semantic=semantic,
                     toolbox=Toolbox(con, rung, semantic, tree, guardrails=g, protocol=p,
                                     schema=schema))
