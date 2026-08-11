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

import re
from dataclasses import dataclass

__all__ = ["Ambiguity", "MemberClash", "confusable_pairs", "considers",
           "member_clashes", "report"]

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


def considers(a: str, b: str) -> bool:
    """Whether this lint would COMPARE two metric names at all.

    Public because the coverage audit's whole question is "what does the detector never look at",
    and answering it from a second, similar-looking rule is how the two come to disagree. The gate
    is name tokens only: synonyms and descriptions are not consulted, so two metrics can share
    plenty of words and still never be compared here."""
    return bool(_overlap(a, b))


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


# ─────────────────────────────────────────────────────────────────────────────────
# Dimension MEMBERS. The lint above checks metric names; this checks the values a
# caller may name, which is where the sharper collisions live.
# ─────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MemberClash:
    """One addressable member string, and why it is not safe to reach from free text.

    SCOPE, because getting this wrong is what the first version of this lint did: only
    `collision` is a defect on its own terms. `code_as_text` and `common_in_prose` are findings
    ABOUT FREE-TEXT RESOLUTION — they matter to a system that maps a user's words onto a member,
    and say nothing about a caller that supplies a member deliberately.

    Measured on this layer: the model passed `region='apac'` 211 times, `platform='ios'` 41 times
    and `plan='annual'` 42 times, every one of them flagged here and every one of them CORRECT.
    Reporting those as defects counts the alias map working as evidence it is broken."""

    text: str
    kind: str                          # collision | code_as_text | common_in_prose
    claimed_by: tuple[str, ...]        # "dimension.member" for each claimant
    note: str = ""
    seen_in: int = 0                   # occurrences in a supplied corpus, when given

    @property
    def severity(self) -> str:
        """`collision` is a defect however the value arrives. The other two are conditional, so
        they are labelled as advice rather than ranked as faults."""
        return "high" if self.kind == "collision" else "if-you-resolve-prose"


def _member_aliases(dimension: dict) -> dict:
    """{addressable string -> canonical member}, for one dimension.

    Members come in two shapes in this layer — a bare synonym list, or a dict carrying synonyms
    plus metadata — and BOTH are read, because the point is to find every string a caller could
    send. The canonical value is addressable too: `resolve_member` matches it, so it is part of
    the surface whether or not anyone meant it to be.
    """
    out = {}
    for canonical, member in (dimension or {}).items():
        synonyms = member.get("synonyms", []) if isinstance(member, dict) else (member or [])
        for text in [canonical, *synonyms]:
            out.setdefault(str(text).strip().lower(), str(canonical))
    return out


def member_clashes(dimensions: dict, corpus: list[str] | None = None) -> list[MemberClash]:
    """Addressable member strings that will resolve to the wrong thing, or to a thing nobody meant.

    ONLY THE FIRST IS A DEFECT ON ITS OWN. The other two are conditional on free-text resolution,
    and are returned as advice — see MemberClash.severity. Three rules, each with a reason rather
    than a taste:

    COLLISION — one string claimed by two members. `google` is an alias of platform=android and
    lives inside `google ads`, an alias of channel=paid_search, so which dimension wins depends on
    how many words the caller happens to send. Cube would reject two segments sharing a name;
    LookML would reject two dimensions sharing a label. Here it is resolved by iteration order.

    CODE AS TEXT — an alias of one or two characters is an identity code, not language. `resolve_
    member` lowercases before comparing, so ISO country codes become addressable as English:
    IN, US, ID, DE, BR, FR, GB, PH. A code should match as identity — exact and case-sensitive —
    and never as a word.

    COMMON IN PROSE — measured against a corpus when one is supplied, rather than judged. An alias
    that appears often in ordinary questions is dangerous regardless of how reasonable it looks in
    the YAML: `paid` reads fine next to paid_search and fires on "trial-to-paid". For a client the
    corpus is their query log; here it is the question set.
    """
    addressable: dict = {}
    for dim, members in (dimensions or {}).items():
        for text, canonical in _member_aliases(members).items():
            addressable.setdefault(text, []).append(f"{dim}.{canonical}")

    words: dict = {}
    for line in corpus or []:
        for w in re.findall(r"[a-z][a-z']*", str(line).lower()):
            words[w] = words.get(w, 0) + 1

    out: list[MemberClash] = []
    for text, claimants in addressable.items():
        if len(claimants) > 1:
            out.append(MemberClash(text, "collision", tuple(sorted(claimants)),
                                   "one string, two members — the winner depends on how the "
                                   "caller happens to phrase it"))
        elif len(text) <= 2:
            out.append(MemberClash(text, "code_as_text", tuple(claimants),
                                   "an identity code, matched case-insensitively against free "
                                   "text; it should match as identity, not as a word"))
        elif corpus and words.get(text, 0) >= 2:
            out.append(MemberClash(text, "common_in_prose", tuple(claimants),
                                   "appears in ordinary questions, so any text reaching the "
                                   "resolver will match it", seen_in=words[text]))
    # defects first, advice after — the ordering IS the distinction the caller must not lose
    return sorted(out, key=lambda x: (0 if x.severity == "high" else 1, x.kind, x.text))
