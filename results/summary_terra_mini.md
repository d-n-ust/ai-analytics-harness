# Results — AI analytics harness
_Generated 2026-07-17. 300 runs (2 models x 6 rungs x 25 questions)._

## Accuracy by rung

| rung | gpt | mini |
|---|---|---|
| 1 · messy data | 9/25 (36%) | 4/25 (16%) |
| 2 · star schema | 12/25 (48%) | 9/25 (36%) |
| 3 · semantic layer | 17/25 (68%) | 13/25 (52%) |
| 4 · + verified examples | 21/25 (84%) | 19/25 (76%) |
| 5 · + knowledge base | 20/25 (80%) | 19/25 (76%) |
| 6 · + metric tree | 23/25 (92%) | 17/25 (68%) |

## Question-type unlock — gpt (correct-rate by tier x rung)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 4/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| filtered | 3/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| metric | 2/5 | 3/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| knowledge | 0/5 | 0/5 | 1/5 | 5/5 | 5/5 | 5/5 |
| diagnostic | 0/5 | 1/5 | 1/5 | 1/5 | 0/5 | 3/5 |

## Question-type unlock — mini (correct-rate by tier x rung)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 3/5 | 5/5 | 4/5 | 4/5 | 4/5 | 5/5 |
| filtered | 1/5 | 3/5 | 3/5 | 5/5 | 5/5 | 4/5 |
| metric | 0/5 | 0/5 | 4/5 | 5/5 | 5/5 | 5/5 |
| knowledge | 0/5 | 1/5 | 2/5 | 4/5 | 5/5 | 3/5 |
| diagnostic | 0/5 | 0/5 | 0/5 | 1/5 | 0/5 | 0/5 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt | 1 | t1_ios_value_moments_june | 1316 | 5648.0 |
| gpt | 1 | t2_web_value_moments_june | 1068 | 4812.0 |
| gpt | 1 | t2_referral_signups_q2 | 165 | 243.0 |
| gpt | 1 | t3_active_users_last_week | 919 | 886.0 |
| gpt | 1 | t3_activation_rate_june | 98.55334538878843% | 0.5322 |
| gpt | 1 | t4_real_signups_june | 512 | 453.0 |
| gpt | 1 | t4_real_acquisition_spend_june | 12987.77 | 18267.17 |
| gpt | 1 | t4_retention_trend | 42.3% | None |
| gpt | 1 | t4_business_health | Cautiously healthy, with a meaningful acquisition/conversion warning. | None |
| gpt | 2 | t1_ios_value_moments_june | 0 | 5648.0 |
| gpt | 2 | t2_web_value_moments_june | 0 | 4812.0 |
| gpt | 2 | t3_activation_rate_june | 60.773480662983424% | 0.5322 |
| gpt | 2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt | 2 | t4_real_signups_june | 433 | 453.0 |
| gpt | 2 | t4_real_acquisition_spend_june | 19138.25 | 18267.17 |
| gpt | 2 | t4_retention_trend | Week-over-week retention declined overall from 51.8% (week of May 18) to 45.8% (week of July 6), after bottoming at 45.4% in early June and recovering to 48.3% in late June before the latest dip. | None |
| gpt | 2 | t4_business_health | The app appears broadly healthy, but engagement intensity and reminder delivery warrant attention. | None |
| gpt | 3 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt | 3 | t4_real_signups_june | 553 | 453.0 |
| gpt | 3 | t4_real_acquisition_spend_june | 19138.25 | 18267.17 |
| gpt | 3 | t4_retention_trend | Retention has been stable to slightly improving: month-1 retention increased from 80.51% for the April signup cohort to 84.50% for May (March: 84.05%), while month-2 retention rose from 78.45% (March) to 80.93% (April). | None |
| mini | 1 | t1_value_moments_june | 26335 | 16041.0 |
| mini | 1 | t1_ios_value_moments_june | 1316 | 5648.0 |
| mini | 1 | t2_web_value_moments_june | 0 | 4812.0 |
| mini | 1 | t2_referral_signups_q2 | 165 | 243.0 |
| mini | 1 | t2_paid_search_spend_q2 | 11433.65 | 36875.98 |
| mini | 1 | t2_americas_value_moments_june | 8741 | 5386.0 |
| mini | 1 | t3_mrr | 11448.08 | 2685.08 |
| mini | 1 | t3_arpu | 30.857358490566046 | 7.24 |
| mini | 1 | t3_active_users_last_week | 919 | 886.0 |
| mini | 1 | t3_power_users | 421 | 151.0 |
| mini | 1 | t3_activation_rate_june | 76.85352622061482% | 0.5322 |
| mini | 1 | t4_apac_value_moments_q2 | 7137 | 3852.0 |
| mini | 1 | t4_real_signups_june | 468 | 453.0 |
| mini | 1 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| mini | 1 | t4_business_health | I can’t answer this reliably from the available data alone. | None |
| mini | 2 | t2_web_value_moments_june | 0 | 4812.0 |
| mini | 2 | t3_mrr | 11448.08 | 2685.08 |
| mini | 2 | t3_arpu | 30.857358490566046 | 7.24 |
| mini | 2 | t3_active_users_last_week | 919 | 886.0 |
| mini | 2 | t3_power_users | 184 | 151.0 |
| mini | 2 | t3_activation_rate_june | 76.85% | 0.5322 |
| mini | 2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| mini | 2 | t4_real_signups_june | 433 | 453.0 |
| mini | 2 | t4_real_acquisition_spend_june | 21013.2 | 18267.17 |
| mini | 3 | t1_total_habits | 2500 | 7467.0 |
| mini | 3 | t2_referral_signups_q2 | 234 | 243.0 |
| mini | 3 | t2_americas_value_moments_june | 5133 | 5386.0 |
| mini | 3 | t3_activation_rate_june | 0.5124275062137531 | 0.5322 |
| mini | 3 | t4_apac_value_moments_q2 | 4239 | 3852.0 |
| mini | 3 | t4_real_signups_june | 0 | 453.0 |
| mini | 3 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| mini | 4 | t1_total_habits | 67132 | 7467.0 |
| mini | 4 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| mini | 5 | t1_total_habits | 67132 | 7467.0 |
| mini | 6 | t2_referral_signups_q2 | 234 | 243.0 |
| mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt | 713,082 / 38,113 | $1.27 |
| mini | 781,910 / 38,173 | $0.27 |
