"""Member licensing — which governed values a natural-language phrase may map to.

The rule the Instagram substitution forced into existence (findings §57): the MODEL proposes a
mapping from a phrase to a dimension member (language, its superpower), but its WORLD KNOWLEDGE
is exactly what invented "Instagram is inside paid_search" — so a proposal is honoured only when
the layer's OWN text licenses it. World knowledge may propose; only documentation may license.

A license for member m comes from two sources, both governed:
  - the member's NAME: a phrase token matching a token of m ("paid search" -> paid_search);
  - the member's CLAUSE in the dimension's governed description: the catalogue says
    "content_seo is content marketing and SEO; organic is organic; ..." — clause-per-member, and
    a phrase token inside m's clause licenses m ("SEO" -> content_seo).

The count routes: one license -> serve with the mapping DISCLOSED; several -> a member-level
contest (clarify, or both slices disclosed); zero -> no referent in this closed world — refuse
`ungoverned_dimension_value`, never fold the term into a sibling. Production layers declare
synonyms explicitly (a `synonyms:` field); the clause check is this fixture's version of the
same governed registry.
"""
from __future__ import annotations

import re

_STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "our", "we", "ads",
         "ad", "spend", "spending", "channel", "channels", "marketing", "via", "through"}


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", str(text or "").lower())
            if t not in _STOP and len(t) > 1}


def licenses(phrase: str, members, description: str = "") -> list:
    """The members of one dimension that the governed layer licenses `phrase` to mean.

    Deterministic: token overlap with member names, or with the member's own clause of the
    dimension description (clauses split on ';', each owned by the member it names). Returns []
    when nothing licenses the phrase — the closed-world no-referent verdict."""
    ptoks = _tokens(phrase)
    if not ptoks:
        return []
    members = [str(m) for m in (members or ())]
    out = []
    clauses = {}
    for clause in str(description or "").split(";"):
        for m in members:
            if m.lower() in clause.lower():
                clauses[m] = clauses.get(m, "") + " " + clause
    for m in members:
        licensed = bool(ptoks & _tokens(m.replace("_", " "))) or \
            bool(ptoks & (_tokens(clauses.get(m, "")) - _tokens(m.replace("_", " ")) - set(members)))
        if licensed:
            out.append(m)
    return out
