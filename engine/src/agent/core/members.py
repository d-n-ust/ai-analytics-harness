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


def _stem_match(a: set, b: set) -> bool:
    """Token sets share a stem: exact, or one is a prefix of the other (>=4 chars) —
    "organically" licenses `organic`, "referrals" licenses `referral`. Morphology broke the
    exact-token first cut on its first full-suite exposure."""
    for x in a:
        for y in b:
            if x == y or (len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))):
                return True
    return False


def licenses(phrase: str, members, description: str = "", dimension: str = "") -> list:
    """The members of one dimension that the governed layer licenses `phrase` to mean.

    Deterministic evidence, three sources: the member's NAME (stem-matched, so "organically"
    licenses `organic`), the member's own clause of the dimension description (split on ';'),
    and — the production-shaped source — SYNONYMS the description declares in parentheses after
    a member ("DE (Germany)"). GENERIC descriptor tokens are suppressed before matching: a token
    from the dimension's own name, or one that would license more than half the members ("web
    PLATFORM" — 'platform' describes the dimension, 'web' selects the member), is a descriptor,
    not a selector; the first cut licensed all four platforms off the word "platform" and turned
    a clear question into a false contest. Returns [] when nothing licenses the phrase — the
    closed-world no-referent verdict."""
    ptoks = _tokens(phrase)
    ptoks -= _tokens(dimension.replace("__", " ").replace("_", " "))
    if not ptoks:
        return []
    members = [str(m) for m in (members or ())]
    clauses = {}
    for clause in str(description or "").split(";"):
        for m in members:
            # WORD boundary, not substring: the code IN sits inside "PhilippINes" and "IndonesIa",
            # and substring clause-assignment licensed IN off both neighbours' clauses
            if re.search(rf"\b{re.escape(m)}\b", clause, re.IGNORECASE):
                clauses[m] = clauses.get(m, "") + " " + clause

    def support(m):
        own = _tokens(m.replace("_", " "))
        doc = _tokens(clauses.get(m, "")) - own - set(x.lower() for x in members)
        return own | doc

    per = {m: support(m) for m in members}
    # a token supporting more than half the members is a descriptor of the DIMENSION, not a
    # selector of a member — drop it before deciding
    generic = {t for t in ptoks
               if sum(1 for m in members if _stem_match({t}, per[m])) > len(members) / 2}
    ptoks -= generic
    if not ptoks:
        return []
    return [m for m in members if _stem_match(ptoks, per[m])]
