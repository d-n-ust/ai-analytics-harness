"""Measure the value-binding seam: how well the deterministic resolver maps a free-text
filter value in a question onto the governed dimension member — the NL->object binding
the R6 spec check does NOT cover (it makes entity/segment/measure/grain exact, but the
filter VALUES stay free text). This turns "the binding is the part you didn't measure"
into two reported numbers:

  coverage:        of values that SHOULD resolve, how many did — to the RIGHT member.
  false-refusal:   of values that should resolve, how many the resolver rejected.
  correct-refusal: of values with no governed member, how many were correctly rejected.

No LLM: the resolver is deterministic (synonym lookup), so this measures the synonym
table's quality. The aliases below are authored as natural phrasings a user would type,
INCLUDING ones not spelled out in the table, so the coverage number is honest (exact
matching misses multi-word phrases like "Apple devices") rather than table-self-checking.

Run: PYTHONPATH=. .venv/bin/python evaluation/resolver_eval.py
"""

from __future__ import annotations

from harness.semantic import SemanticLayer
from harness.warehouse import open_warehouse

# (dimension, value-as-a-user-would-type-it, expected member or None to mean "refuse")
CASES = [
    ("platform", "iPhone", "ios"), ("platform", "Apple", "ios"), ("platform", "iOS", "ios"),
    ("platform", "Apple devices", "ios"), ("platform", "Android phones", "android"),
    ("platform", "browser", "web"), ("platform", "the web", "web"),
    ("platform", "Windows", None), ("platform", "Blackberry", None),
    ("region", "Asia", "APAC"), ("region", "APAC", "APAC"), ("region", "Europe", "EMEA"),
    ("region", "North America", "Americas"), ("region", "the Americas", "Americas"),
    ("region", "Antarctica", None),
    ("plan", "annual", "annual"), ("plan", "yearly", "annual"), ("plan", "monthly plan", "monthly"),
    ("plan", "premium", None),                       # premium is a segment word, not a plan
    ("channel", "paid search", "paid_search"), ("channel", "SEO", "content_seo"),
    ("channel", "referrals", "referral"), ("channel", "google ads", "paid_search"),
    ("channel", "email", None),                      # email isn't a governed channel
    ("country", "US", "US"), ("country", "UK", "GB"), ("country", "Germany", "DE"),
    ("country", "Spain", None),
]


def main():
    sem = SemanticLayer(open_warehouse())
    should_resolve = [c for c in CASES if c[2] is not None]
    should_refuse = [c for c in CASES if c[2] is None]
    right = wrong = false_refused = correct_refused = 0
    misses = []

    for dim, value, expected in CASES:
        got = sem.resolve_member(dim, value)
        if expected is not None:                     # should resolve to `expected`
            if got == expected:
                right += 1
            elif got is None:
                false_refused += 1
                misses.append(f"false-refuse: {dim}={value!r} (wanted {expected})")
            else:
                wrong += 1
                misses.append(f"WRONG BIND: {dim}={value!r} -> {got} (wanted {expected})")
        else:                                        # should refuse
            correct_refused += 1 if got is None else 0
            if got is not None:
                misses.append(f"should-refuse but bound: {dim}={value!r} -> {got}")

    n_res, n_ref = len(should_resolve), len(should_refuse)
    print(f"Value-binding eval — {len(CASES)} cases ({n_res} should-resolve, {n_ref} should-refuse)\n")
    print(f"coverage (right member) : {right}/{n_res} = {right/n_res:.0%}")
    print(f"wrong binding           : {wrong}/{n_res} = {wrong/n_res:.0%}")
    print(f"false-refusal           : {false_refused}/{n_res} = {false_refused/n_res:.0%}")
    print(f"correct-refusal         : {correct_refused}/{n_ref} = {correct_refused/n_ref:.0%}")
    if misses:
        print("\nmisses (the honest tail — exact matching drops multi-word phrasings):")
        for m in misses:
            print("  " + m)


if __name__ == "__main__":
    main()
