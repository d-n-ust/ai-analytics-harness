#!/usr/bin/env python3
"""Validation for the aptness challenger — a JUDGE must be validated before it is trusted.

    uv run python apt_validate.py

The architecture forbids an unvalidated judge gating behaviour (the repo's original sin). Two
honesty rules govern this file:

1. TUNE vs HOLDOUT. The first 6 cases are the set the prompt was refocused AGAINST (the 'refute if
   you can' first cut scored 1/6 on them; the defect-hunting rewrite was tuned until they passed).
   A score on them measures memorisation of the tuning set, not discrimination. The 8 cases added
   later are the holdout; only the holdout score is evidence, and only it is asserted on.
2. The challenger runs on the VERIFIER resolution (get_verifier: one notch up the effort ladder,
   optionally a different model via VERIFIER_MODEL), because that is how the agent now wires it —
   validation on a different resolution than production would validate the wrong judge.

Defect classes covered: wrong population, missing/wrong window, a proxy for a different quantity, a
semi-additive summed over time, a count served as a rate. Still validated on a curated set, not
production traffic — which is why the challenger is wired to DISCLOSE, not hard-refuse.
"""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "../../..")

from agent.runtime.providers import get_verifier, load_env          # noqa: E402
from agent.guardrails.classify import challenge_aptness      # noqa: E402

# Cases 1-6: TUNE (the prompt was refocused against these — scored, never asserted on).
# Cases 7-14: HOLDOUT (added blind at 605c303 — the number that counts).
N_TUNE = 6
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
    model = get_verifier("gpt-5-mini")
    print(f"challenger model: {model.spec.name} (verifier resolution)")
    stats = {"tune": [0, 0, 0], "holdout": [0, 0, 0]}  # exact, flagged, n
    print(f"{'set':8} {'expected':10} {'predicted':10} {'ok':4}  case")
    for i, (q, defn, exp, note) in enumerate(CASES):
        part = "tune" if i < N_TUNE else "holdout"
        r = challenge_aptness(model, q, defn)
        pred = r["verdict"]
        stats[part][0] += pred == exp
        stats[part][1] += (exp != "apt") == (pred != "apt")
        stats[part][2] += 1
        print(f"{part:8} {exp:10} {pred:10} {'OK' if pred == exp else 'xx':4}  {note[:56]}")
    for part in ("tune", "holdout"):
        e, f, n = stats[part]
        print(f"\n{part}: exact {e}/{n}   apt-vs-flagged {f}/{n}")
    e, f, n = stats["holdout"]
    assert f >= 0.85 * n, "challenger fails the HOLDOUT — do not let it gate"


if __name__ == "__main__":
    main()
