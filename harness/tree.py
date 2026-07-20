"""The metric tree (rung 5): decomposition and root-cause, computed in code.

`explain_change` answers "why did X move between two periods" by walking the tree:
  1. Identity children first — exact arithmetic. A log-difference decomposition
     attributes the parent's change to each child (the shares sum to 1 because the
     parent equals the product of its children). This is not the model's judgment;
     it is arithmetic, computed here.
  2. Then the influence children of whichever identity term moved most — the soft,
     correlational drivers, returned with their evidence and confidence so the model
     narrates them hedged, never as proven cause.

The model's job at rung 5 is to read this structure back in words. It does not do
the maths and it does not invent a cause the tree doesn't carry.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "grounding" / "rung6_tree" / "metric_tree.yml"


class TreeError(Exception):
    pass


def _pct(a, b):
    return (b / a - 1.0) if (a not in (None, 0) and b is not None) else None


def _dln(a, b):
    return math.log(b / a) if (a and b and a > 0 and b > 0) else None


class MetricTree:
    def __init__(self, layer, spec_path: Path = SPEC_PATH):
        self.layer = layer
        spec = yaml.safe_load(spec_path.read_text())
        self.root: str = spec["root"]
        self.nodes: dict[str, dict] = spec["nodes"]
        self.edges: list[dict] = spec["edges"]

    def _children(self, node: str, kind: str) -> list[dict]:
        return [e for e in self.edges if e["parent"] == node and e["type"] == kind]

    def causal_evidence(self, driver: str | None = None, outcome: str | None = None) -> tuple[bool, str]:
        """Answerability check: does the tree carry an edge linking driver to outcome?
        Both a driver and an outcome are required — an omitted term is not a wildcard
        (that would trivially match every edge). A found influence edge reports its
        confidence, so a low-confidence link is not mistaken for proof."""
        if not (driver and driver.strip()) or not (outcome and outcome.strip()):
            return False, ("name both a driver and an outcome to check. Encoded edges: "
                           + "; ".join(f"{e['parent']} <- {e['child']}" for e in self.edges) + ".")

        def matches(term, node):
            t = "".join(c if c.isalnum() else "_" for c in term.lower()).strip("_")
            return t == node or node in t or t in node

        for e in self.edges:
            if matches(driver, e["child"]) and matches(outcome, e["parent"]):
                if e["type"] == "identity":
                    return True, (f"{e['parent']} = ... x {e['child']} (identity, exact arithmetic).")
                conf = e.get("confidence", "unknown")
                proven = conf in ("high",)
                lead = "weak, correlational evidence" if not proven else "evidence"
                return proven, (f"{lead} — edge {e['parent']} <- {e['child']} "
                                f"[influence, confidence: {conf}]: {e.get('evidence', '')} "
                                "An influence edge is not proof of causation; a low-confidence "
                                "edge is not a basis for a confident causal claim.")
        return False, (f"no encoded edge links {driver!r} to {outcome!r}. "
                       "Edges exist only for: "
                       + "; ".join(f"{e['parent']} <- {e['child']}" for e in self.edges) + ".")

    def describe(self) -> str:
        lines = [f"Metric tree (root: {self.root}):"]
        for node in self.nodes:
            ident = self._children(node, "identity")
            if ident:
                terms = " x ".join(c["child"] for c in ident)
                lines.append(f"- {node} = {terms}   [identity, exact]")
            for e in self._children(node, "influence"):
                lines.append(
                    f"- {node} <- {e['child']}   [influence, {e['confidence']}]: {e['evidence']}")
        return "\n".join(lines)

    def explain_change(self, node: str | None = None, period_a: str = "prev_week",
                       period_b: str = "last_week", filters: dict | None = None) -> dict:
        node = node or self.root
        if node not in self.nodes:
            raise TreeError(f"unknown node {node!r}. Nodes: {', '.join(self.nodes)}")
        # The official North Star is the internal-excluded population. Any caller
        # filter is layered ON TOP of that exclusion, never instead of it — otherwise
        # the parent (population-neutral) and children (internal-excluded) would be
        # computed over different populations and the identity shares would not sum to 1.
        filters = {"is_internal": False, **(filters or {})}

        def val(metric, period):
            return self.layer.scalar(metric, period=period, filters=filters)

        pmetric = self.nodes[node]["metric"]
        a, b = val(pmetric, period_a), val(pmetric, period_b)
        dln_parent = _dln(a, b)

        identity = []
        for e in self._children(node, "identity"):
            c = e["child"]
            ai, bi = val(self.nodes[c]["metric"], period_a), val(self.nodes[c]["metric"], period_b)
            dln_i = _dln(ai, bi)
            share = (dln_i / dln_parent) if (dln_i is not None and dln_parent) else None
            identity.append({
                "child": c, "label": self.nodes[c]["label"],
                "value_a": ai, "value_b": bi, "pct_change": _pct(ai, bi),
                "contribution_share": share,
            })

        primary = max(identity, key=lambda x: abs(x["contribution_share"] or 0), default=None)
        infl_source = primary["child"] if primary else node
        influences = []
        for e in self._children(infl_source, "influence"):
            c = e["child"]
            ai, bi = val(self.nodes[c]["metric"], period_a), val(self.nodes[c]["metric"], period_b)
            influences.append({
                "child": c, "label": self.nodes[c]["label"],
                "value_a": ai, "value_b": bi, "pct_change": _pct(ai, bi),
                "confidence": e["confidence"], "evidence": e["evidence"],
            })

        return {
            "node": node, "label": self.nodes[node]["label"],
            "period_a": period_a, "period_b": period_b,
            "value_a": a, "value_b": b, "pct_change": _pct(a, b),
            "identity_decomposition": identity,
            "primary_driver": primary,
            "influence_candidates": influences,
            "note": ("Identity shares are exact and sum to 1 (the parent is the product of its "
                     "children). Influence candidates are correlational — report them as likely "
                     "drivers with their evidence, not proven causes."),
        }
