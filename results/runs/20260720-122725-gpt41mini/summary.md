# Results — AI analytics harness
_Generated 2026-07-20. 93 runs (1 models x 3 rungs x 31 questions x 1 reps)._

## Accuracy by rung (pooled over reps)

| rung | gpt41mini |
|---|---|
| 1 · messy data | 6/31 (19%) |
| 3 · semantic layer | 17/31 (55%) |
| 6 · + metric tree | 20/31 (65%) |

## Question-type unlock — gpt41mini (correct-rate by tier x rung)

| tier | r1 | r3 | r6 |
|---|---|---|---|
| lookup | 4/5 | 5/5 | 5/5 |
| filtered | 1/5 | 5/5 | 5/5 |
| metric | 0/5 | 4/5 | 5/5 |
| knowledge | 1/5 | 2/5 | 4/5 |
| diagnostic | 0/5 | 0/5 | 1/5 |
| unanswerable | 0/6 | 1/6 | 0/6 |

## Refusal & fabrication — gpt41mini

| rung | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 1 | 6/19 | 19/25 | 0 | 3/6 | 0/0 | 0 | -58.0 |
| 3 | 16/24 | 24/25 | 0 | 2/6 | 1/1 | 0 | -11.0 |
| 6 | 20/25 | 25/25 | 0 | 4/6 | 0/0 | 0 | +4.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt41mini | 1 | t2_web_value_moments_june | 7967 | 4812.0 |
| gpt41mini | 1 | t2_referral_signups_q2 | 90 | 243.0 |
| gpt41mini | 1 | t2_paid_search_spend_q2 | 9709.05 | 36875.98 |
| gpt41mini | 1 | t2_americas_value_moments_june | 15309 | 5386.0 |
| gpt41mini | 1 | t3_mrr | 11448.08 | 2685.08 |
| gpt41mini | 1 | t3_arpu | 27.68 | 7.24 |
| gpt41mini | 1 | t3_active_users_last_week | 919 | 886.0 |
| gpt41mini | 1 | t3_power_users | 11 | 151.0 |
| gpt41mini | 1 | t4_apac_value_moments_q2 | 10759 | 3852.0 |
| gpt41mini | 1 | t4_real_acquisition_spend_june | 15532.84 | 18267.17 |
| gpt41mini | 1 | t4_retention_trend | Retention rates for new user cohorts from May to early July 2026 show modest fluctuations but no strong upward or downward trend; retention after signup week typically starts around 25%-40% and fluctuates around 35%-50% in subsequent weeks within the available data. | None |
| gpt41mini | 1 | u_churn_risk | 41, 155, 191, 205, 229, 242, 310, 321, 332, 342 | None |
| gpt41mini | 1 | u_apac_march | 472 | None |
| gpt41mini | 1 | u_enterprise_users | 78 | None |
| gpt41mini | 3 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt41mini | 3 | t4_real_signups_june | 543 | 453.0 |
| gpt41mini | 3 | u_apac_march | 472 | None |
| gpt41mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt41mini | 6 | u_engagement_score | Engagement score = 16041 value moments and 1620 active users in June 2026 | None |
| gpt41mini | 6 | u_apac_march | 472 | None |
| gpt41mini | 6 | u_prelaunch_trend | The weekly value moments in July 2025 cannot be reported because there is no data available for that period. However, I do have data for the latest weeks in July 2026 if that is of interest. | None |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt41mini | 582,339 / 25,058 | $0.27 |
