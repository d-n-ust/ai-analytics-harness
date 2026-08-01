"""Which governed names can be mistaken for each other — a lint for the semantic layer itself.

Run before an agent ever sees the layer. It reads the declarations, not the traffic, so it says
which confusions are POSSIBLE rather than which have happened, and it needs no model, no
questions, and no run.

WHY THIS AND NOT AN EMBEDDING

The obvious version compares question text to metric names by embedding distance. That answers
"which metric is closest to what was asked", which is a *retrieval* question, and it answers it
with a model — trading a governed decision for an inferred one, in the one place this harness
refuses to.

The question worth asking is different and harder: **which pairs of governed names would a
competent reader confuse, and would anything downstream notice if they were swapped?** That is a
property of the layer, and the layer already declares everything needed to compute it.

THE DANGEROUS QUADRANT

Two names are safe when they are far apart in name, or identical in meaning. The trap is the
diagonal: near in name, different in scope.

    value_moments        entity value_moments · agg sum(moments) · base agg_active_days
                         segment all
    real_value_moments   entity value_moments · agg sum(moments) · base agg_active_days
                         segment active · default_filters [NOT is_internal]

Identical in six declared facets; different in two, and both of those are SCOPE. So the two
figures are near neighbours — 12.12% against 11.88% on the same week — and every numeric check
passes a swap between them. The provenance check passes. The output validation passes. The judge
sees a real number computed by a real metric. This is the harness's single largest source of
mislabelled claims: 59% of every mislabel ever recorded is this one pair.

That is the finding this module exists to surface BEFORE a run, from the YAML alone.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Ambiguity", "confusable_pairs", "report"]

# The facets a metric declares about what it MEASURES. Two metrics agreeing on all of these
# measure the same thing; the rest of the declaration is scope, presentation, or plumbing.
_MEANING = ("entity", "agg", "base", "unit")
# The facets that narrow it. A difference here changes WHICH ROWS, never what is counted — which
# is exactly why the two numbers land close together and no value check separates them.
_SCOPE = ("segment", "default_filters", "time_column")


@dataclass(frozen=True)
class Ambiguity:
    """One pair of governed names that could be mistaken for each other."""

    a: str
    b: str
    shared_tokens: tuple[str, ...]
    same_meaning: tuple[str, ...]      # facets where they agree about what is measured
    differs_in: tuple[str, ...]        # facets where they disagree
    kind: str                          # scope_only | different_measure | alias
    note: str = ""

    @property
    def severity(self) -> str:
        """`scope_only` is the dangerous one and it is not a matter of degree.

        A pair that differs in what it MEASURES produces numbers that are far apart, so a swap is
        loud — a range check, a magnitude, a reader's eyebrow. A pair that differs only in scope
        produces neighbours, and nothing downstream can tell them apart. That is a categorical
        difference in detectability, not a score."""
        return {"scope_only": "high", "alias": "medium"}.get(self.kind, "low")


# Words that qualify a measure rather than name one. Two names sharing only these are not
# confusable — `days_per_user` and `moments_per_day` both contain "per" and nobody has ever mixed
# them up. Without this the lint reported eleven pairs of which nine were noise, and a lint whose
# output must be skimmed for the real entry is a lint nobody runs twice.
_QUALIFIERS = frozenset({"per", "rate", "avg", "average", "total", "count", "of", "and", "the",
                         "weekly", "daily", "monthly", "new", "open"})


def _tokens(name: str) -> set[str]:
    return {t for t in str(name).replace("-", "_").split("_") if t}


def _overlap(a: str, b: str) -> set[str]:
    """The name tokens two names share, ignoring pure qualifiers.

    Deliberately not a similarity score: the useful signal is WHICH words are shared, because that
    is what a reader would report back and what a rename has to change. Empty when the only thing
    in common is a qualifier."""
    return (_tokens(a) & _tokens(b)) - _QUALIFIERS


def _classify(da: dict, db: dict) -> tuple[str, tuple, tuple, str]:
    """How two declarations differ, and how badly a swap between them would hide."""
    same = tuple(f for f in _MEANING if da.get(f) == db.get(f) and da.get(f) is not None)
    differs = tuple(f for f in (*_MEANING, *_SCOPE) if da.get(f) != db.get(f))
    if not differs:
        return "alias", same, differs, "identical declarations under two names"
    if len(same) == len(_MEANING) and set(differs) <= set(_SCOPE):
        return ("scope_only", same, differs,
                "measures the same thing at a different scope, so the two figures are near "
                "neighbours and no numeric check separates them")
    return "different_measure", same, differs, "differs in what it measures, not only in scope"


def confusable_pairs(metrics: dict, tree_nodes: dict | None = None) -> list[Ambiguity]:
    """Every pair of governed names sharing a meaningful name token, classified by what differs.

    `metrics` is the layer's catalog (name -> declaration). `tree_nodes` maps a tree node to the
    metric beneath it — a node is a third public name for a measure, and one of them is the
    `weekly_value_moments` in this repo's own worst case.
    """
    out: list[Ambiguity] = []
    names = sorted(metrics)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = _overlap(a, b)
            if not shared:
                continue
            kind, same, differs, note = _classify(metrics[a] or {}, metrics[b] or {})
            out.append(Ambiguity(a, b, tuple(sorted(shared)), same, differs, kind, note))

    # A tree node is a public name too, and it is classified the same way — by comparing the
    # declaration BEHIND it against the metric it collides with. Flagging every token overlap
    # instead reported nine pairs nobody could confuse and buried the one that matters: the node
    # `weekly_value_moments` resolves to `real_value_moments` while reading like `value_moments`,
    # so three surface names cover two measures and the two measures differ only in scope.
    for node, metric in (tree_nodes or {}).items():
        for name in names:
            shared = _overlap(node, name)
            if name == metric or not shared or metric not in metrics:
                continue
            kind, same, differs, note = _classify(metrics[metric] or {}, metrics[name] or {})
            out.append(Ambiguity(
                a=f"{node} (tree node -> {metric})", b=name, shared_tokens=tuple(sorted(shared)),
                same_meaning=same, differs_in=differs, kind=kind,
                note=f"the node reads like {name!r} and resolves to {metric!r}; those two " + note))

    return sorted(out, key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x.severity], x.a, x.b))


def report(metrics: dict, tree_nodes: dict | None = None) -> str:
    found = confusable_pairs(metrics, tree_nodes)
    high = [f for f in found if f.severity == "high"]
    lines = [f"{len(found)} confusable name pair(s) in the governed layer; "
             f"{len(high)} where no numeric check could catch a swap", ""]
    for f in found:
        lines.append(f"  [{f.severity:6}] {f.a}  ~  {f.b}")
        lines.append(f"             shares the name token(s): {', '.join(f.shared_tokens)}")
        if f.same_meaning:
            lines.append(f"             agrees on: {', '.join(f.same_meaning)}")
        lines.append(f"             differs in: {', '.join(f.differs_in)}")
        lines.append(f"             {f.note}")
        lines.append("")
    if high:
        lines.append("A `high` pair is a rename, not a warning to live with: give the two names "
                     "different head nouns, or fold one into the other as a governed segment of "
                     "it, so the vocabulary cannot express the confusion.")
    return "\n".join(lines)
