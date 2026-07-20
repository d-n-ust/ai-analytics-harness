# Results — AI analytics harness
_Generated 2026-07-20. 496 runs (2 models x 1 rungs x 4 reliability-rungs x 31 questions x 2 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything)._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | other |
|---|---|---|---|---|
| R0 · no I-don't-know | 47 | 9 | 4 | 2 |
| R1 · can refuse | 46 | 9 | 6 | 1 |
| R2 · +told cost | 45 | 8 | 8 | 1 |
| R3 · +can check | 48 | 3 | 11 | 0 |

## Response mix — gpt-5.6-terra  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything)._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | other |
|---|---|---|---|---|
| R0 · no I-don't-know | 50 | 7 | 2 | 3 |
| R1 · can refuse | 50 | 2 | 10 | 0 |
| R2 · +told cost | 49 | 3 | 10 | 0 |
| R3 · +can check | 50 | 0 | 12 | 0 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini | gpt-5.6-terra |
|---|---|---|
| 6 · + metric tree | 206/248 (83%) | 228/248 (92%) |

## Accuracy by rung — mean ± sd across reps

| rung | gpt-5.4-mini | gpt-5.6-terra |
|---|---|---|
| 6 · + metric tree | 83% ± 3 (81–85) | 92% ± 1 (91–93) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 34/40 |
| filtered | 39/40 |
| metric | 40/40 |
| knowledge | 34/40 |
| diagnostic | 39/40 |
| unanswerable | 20/48 |

## Question-type unlock — gpt-5.6-terra (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 40/40 |
| filtered | 40/40 |
| metric | 40/40 |
| knowledge | 40/40 |
| diagnostic | 39/40 |
| unanswerable | 29/48 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R0 | 47/50 | 50/50 | 0 | 6/12 | 0/0 | 4 | 0 | +11.0 |
| 6·R1 | 46/50 | 50/50 | 0 | 5/11 | 6/6 | 0 | 1 | +16.0 |
| 6·R2 | 45/49 | 49/50 | 1 | 4/12 | 4/5 | 2 | 0 | +18.0 |
| 6·R3 | 48/50 | 50/50 | 0 | 1/12 | 9/9 | 2 | 0 | +45.0 |

## Refusal & fabrication — gpt-5.6-terra

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R0 | 50/50 | 50/50 | 0 | 7/12 | 0/0 | 2 | 0 | +22.0 |
| 6·R1 | 50/50 | 50/50 | 0 | 2/12 | 9/9 | 1 | 0 | +51.0 |
| 6·R2 | 49/50 | 50/50 | 0 | 2/12 | 8/8 | 2 | 0 | +45.0 |
| 6·R3 | 50/50 | 50/50 | 0 | 0/12 | 12/12 | 0 | 0 | +62.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | u_engagement_score | Overall engagement in June 2026 was 16,041 value moments, with 1,620 active users, 5.12 days per user, and 1.85 moments per active day. | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, 5.1154320987654325 days per user, and 1.8497646916857728 moments per day | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | Engagement in June 2026 was 16,041 value moments and 1,620 active users; days per user was 5.1154. | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, 5.1154 days per user, and 1.8498 moments per day | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_engagement_score | 16041 value moments, 1620 active users, and 5.1154320987654325 days per user in June 2026 | None |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6 | u_apac_march | 472 | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |
| gpt-5.6-terra | 6 | u_apac_march | 0 | None |
| gpt-5.6-terra | 6 | u_enterprise_users | 0 | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |
| gpt-5.6-terra | 6 | u_apac_march | 0 | None |
| gpt-5.6-terra | 6 | u_enterprise_users | 0 | None |
| gpt-5.6-terra | 6 | u_pricing_cause | No—there is no evidence that the pricing change caused the dip: value moments fell 11.88% (4,133 to 3,642) last week, driven by a 16.44% decline in days per user, while active users rose 5.98%; the metric tree contains no pricing signal or causal link. | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |
| gpt-5.6-terra | 6 | u_engagement_score | 16,041 value moments and 1,620 active users | None |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 1,931,255 / 31,708 | $0.55 |
| gpt-5.6-terra | 1,417,726 / 31,588 | $2.09 |
