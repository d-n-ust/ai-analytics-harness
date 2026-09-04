"""The semantic layer: governed metric definitions, the metric tree, and the compiler that turns a
metric selection into correct SQL.

This is the package's public API. Depend on these names, not on the internal module layout — so the
internals can be reorganised (or the package extracted) without touching callers. `MetricFlowLayer`
is deliberately absent: it pulls the optional MetricFlow dependency, so it stays a lazy import at its
one call site.
"""

from .clusters import Clusters, Competitor, StaleIndex
from .clusters import load as load_clusters
from .engine import check_compatible, tools_unavailable
from .semantic import SemanticError, SemanticLayer
from .tree import Causality, MetricTree, TreeError

__all__ = [
    "SemanticLayer", "SemanticError",
    "Clusters", "Competitor", "StaleIndex", "load_clusters",
    "MetricTree", "Causality", "TreeError",
    "check_compatible", "tools_unavailable",
]
