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
from enum import StrEnum
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent / "metric_tree.yml"


class TreeError(Exception):
    pass


def _pct(a, b):
    return (b / a - 1.0) if (a not in (None, 0) and b is not None) else None


def _dln(a, b):
    return math.log(b / a) if (a and b and a > 0 and b > 0) else None


class Causality(StrEnum):
    """What the tree can say about a driver and an outcome. FOUR states, because a boolean
    conflated the two that must never be conflated.

      PROVEN         identity arithmetic, or a high-confidence influence
      CORRELATIONAL  an edge exists and is weak — here it is, with its confidence
      NOT_ENCODED    both terms ARE modelled, and no edge joins them. A finding: someone drew
                     this graph and did not draw that arrow
      UNKNOWN        a term is outside the model entirely. An admission, carrying no evidence in
                     either direction

    The last two were one value, and they are not the same claim. "We modelled this and found no
    link" is weak evidence of no link; "we have never heard of this thing" is none. Collapsed,
    `causal_evidence('pricing_change', ...)` answered NO for an event the layer does not model at
    all, and 5 of 40 answers to u_pricing_cause said "No — the pricing change did not cause it",
    which is absence of evidence restated as evidence of absence. The repo already fixed exactly
    that for a missing TREE (agent/tools.py) and never generalised it to a missing TERM.
    """

    PROVEN = "proven"
    CORRELATIONAL = "correlational"
    NOT_ENCODED = "not_encoded"
    UNKNOWN = "unknown"


class MetricTree:
    def __init__(self, layer, spec_path: Path = SPEC_PATH):
        self.layer = layer
        spec = yaml.safe_load(spec_path.read_text())
        self.root: str = spec["root"]
        self.nodes: dict[str, dict] = spec["nodes"]
        self.edges: list[dict] = spec["edges"]

    def _children(self, node: str, kind: str) -> list[dict]:
        return [e for e in self.edges if e["parent"] == node and e["type"] == kind]

    @staticmethod
    def _matches(term: str, node: str) -> bool:
        t = "".join(c if c.isalnum() else "_" for c in term.lower()).strip("_")
        return t == node or node in t or t in node

    def _edge_text(self, e: dict) -> str:
        if e["type"] == "identity":
            return f"{e['parent']} <- {e['child']} [identity, exact arithmetic]"
        return (f"{e['parent']} <- {e['child']} [influence, confidence: "
                f"{e.get('confidence', 'unknown')}]: {e.get('evidence', '')}")

    def _path(self, outcome: str, driver: str) -> list[dict] | None:
        """The shortest edge chain from an outcome down to a driver, or None.

        Breadth-first, so the chain returned is the most direct one the tree carries. Edges point
        parent <- child, and a driver is always further from the root than the outcome it acts on,
        so the walk only ever goes downward and cannot loop back through a node it has left."""
        queue: list[tuple[str, list[dict]]] = [(n, []) for n in self.nodes if self._matches(outcome, n)]
        seen = {n for n, _ in queue}
        while queue:
            node, path = queue.pop(0)
            for e in (x for x in self.edges if x["parent"] == node):
                chain = [*path, e]
                if self._matches(driver, e["child"]):
                    return chain
                if e["child"] not in seen:
                    seen.add(e["child"])
                    queue.append((e["child"], chain))
        return None

    def _known(self, term: str) -> bool:
        """Is this term something the model has a node for at all? The whole test that separates a
        finding from an admission, and it was never asked."""
        return any(self._matches(term, node) for node in self.nodes)

    def causal_evidence(self, driver: str | None = None,
                        outcome: str | None = None) -> tuple[Causality, str]:
        """Answerability check: does the tree link driver to outcome, directly or through a chain?

        Both terms are required — an omitted one is not a wildcard, which would trivially match
        every edge. A found influence edge reports its confidence, so a low-confidence link is not
        mistaken for proof.

        An INDIRECT link is reported as one, rather than as nothing. Asked whether reminders caused
        the North Star to fall, this used to answer "no encoded edge" — true of a direct edge, and
        badly misleading: reminder_open_rate influences days_per_user, which is an identity child
        of the root. A model reading that flat NO refused a question the tree could speak to, and
        did so on two different backbones. The verdict is unchanged (a chain through a low-
        confidence influence edge is still not proof); only the explanation stops hiding the path.

        A chain is exactly as strong as its weakest edge, which is the rule the claim layer uses
        too: identity composes with identity and stays exact, and one correlational edge anywhere
        makes the whole chain correlational.
        """
        if not (driver and driver.strip()) or not (outcome and outcome.strip()):
            return Causality.UNKNOWN, ("name both a driver and an outcome to check. Encoded edges: "
                                       + "; ".join(f"{e['parent']} <- {e['child']}"
                                                   for e in self.edges) + ".")

        # A term the model has no node for. Naming WHICH term is the point: it tells an analyst
        # what the layer would need in order to answer, where "no encoded edge" tells them nothing
        # and invites them to conclude there is no effect.
        missing = [t for t in (driver, outcome) if not self._known(t)]
        if missing:
            return Causality.UNKNOWN, (
                f"{', '.join(repr(m) for m in missing)} is not a modelled entity — the tree has no "
                f"node for it, so there is nothing here that could show a link either way. This is "
                f"NOT evidence that no link exists; it means the layer cannot speak to it. Do not "
                f"answer the causal question in the negative on the strength of this. Modelled "
                f"nodes: {', '.join(self.nodes)}.")

        for e in self.edges:
            if self._matches(driver, e["child"]) and self._matches(outcome, e["parent"]):
                if e["type"] == "identity":
                    return Causality.PROVEN, (f"{e['parent']} = ... x {e['child']} "
                                              "(identity, exact arithmetic).")
                conf = e.get("confidence", "unknown")
                proven = conf in ("high",)
                lead = "weak, correlational evidence" if not proven else "evidence"
                return (Causality.PROVEN if proven else Causality.CORRELATIONAL), (
                    f"{lead} — edge {e['parent']} <- {e['child']} "
                                f"[influence, confidence: {conf}]: {e.get('evidence', '')} "
                                "An influence edge is not proof of causation; a low-confidence "
                                "edge is not a basis for a confident causal claim.")

        chain = self._path(outcome, driver)
        if chain:
            proven = all(e["type"] == "identity" or e.get("confidence") == "high" for e in chain)
            weakest = "exact arithmetic throughout" if proven else (
                "the weakest link is a correlational influence edge, so the chain is not proof of "
                "causation and cannot support a confident causal claim")
            return (Causality.PROVEN if proven else Causality.CORRELATIONAL), (
                f"no DIRECT edge links {driver!r} to {outcome!r}, but the tree carries a path: "
                + " ; ".join(self._edge_text(e) for e in chain)
                + f". A chain is only as strong as its weakest edge — {weakest}. The intermediate "
                  f"node ({chain[-1]['parent']}) is where to check whether anything actually moved.")

        # Both terms ARE modelled and nothing joins them. A finding, not an admission.
        return Causality.NOT_ENCODED, (
            f"both {driver!r} and {outcome!r} are modelled, and no encoded edge links them, "
            "directly or through any chain. Edges exist only for: "
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
        # No population is forced here. Each node's metric carries its own, and the identity
        # closes because the DEFINITIONS agree — real_value_moments and its three children all
        # exclude internal/test — not because this function remembers to filter.
        #
        # Forcing it here broke the invariant that matters more: a tree node reports the metric
        # it names. The root named value_moments (every account, 4,307) and reported 4,133, so
        # "why did value moments drop?" and "how many value moments?" answered with different
        # numbers for the same word. A filter applied here is a metric definition living in a
        # second place, and the second place always wins silently.
        filters = filters or {}

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

        # The largest contribution IN THE DIRECTION THE PARENT MOVED. Signed, not absolute.
        #
        # `max(..., key=abs)` discarded the sign, so a child that pushed AGAINST the change could
        # be named its primary driver. Shares are normalised by the parent's log change and sum to
        # 1, so at least one is always positive and the signed max is always well defined — the
        # absolute value handled a case that cannot arise while creating one that can.
        movers = [c for c in identity if c["contribution_share"] is not None]
        primary = max(movers, key=lambda x: x["contribution_share"], default=None)
        # The other direction, named rather than left for a reader to infer from a minus sign.
        # "Active users rose 5.98% and contributed -0.46" is the fact a whole class of question
        # turns on — growth masked by a decline elsewhere — and nothing in the payload said it.
        offsetting = [c for c in movers if (c["contribution_share"] or 0) < 0]

        # Influences for EVERY identity child, keyed by the child they belong to.
        #
        # This returned the influences of the primary driver alone, under the name
        # `influence_candidates`, with nothing saying a branch had been dropped. So a question
        # like "is this a product problem or an acquisition problem" was unanswerable from the
        # tool that exists to answer it: acquisition feeds active_users, active_users was not the
        # top contributor, and its two influence edges were therefore structurally invisible. The
        # agent read a field named "candidates" holding one entry and reasonably stopped.
        #
        # Keyed by child rather than flattened because WHICH child an influence hangs off is the
        # information such a question needs. A flat list was unambiguous only while it could never
        # hold more than one branch.
        influences: dict[str, list] = {}
        for parent in [node, *(c["child"] for c in identity)]:
            found = []
            for e in self._children(parent, "influence"):
                c = e["child"]
                ai, bi = val(self.nodes[c]["metric"], period_a), val(self.nodes[c]["metric"], period_b)
                found.append({
                    "child": c, "label": self.nodes[c]["label"],
                    "value_a": ai, "value_b": bi, "pct_change": _pct(ai, bi),
                    "confidence": e["confidence"], "evidence": e["evidence"],
                })
            if found:
                influences[parent] = found

        return {
            "node": node, "label": self.nodes[node]["label"],
            "period_a": period_a, "period_b": period_b,
            "value_a": a, "value_b": b, "pct_change": _pct(a, b),
            "identity_decomposition": identity,
            "primary_driver": primary,
            "offsetting": offsetting,
            "influences": influences,
            # What this call did NOT open. A tool that can prune has to say what it pruned, and an
            # EMPTY list is the useful case: it states positively that nothing is hidden, which is
            # exactly what an agent needs before concluding it has the whole picture.
            "not_expanded": self._unexpanded(node, identity, influences),
            "note": ("Identity shares are exact, signed, and sum to 1 (the parent is the product "
                     "of its children); a negative share means that child pushed the parent the "
                     "OTHER way and is listed under `offsetting`. Influence children are "
                     "correlational — report them as likely drivers with their evidence, never as "
                     "proven causes. `influences` is keyed by the child each one hangs off, and "
                     "`not_expanded` names any node with further structure this call did not "
                     "open; when it is empty, nothing was left out."),
        }

    def _unexpanded(self, node: str, identity: list, influences: dict) -> list[str]:
        """Nodes reachable from what this call returned that have structure of their own and were
        not opened. Computed from the edges rather than hand-listed, so a tree that grows a level
        starts reporting it without anyone remembering to."""
        opened = {node, *(c["child"] for c in identity), *influences}
        reached = {c["child"] for c in identity}
        reached |= {i["child"] for group in influences.values() for i in group}
        return sorted(n for n in reached - opened
                      if self._children(n, "identity") or self._children(n, "influence"))
