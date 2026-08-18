"""Value types for preflight — immutable, hashable, and free of behaviour.

Everything the detector passes around is a frozen dataclass or a plain string. Immutability is a
deliberate design choice: the transforms in scope.py / adapters.py / detect.py are pure functions
over these values, which is what makes them trivially testable, debuggable, and safe to run in
parallel (no shared mutable state to guard).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The finite vocabularies, as static types. Kept as plain strings at runtime (not enums) so results
# serialise to JSON and compare to string literals with no surprises, while still being checkable.
Danger = Literal["high", "medium", "low"]
CollisionType = Literal[
    "DUPLICATE", "SCOPE_TRAP", "SIBLING", "CONCEPT_FORK",
    "DEFINITION_DIVERGENCE", "NAME_COLLISION", "GRAIN_MISMATCH",
]
Layer = str            # semantic | warehouse | docs | queries
Additivity = Literal["additive", "semi", "non"]

# A parsed WHERE leaf: (column, kind, payload). kind ∈ {"set","cmp","raw"}; payload is a frozenset of
# values for "set", or a normalised SQL string for "cmp"/"raw". A Scope is a sorted tuple of these.
# Kept a typed tuple (not a dataclass) because the value is a tested contract — tests assert on the
# literal `(("col","set",frozenset({...})),)` shape — and the union already restores type-checking.
Predicate = tuple[str, str, frozenset[str] | str]
Scope = tuple[Predicate, ...]

DANGER_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Recovered:
    """Which meaning facets sqlglot could recover from a raw query (T3 diagnostics only)."""

    agg: bool = False
    base: bool = False
    scope: bool = False
    entity: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {"agg": self.agg, "base": self.base, "scope": self.scope, "entity": self.entity}


@dataclass(frozen=True)
class Source:
    """Where a grounding fact was found, so a finding can be cited back as `path:line` and the
    offending line shown to the reader. No column offset is stored: the highlighter locates the term
    within the line by the fact's own label, which survives reformatting that an offset would not."""

    path: str
    line: int

    def to_dict(self) -> dict:
        return {"path": self.path, "line": self.line}


@dataclass(frozen=True)
class GroundingFact:
    """One thing an agent could read to ground a query on, normalised across artifact types.

    A semantic-layer metric, a warehouse column/view, a documented term, or a welded query all
    reduce to this one shape, so the detector runs over the whole surface at once — including
    collisions that cross layers.
    """

    id: str                        # unique, layer-prefixed: "sl:net_revenue", "wh:fct_orders.revenue"
    label: str                     # the bare term a reader sees / would say: "net_revenue", "revenue"
    layer: str                     # semantic | warehouse | docs | queries
    kind: str                      # metric | dimension | segment | column | table | view | term | query
    entity: str | None = None      # what is counted (meaning)
    agg: str | None = None         # aggregation (meaning)
    base: str | None = None        # source table (meaning)
    measure: str | None = None     # measured column/expr (meaning)
    grain: str | None = None       # group-by level (day/week/month)
    additive: str | None = None    # additive | semi | non — derived from agg, never per-metric
    scope: Scope = ()              # parsed predicates, segment-resolved
    text: str = ""                 # source text for the confusability gate + human review
    derived: bool = False          # a ratio/derived metric that references other metrics, not rows
    recovered: Recovered | None = None
    source: Source | None = None   # file + line it was defined at, for citing findings back

    @property
    def meaning(self) -> dict[str, str | None]:
        return {"entity": self.entity, "agg": self.agg, "base": self.base, "measure": self.measure}


@dataclass(frozen=True)
class Classification:
    """A per-pair verdict from classify(): what kind of collision, and how dangerous."""

    type: CollisionType
    danger: Danger
    note: str


@dataclass(frozen=True)
class Item:
    """One grounding fact as it appears inside a Finding."""

    id: str
    label: str
    layer: str
    source: Source | None = None   # carried from the fact, so a Finding can be cited to path:line

    def to_dict(self) -> dict:
        d: dict = {"id": self.id, "label": self.label, "layer": self.layer}
        if self.source is not None:
            d["source"] = self.source.to_dict()
        return d


@dataclass(frozen=True)
class Finding:
    """A clustered collision: one concept, the facts that collide on it, and the danger call."""

    type: CollisionType
    danger: Danger
    note: str
    items: tuple[Item, ...]

    def to_dict(self) -> dict:
        return {"type": self.type, "danger": self.danger, "note": self.note,
                "items": [it.to_dict() for it in self.items]}


@dataclass(frozen=True)
class DetectConfig:
    """Detector thresholds, made explicit and injectable rather than hidden as module globals.

    Passing this in (rather than reading globals) is what lets a test pin behaviour and a caller
    tune sensitivity without editing the package."""

    gate: float = 0.55                 # min label similarity to examine a non-identical pair
    warehouse_synonym: float = 0.82    # min similarity for a warehouse near-synonym column pair
    name_collision: float = 0.82       # min similarity for a plain read-alike NAME_COLLISION
    definition_overlap: float = 0.6    # max doc-prose Jaccard before two definitions "diverge"
    min_shared_facets: int = 2         # meaning facets that must agree to call it the same measure
    overloaded_tables: int = 4         # a non-key column in >= this many tables is "overloaded" (keys excluded)


DEFAULT_CONFIG = DetectConfig()
