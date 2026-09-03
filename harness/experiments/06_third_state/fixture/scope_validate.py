#!/usr/bin/env python3
"""Validation for the shadow Scope reader — a JUDGE must be validated before it is trusted.

    uv run python scope_validate.py

Twelve labelled questions covering every component the record types: measure, segments, period,
compare_period, breakdown, qualifiers, chose, presupposition. HONESTY: this set is authored with
the prompt (a TUNE set); the field test is the shadow suite run, where the record's per-field
agreement with the live classifier stack is measured over questions this file never saw. The
reader gates nothing in phase 1 either way.

Scoring is per FIELD, not per question: presence/absence must match the label, and where the
label names expected words, the reported span must contain them (the reader quotes minimal spans
of the question; exact-span equality would test the label author, not the judge)."""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")

from agent.runtime.providers import get_model, load_env             # noqa: E402
from agent.guardrails.classify import read_scope                    # noqa: E402

# (question, {field: expected}) — a field absent from the label must come back empty/None.
# String label: the reported span must CONTAIN these words. List label: one entry per item.
CASES = [
    ("How many people from Germany signed up in the first half of 2026?",
     {"measure": "signed up", "segments": ["Germany"], "period": "first half of 2026"}),
    ("How many people signed up through referrals in the fourth quarter of 2025?",
     {"measure": "signed up", "segments": ["referrals"], "period": "fourth quarter of 2025"}),
    ("How much did we spend on Instagram ads in June 2026?",
     {"measure": "spend", "segments": ["Instagram ads"], "period": "June 2026"}),
    ("How many customer accounts, not counting staff or test users, were active in June 2026?",
     {"measure": "accounts", "period": "June 2026",
      "qualifiers": ["not counting staff or test users"]}),
    ("How many support tickets did we receive last week?",
     {"measure": "support tickets", "period": "last week"}),
    ("What did it cost us in marketing for each person who signed up in the first quarter of 2026?",
     {"measure": "cost us in marketing for each person", "period": "first quarter of 2026"}),
    ("Which acquisition channel gives us the best 90-day retention?",
     {"measure": "90-day retention", "breakdown": "acquisition channel"}),
    ("Why did signups collapse in June?",
     {"measure": "signups", "period": "June",
      "presupposes": {"kind": "direction", "claim": "fell", "quote": "collapse"}}),
    ("Did active users grow in May 2026 compared to April?",
     {"measure": "active users", "period": "May 2026", "compare_period": "April"}),
    ("Including the internal partnerships test integration, how much did we spend on marketing in December 2025?",
     {"measure": "spend on marketing", "period": "December 2025",
      "qualifiers": ["Including the internal partnerships test integration"]}),
    ("How many active users did we have in October 2026?",
     {"measure": "active users", "period": "October 2026"}),
    ("On average, how many habits did each active user complete in March 2026?",
     {"measure": "habits did each active user complete", "period": "March 2026"}),
]

LIST_FIELDS = ("segments", "qualifiers")
STR_FIELDS = ("measure", "period", "compare_period", "breakdown")


def _contains(span: str, words: str) -> bool:
    return words.lower() in span.lower()


def main() -> None:
    load_env()
    model = get_model("gpt-5-mini")
    field_ok = field_n = 0
    for q, want in CASES:
        rec = read_scope(model, q)
        errs = []
        for f in STR_FIELDS:
            expected, got = want.get(f, ""), rec.get(f, "")
            field_n += 1
            if (not expected and not got) or (expected and got and _contains(got, expected)):
                field_ok += 1
            else:
                errs.append(f"{f}: want {expected!r} got {got!r}")
        for f in LIST_FIELDS:
            expected, got = want.get(f, []), rec.get(f, [])
            field_n += 1
            if len(expected) == len(got) and all(
                    any(_contains(g, e) for g in got) for e in expected):
                field_ok += 1
            else:
                errs.append(f"{f}: want {expected!r} got {got!r}")
        p_want, p_got = want.get("presupposes"), rec.get("presupposes")
        field_n += 1
        if (p_want is None) == (p_got is None) and (
                p_want is None or (p_got["kind"] == p_want["kind"]
                                   and p_got["claim"] == p_want["claim"]
                                   and _contains(p_got["quote"], p_want["quote"]))):
            field_ok += 1
        else:
            errs.append(f"presupposes: want {p_want!r} got {p_got!r}")
        mark = "OK " if not errs else "xx "
        print(f"{mark} {q[:72]}")
        for e in errs:
            print(f"      {e}")
        if rec.get("unverified"):
            print(f"      (unverified spans dropped: {rec['unverified']})")
    print(f"\nfields: {field_ok}/{field_n}")
    assert field_ok >= 0.85 * field_n, "scope reader below the tune-set floor — do not shadow it yet"


if __name__ == "__main__":
    main()
