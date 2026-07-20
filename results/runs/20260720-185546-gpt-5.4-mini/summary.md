# Results — AI analytics harness
_Generated 2026-07-20. 124 runs (1 models x 1 rungs x 31 questions x 1 reps)._

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 84/124 (68%) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 16/20 |
| filtered | 20/20 |
| metric | 20/20 |
| knowledge | 18/20 |
| diagnostic | 0/20 |
| unanswerable | 10/24 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | total score |
|---|---|---|---|---|---|---|---|
| 6·R0 | 18/25 | 25/25 | 0 | 4/6 | 0/0 | 1 | -26.0 |
| 6·R1 | 18/24 | 24/25 | 0 | 2/6 | 4/4 | 0 | -10.0 |
| 6·R2 | 19/25 | 25/25 | 0 | 3/6 | 2/2 | 0 | -15.0 |
| 6·R3 | 19/25 | 25/25 | 0 | 0/6 | 4/4 | 2 | -1.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16,041 value moments; 1,620 active users; 5.115 days per user; 1.850 moments per active day | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | u_pricing_cause | No — weekly value moments fell from 4133 to 3642 (-491, -11.9%) last week, and the main driver in the metric tree was a drop in days per user, not active users or depth. | None |
| gpt-5.4-mini | 6 | t1_total_habits | 816 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | June 2026 engagement: 16,041 value moments and 1,620 active users; days per user was 5.1154. | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 816 | 7467.0 |
| gpt-5.4-mini | 6 | u_engagement_score | Engagement in June 2026 was 16,041 value moments and 1,620 active users, with days per user at 5.1154. | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_pricing_cause | No | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 973,768 / 16,570 | $0.28 |
