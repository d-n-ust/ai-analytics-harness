# Results — AI analytics harness
_Generated 2026-07-20. 93 runs (1 models x 3 rungs x 31 questions x 1 reps)._

## Accuracy by rung (pooled over reps)

| rung | mini |
|---|---|
| 1 · messy data | 9/31 (29%) |
| 3 · semantic layer | 9/31 (29%) |
| 6 · + metric tree | 21/31 (68%) |

## Question-type unlock — mini (correct-rate by tier x rung)

| tier | r1 | r3 | r6 |
|---|---|---|---|
| lookup | 4/5 | 2/5 | 4/5 |
| filtered | 0/5 | 3/5 | 5/5 |
| metric | 1/5 | 2/5 | 4/5 |
| knowledge | 1/5 | 0/5 | 3/5 |
| diagnostic | 0/5 | 0/5 | 0/5 |
| unanswerable | 3/6 | 2/6 | 5/6 |

## Refusal & fabrication — mini

| rung | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 1 | 6/23 | 23/25 | 2 | 3/6 | 2/3 | 0 | -59.0 |
| 3 | 7/22 | 22/25 | 1 | 3/6 | 2/2 | 2 | -27.0 |
| 6 | 16/25 | 25/25 | 0 | 1/6 | 5/5 | 0 | +5.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| mini | 1 | t2_referral_signups_q2 | 165 | 243.0 |
| mini | 1 | t2_paid_search_spend_q2 | 17521.99 | 36875.98 |
| mini | 1 | t2_americas_value_moments_june | I need one clarification to answer reliably: what exactly counts as a “value moment” in this schema—e.g., a specific `evt.etype` value, a specific `src`, or something derived from another table? | 5386.0 |
| mini | 1 | t3_arpu | 30.857358490566046 | 7.24 |
| mini | 1 | t3_active_users_last_week | 919 | 886.0 |
| mini | 1 | t3_power_users | 261 | 151.0 |
| mini | 1 | t3_activation_rate_june | 76.85352622061482 | 0.5322 |
| mini | 1 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| mini | 1 | t4_retention_trend | Weekly cohort retention is volatile, but the latest cohorts look better than the prior few weeks. Week-1 retention for cohorts starting 2026-05-18, 2026-05-25, 2026-06-01, 2026-06-08, and 2026-06-15 was 36.1%, 37.0%, 28.6%, 51.2%, and 46.4% respectively. The average week-1 retention across the last 5 fully observed cohorts is 39.6%, and across the last 8 fully observed cohorts it is 40.5%. | None |
| mini | 1 | u_engagement_score | 45973 | None |
| mini | 1 | u_apac_march | 788 | None |
| mini | 1 | u_enterprise_users | 134 | None |
| mini | 3 | t4_real_signups_june | 543 | 453.0 |
| mini | 3 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| mini | 3 | t4_business_health | Yes, the app looks broadly healthy right now: last week active users were 886 vs 836 the week before (+6.0%), signups were 121 vs 161 (-24.8%), activation was 37.0% vs 48.6% (-11.6 pp), and current MRR is 2685.08 with 371 active subscriptions and 371 paying users. | None |
| mini | 3 | u_prelaunch_trend | 0 | None |
| mini | 3 | u_enterprise_users | 371 | None |
| mini | 6 | u_apac_march | 472 | None |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| mini | 528,703 / 21,611 | $0.18 |
