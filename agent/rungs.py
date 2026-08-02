"""What each grounding rung gives the agent.

A rung number used to carry two meanings at once: a POSITION on the ladder, and the SET OF
CAPABILITIES at that position. They agree exactly as long as every rung is a superset of the one
below, which is why the code could ask `rung >= 6` and mean "has the metric tree".

Rung 7 breaks the agreement on purpose. It is the governed-only configuration — semantic layer
and metric tree, without the verified examples and knowledge base that sit between rungs 3 and 6
— so it holds LESS than rung 6 while sorting after it. That distinction is the point of the
configuration: the semantic layer and the tree are governed structures that compile to SQL and
are correct by construction, while examples and the knowledge base are advisory prose that helps
the model choose but cannot be checked. Rung 7 is everything governed and nothing advisory.

With the two meanings separated, capabilities are DECLARED here and asked, never computed from
the number. Three files previously each held their own copy of "rung 6 means tree" (grounding,
prompts, action_space) and two held identical copies of the names; a new configuration had to be
special-cased into every one of them or silently disagree with the others.

Nothing may infer a capability by comparing rung numbers. The ladder is no longer monotonic, so
`rung >= n` is not a statement about what the agent has.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["RUNGS", "RUNG_NAMES", "Rung", "capabilities", "parse_rung"]


@dataclass(frozen=True)
class Rung:
    """One grounding configuration, described by what the agent gets rather than by its number.

    Two kinds of grounding, and the split is the experiment's most useful distinction:
    GOVERNED (`semantic`, `tree`) is checkable — it compiles to SQL and is correct by
    construction. ADVISORY (`examples`, `knowledge`) is prose that informs a choice and can
    neither be verified nor kept from rotting.
    """

    name: str
    star: bool = False        # the cleaned star schema (dim_*/fct_*) rather than raw tables
    semantic: bool = False    # governed catalog — list_metrics, query_metric
    examples: bool = False    # verified worked examples, in the prompt
    knowledge: bool = False   # the knowledge base, in the prompt
    tree: bool = False        # metric tree — get_metric_tree, decompose_change

    def governed(self) -> bool:
        return self.semantic or self.tree

    def advisory(self) -> bool:
        return self.examples or self.knowledge


RUNGS: dict[float, Rung] = {
    1: Rung("messy data"),
    2: Rung("star schema", star=True),
    3: Rung("semantic layer", star=True, semantic=True),
    4: Rung("+ verified examples", star=True, semantic=True, examples=True),
    5: Rung("+ knowledge base", star=True, semantic=True, examples=True, knowledge=True),
    6: Rung("+ metric tree", star=True, semantic=True, examples=True, knowledge=True, tree=True),
    # Named for what it holds, not where it sorts: every chart that prints a rung number prints
    # this too, so "7" cannot be read as "more than 6" without the correction alongside it.
    7: Rung("governed only — semantic layer + metric tree", star=True, semantic=True, tree=True),
}

RUNG_NAMES: dict[float, str] = {n: r.name for n, r in RUNGS.items()}


def capabilities(rung) -> Rung:
    """What this rung gives the agent. Raises on an unknown rung rather than defaulting to a
    quiet nothing — a typo'd rung that silently grounds the agent at rung 1 produces rows that
    are indistinguishable from real ones once written."""
    caps = RUNGS.get(rung)
    if caps is None:
        raise ValueError(f"unknown rung {rung!r}; defined: {sorted(RUNGS)}")
    return caps


def parse_rung(text: str) -> float:
    """A rung from the command line. Accepts '3' and '3.5' alike and returns the key as stored,
    so `--rung 7` and `--rungs 3,7` agree with RUNGS without the caller knowing the key type."""
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"rung {text!r} is not a number; defined: {sorted(RUNGS)}") from None
    value = int(value) if value.is_integer() else value
    capabilities(value)
    return value


def describe(rung) -> str:
    """One line naming the rung and every capability it carries — for a trace or a run header,
    where 'rung 7' alone is not enough to know what was measured."""
    caps = capabilities(rung)
    on = [f.name for f in fields(caps) if f.name != "name" and getattr(caps, f.name)]
    return f"rung {rung} ({caps.name}): {', '.join(on) if on else 'raw tables only'}"
