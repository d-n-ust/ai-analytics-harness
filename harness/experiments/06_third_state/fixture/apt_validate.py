#!/usr/bin/env python3
"""Validation for the aptness challenger — a JUDGE must be validated before it is trusted.

    uv run python apt_validate.py

The architecture forbids an unvalidated judge gating behaviour (the repo's original sin). This is the
held-out check: 14 labelled (question, definition, expected) cases, clear-cut by construction,
measuring whether the challenger discriminates an APT definition from a DEFECT (wrong population,
missing/wrong window, a proxy for a different quantity, a semi-additive summed over time, a count
served as a rate). A first cut that flagged everything ('refute if you can') scored 1/6; the
refocused defect-hunting prompt scores 13/14 exact and 14/14 apt-vs-flagged — the one non-exact is a
contested case flagged as `wrong` (still flagged, a defensible call). The `assert flagged >= 0.85*n`
guards the discriminator so a regression cannot silently make it gate on noise. Still validated on a
curated set, not production traffic — which is why the challenger is wired to DISCLOSE, not
hard-refuse.
"""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")

from agent.providers import get_model, load_env             # noqa: E402
from agent.guardrails.classify import challenge_aptness      # noqa: E402

CASES = [
    ("How many active users did we have last week?",
     "governed metric active_users: distinct accounts with activity, EXCLUDING internal and test accounts, last week",
     "apt", "a governed metric answering its own concept"),
    ("How many app opens per active user last week?",
     "ratio of governed metrics: app_opens divided by active_users, last week",
     "apt", "a faithful per-unit ratio of two governed metrics"),
    ("How many active users did we have last week?",
     "governed metric active_accounts: distinct accounts INCLUDING internal and test accounts, last week",
     "wrong", "wrong population — includes internal/test"),
    ("What did it cost us in marketing for each person who signed up in Q2 2026?",
     "ratio: marketing_spend (ALL marketing channels) divided by new_signups, Q2 2026",
     "apt", "marketing_spend is a defensible literal reading; the contest is the deterministic layer's"),
    ("Which acquisition channel gives us the best 90-day retention?",
     "raw SQL: share of each channel's signup cohort with ANY activity at any time after signup (no 90-day window), by channel",
     "wrong", "no 90-day window at all"),
    ("Which acquisition channel gives us the best 90-day retention?",
     "raw SQL: share of each channel's signup cohort with at least one activity WITHIN 90 days of signup, by channel",
     "apt", "the standard within-90-days cohort-retention reading (debatable — see header)"),
    # apt: governed metrics answering their own concept, with a filter or period applied
    ("How many people signed up in the first quarter of 2026?",
     "governed metric new_signups for 2026-Q1", "apt", "a governed metric with a period"),
    ("How much did we spend on paid search advertising?",
     "governed metric marketing_spend filtered to channel = paid_search",
     "apt", "a governed metric with a governed segment filter"),
    ("What is our monthly recurring revenue right now?",
     "governed metric mrr, the running figure with no period", "apt", "the governed running figure"),
    # wrong: a defect a competent analyst would name
    ("What was our revenue per employee last quarter?",
     "total mrr divided by the number of active users last quarter",
     "wrong", "active users are not employees — wrong denominator, a different quantity"),
    ("How many active users did we have last week?",
     "raw SQL: SUM of the daily active_users counts over the seven days of last week",
     "wrong", "summing a distinct count over time double-counts — semi-additive violation"),
    ("What was our subscription churn RATE last quarter?",
     "governed metric: the COUNT of subscriptions with status = canceled last quarter",
     "wrong", "a count, not a rate — the denominator (subscriptions at risk) is missing"),
    ("What was the average order value last month?",
     "ratio: total marketing_spend divided by new_signups last month",
     "wrong", "measures marketing cost per signup, not order value — a proxy for a different quantity"),
    # contested: two named governed metrics genuinely both fit (rare)
    ("How much recurring revenue do we have, counting terms later refunded?",
     "governed metric mrr (net of refunds)",
     "contested", "gross_mrr (gross of refunds) is the reading the phrase 'counting refunded' names"),
]


def main() -> None:
    load_env()
    model = get_model("gpt-5-mini")
    exact = flagged = 0
    print(f"{'expected':10} {'predicted':10} {'ok':4}  case")
    for q, defn, exp, note in CASES:
        r = challenge_aptness(model, q, defn)
        pred = r["verdict"]
        exact += pred == exp
        flagged += (exp != "apt") == (pred != "apt")
        print(f"{exp:10} {pred:10} {'OK' if pred == exp else 'xx':4}  {note[:56]}")
    n = len(CASES)
    print(f"\nexact verdict: {exact}/{n}   apt-vs-flagged: {flagged}/{n}")
    assert flagged >= 0.85 * n, "challenger no longer discriminates apt from defect — do not let it gate"


if __name__ == "__main__":
    main()
