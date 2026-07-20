# Results — AI analytics harness  (MOCK)
_Generated 2026-07-20. 62 runs (2 models x 1 rungs x 31 questions x 1 reps)._

## Accuracy by rung (pooled over reps)

| rung | gpt | mini |
|---|---|---|
| 1 · messy data | 0/31 (0%) | 0/31 (0%) |

## Question-type unlock — gpt (correct-rate by tier x rung)

| tier | r1 |
|---|---|
| lookup | 0/5 |
| filtered | 0/5 |
| metric | 0/5 |
| knowledge | 0/5 |
| diagnostic | 0/5 |
| unanswerable | 0/6 |

## Question-type unlock — mini (correct-rate by tier x rung)

| tier | r1 |
|---|---|
| lookup | 0/5 |
| filtered | 0/5 |
| metric | 0/5 |
| knowledge | 0/5 |
| diagnostic | 0/5 |
| unanswerable | 0/6 |

## Refusal & fabrication — gpt

| rung | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 1 | 0/25 | 25/25 | 0 | 6/6 | 0/0 | 0 | -124.0 |

## Refusal & fabrication — mini

| rung | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 1 | 0/25 | 25/25 | 0 | 6/6 | 0/0 | 0 | -124.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt | 1 | t1_value_moments_june | 0 | 16041.0 |
| gpt | 1 | t1_signups_june | 0 | 553.0 |
| gpt | 1 | t1_total_habits | 0 | 7467.0 |
| gpt | 1 | t1_spend_june | 0 | 21013.2 |
| gpt | 1 | t1_ios_value_moments_june | 0 | 5648.0 |
| gpt | 1 | t2_web_value_moments_june | 0 | 4812.0 |
| gpt | 1 | t2_referral_signups_q2 | 0 | 243.0 |
| gpt | 1 | t2_paid_search_spend_q2 | 0 | 36875.98 |
| gpt | 1 | t2_americas_value_moments_june | 0 | 5386.0 |
| gpt | 1 | t2_active_annual_subs | 0 | 134.0 |
| gpt | 1 | t3_mrr | 0 | 2685.08 |
| gpt | 1 | t3_arpu | 0 | 7.24 |
| gpt | 1 | t3_active_users_last_week | 0 | 886.0 |
| gpt | 1 | t3_power_users | 0 | 151.0 |
| gpt | 1 | t3_activation_rate_june | 0 | 0.5322 |
| gpt | 1 | t4_apac_value_moments_q2 | 0 | 3852.0 |
| gpt | 1 | t4_real_signups_june | 0 | 453.0 |
| gpt | 1 | t4_real_acquisition_spend_june | 0 | 18267.17 |
| gpt | 1 | t4_retention_trend | 0 | None |
| gpt | 1 | t4_business_health | 0 | None |
| gpt | 1 | u_churn_risk | 0 | None |
| gpt | 1 | u_engagement_score | 0 | None |
| gpt | 1 | u_apac_march | 0 | None |
| gpt | 1 | u_prelaunch_trend | 0 | None |
| gpt | 1 | u_enterprise_users | 0 | None |
| gpt | 1 | u_pricing_cause | 0 | None |
| mini | 1 | t1_value_moments_june | 0 | 16041.0 |
| mini | 1 | t1_signups_june | 0 | 553.0 |
| mini | 1 | t1_total_habits | 0 | 7467.0 |
| mini | 1 | t1_spend_june | 0 | 21013.2 |
| mini | 1 | t1_ios_value_moments_june | 0 | 5648.0 |
| mini | 1 | t2_web_value_moments_june | 0 | 4812.0 |
| mini | 1 | t2_referral_signups_q2 | 0 | 243.0 |
| mini | 1 | t2_paid_search_spend_q2 | 0 | 36875.98 |
| mini | 1 | t2_americas_value_moments_june | 0 | 5386.0 |
| mini | 1 | t2_active_annual_subs | 0 | 134.0 |
| mini | 1 | t3_mrr | 0 | 2685.08 |
| mini | 1 | t3_arpu | 0 | 7.24 |
| mini | 1 | t3_active_users_last_week | 0 | 886.0 |
| mini | 1 | t3_power_users | 0 | 151.0 |
| mini | 1 | t3_activation_rate_june | 0 | 0.5322 |
| mini | 1 | t4_apac_value_moments_q2 | 0 | 3852.0 |
| mini | 1 | t4_real_signups_june | 0 | 453.0 |
| mini | 1 | t4_real_acquisition_spend_june | 0 | 18267.17 |
| mini | 1 | t4_retention_trend | 0 | None |
| mini | 1 | t4_business_health | 0 | None |
| mini | 1 | u_churn_risk | 0 | None |
| mini | 1 | u_engagement_score | 0 | None |
| mini | 1 | u_apac_march | 0 | None |
| mini | 1 | u_prelaunch_trend | 0 | None |
| mini | 1 | u_enterprise_users | 0 | None |
| mini | 1 | u_pricing_cause | 0 | None |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt | 620 / 310 | $0.00 |
| mini | 620 / 310 | $0.00 |
