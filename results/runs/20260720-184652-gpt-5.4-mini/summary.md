# Results — AI analytics harness
_Generated 2026-07-20. 124 runs (1 models x 1 rungs x 31 questions x 1 reps)._

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 70/124 (56%) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 13/20 |
| filtered | 16/20 |
| metric | 16/20 |
| knowledge | 15/20 |
| diagnostic | 0/20 |
| unanswerable | 10/24 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 6·R0 | 18/25 | 25/25 | 0 | 4/6 | 0/0 | 2 | -18.0 |
| 6·R1 | 16/24 | 24/25 | 1 | 2/6 | 4/4 | 0 | +4.0 |
| 6·R2 | 14/25 | 25/25 | 0 | 2/6 | 3/4 | 0 | -2.0 |
| 6·R3 | 12/25 | 25/25 | 0 | 3/6 | 2/2 | 1 | -2.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | Need clarification | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | No data | None |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, 5.1154320987654325 days per user, and 1.8497646916857728 moments per active day | None |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, 5.1154 days per user, and 1.8498 moments per day | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 703,307 / 12,680 | $0.20 |
