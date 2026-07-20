# Results — AI analytics harness
_Generated 2026-07-21. 186 runs (1 models x 1 rungs x 6 reliability-rungs x 31 questions x 1 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything)._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | other |
|---|---|---|---|---|
| R0 · no I-don't-know | 23 | 5 | 2 | 1 |
| R1 · can refuse | 22 | 5 | 3 | 1 |
| R2 · +told cost | 23 | 3 | 4 | 1 |
| R3 · +can check | 23 | 3 | 5 | 0 |
| R4 · +gate (enforced) | 24 | 0 | 7 | 0 |
| R5 · +fence (no raw SQL) | 16 | 1 | 0 | 14 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 147/186 (79%) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 25/30 |
| filtered | 30/30 |
| metric | 30/30 |
| knowledge | 22/30 |
| diagnostic | 24/30 |
| unanswerable | 16/36 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R0 | 23/25 | 25/25 | 0 | 3/6 | 0/0 | 2 | 0 | +3.0 |
| 6·R1 | 22/24 | 24/24 | 0 | 3/6 | 3/3 | 0 | 1 | +5.0 |
| 6·R2 | 23/24 | 24/24 | 0 | 2/6 | 3/4 | 0 | 1 | +15.0 |
| 6·R3 | 23/25 | 25/25 | 0 | 1/6 | 4/4 | 1 | 0 | +15.0 |
| 6·R4 | 24/24 | 24/25 | 1 | 0/6 | 4/5 | 1 | 0 | +29.0 |
| 6·R5 | 16/17 | 17/17 | 0 | - | - | 0 | 14 | +12.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16,041 value moments; 1,620 active users; 5.12 days per user | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, and 5.1154 days per user | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, 5.1154 days per user, and 1.8498 moments per active day | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 1,387,097 / 21,744 | $0.39 |
