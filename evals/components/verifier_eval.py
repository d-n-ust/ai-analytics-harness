"""Isolated test of the trajectory verifier (harness/verifier.py).

Each case is a REAL trajectory — the metric + call args are compiled to SQL and run against the
warehouse, so the verifier sees the actual definition, SQL, and result. We hand-pick the exact
cases that broke the other two mechanisms, so we can see whether trajectory-inspection catches the
hard errors while passing the answers the intent parser (arpu) and the recompute judge (MRR) got wrong.

  should FLAG:  spend narrowed to 4/5 channels; a RATE served for a 'how many' count; the 371/457
                floor (currently-active metric for an all-time-total question)
  should PASS:  the correct spend total; arpu (intent parser false-refused this); MRR (judge false-
                overturned this); a plain count; a filter the question DID ask for (annual plan)

Run:  OPENAI_REASONING=low python evaluation/verifier_eval.py
"""

from __future__ import annotations

from agent.models import get_model
from agent.verifier import verify_trajectory
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse

# (label, question, metric, call_args, should_flag)
CASES = [
    ("spend_narrowed", "What was our total marketing spend in June 2026?", "marketing_spend",
     {"start": "2026-06-01", "end": "2026-06-30",
      "filters": {"channel": ["paid_search", "referral", "content_seo", "organic"]}}, True),
    ("rate_for_count",
     "How many people who signed up in June 2026 reached their first completed habit within a week?",
     "activation_rate", {"start": "2026-06-01", "end": "2026-06-30"}, True),
    ("total_subs_floor", "How many subscriptions have we sold in total?",
     "active_subscriptions", {}, True),
    ("spend_total_ok", "What was our total marketing spend in June 2026?", "marketing_spend",
     {"start": "2026-06-01", "end": "2026-06-30"}, False),
    ("arpu_ok", "What is our ARPU (average monthly recurring revenue per paying user)?",
     "arpu", {}, False),
    ("mrr_ok", "What is our current MRR?", "mrr", {}, False),
    ("signups_ok", "How many new users signed up in June 2026?", "new_signups",
     {"start": "2026-06-01", "end": "2026-06-30"}, False),
    ("active_annual_ok", "How many currently-active subscriptions are on the annual plan?",
     "active_subscriptions", {"filters": {"plan": "annual"}}, False),
]


def main():
    con = open_warehouse()
    sem = SemanticLayer(con)
    model = get_model("gpt-5-mini")

    right = 0
    print(f"{'case':18} {'expect':6} {'verdict':7} {'mismatch':11} ok  reason")
    print("-" * 110)
    for label, question, metric, args, should_flag in CASES:
        sql = sem.compile(metric, resolve=True, **args)
        _, rows = sem.query(metric, resolve=True, **args)
        result = rows[0][-1] if rows else None
        window = args.get("period") or (f"{args.get('start')}..{args.get('end')}"
                                        if args.get("start") or args.get("end") else None)
        answers, mismatch, reason = verify_trajectory(
            model, question, metric, sem.metrics.get(metric), sql, result, result,
            applied_filters=args.get("filters"), time_window=window)
        flagged = not answers
        ok = flagged == should_flag
        right += ok
        print(f"{label:18} {'FLAG' if should_flag else 'PASS':6} "
              f"{'FLAG' if flagged else 'pass':7} {mismatch:11} {'Y' if ok else 'N '}  {reason[:70]}")
    print("-" * 110)
    print(f"verifier correct on {right}/{len(CASES)} cases")


if __name__ == "__main__":
    main()
