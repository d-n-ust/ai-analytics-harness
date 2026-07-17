# Results — AI analytics harness
_Generated 2026-07-17. 150 runs (1 models x 6 rungs x 25 questions)._

## Accuracy by rung

| rung | luna |
|---|---|
| 1 · messy data | 9/25 (36%) |
| 2 · star schema | 10/25 (40%) |
| 3 · semantic layer | 16/25 (64%) |
| 4 · + verified examples | 19/25 (76%) |
| 5 · + knowledge base | 20/25 (80%) |
| 6 · + metric tree | 24/25 (96%) |

## Question-type unlock — luna (correct-rate by tier x rung)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 3/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| filtered | 4/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| metric | 2/5 | 1/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| knowledge | 0/5 | 0/5 | 1/5 | 4/5 | 5/5 | 5/5 |
| diagnostic | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 4/5 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| luna | 1 | t1_total_habits | 7138 | 7467.0 |
| luna | 1 | t1_ios_value_moments_june | 9245 | 5648.0 |
| luna | 1 | t2_americas_value_moments_june | 5149 | 5386.0 |
| luna | 1 | t3_arpu | 30.857358490566032 | 7.24 |
| luna | 1 | t3_power_users | 496 | 151.0 |
| luna | 1 | t3_activation_rate_june | 76.85% | 0.5322 |
| luna | 1 | t4_apac_value_moments_q2 | 958 | 3852.0 |
| luna | 1 | t4_real_signups_june | 487 | 453.0 |
| luna | 1 | t4_real_acquisition_spend_june | 19138.25 | 18267.17 |
| luna | 1 | t4_retention_trend | Retention was broadly stable to slightly declining: 4-week retention averaged 52.5% for April–May cohorts, ranging from 44.6% to 57.9%. It peaked around late April/early May (56–57%) and fell to 46.1% for the June 1 cohort and 26.9% for June 8; the latter is likely incomplete because the data ends July 12. | None |
| luna | 1 | t4_business_health | Yes—based on the available product signals, the app appears healthy for the latest complete week (2026-07-06 to 2026-07-12). | None |
| luna | 2 | t2_referral_signups_q2 | 234 | 243.0 |
| luna | 2 | t3_mrr | 11448.08 | 2685.08 |
| luna | 2 | t3_arpu | 30.58192634560908 | 7.24 |
| luna | 2 | t3_activation_rate_june | 76.79558011049724% | 0.5322 |
| luna | 2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| luna | 2 | t4_real_signups_june | 433 | 453.0 |
| luna | 2 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| luna | 2 | t4_retention_trend | Retention was broadly stable: weekly active-user retention ranged from 34.9% to 38.0% across May 4–July 6, 2026. It dipped through early June, then recovered and ended at 36.8% on July 6 versus 35.8% on May 4 (+1.0 percentage point). | None |
| luna | 2 | t4_business_health | The app looks mixed—not clearly healthy yet. | None |
| luna | 3 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| luna | 3 | t4_real_signups_june | 543 | 453.0 |
| luna | 3 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| luna | 3 | t4_retention_trend | Retention has been volatile rather than consistently improving. Weekly D7 retention ranged from 34.3% to 58.0%: 40.7% (May 11), 37.3% (May 18), 51.1% (May 25), 34.3% (Jun 1), 58.0% (Jun 8), 52.7% (Jun 15), and 56.3% (Jun 22). D28 retention was 49.5%–51.1% for the May cohorts, fell to 45.1% for Jun 1 and 26.9% for Jun 8; later cohorts are not mature enough to assess D28. | None |
| luna | 4 | t4_apac_value_moments_q2 | 4355 | 3852.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| luna | 771,565 / 37,605 | $1.07 |
