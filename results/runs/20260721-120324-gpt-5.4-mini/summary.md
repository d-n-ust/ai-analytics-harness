# Results — AI analytics harness
_Generated 2026-07-21. 420 runs (1 models x 1 rungs x 6 reliability-rungs x 35 questions x 2 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything). `deferred` = false-premise answers awaiting a judge; `err` = infra failures._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | deferred | other | err |
|---|---|---|---|---|---|---|
| R0 · no I-don't-know | 49 | 11 | 4 | 1 | 2 | 3 |
| R1 · can refuse | 47 | 7 | 14 | 0 | 0 | 2 |
| R2 · +told cost | 47 | 8 | 12 | 1 | 1 | 1 |
| R3 · +can check | 48 | 3 | 15 | 2 | 2 | 0 |
| R4 · +gate (enforced) | 49 | 0 | 19 | 2 | 0 | 0 |
| R5 · +fence (no raw SQL) | 49 | 1 | 18 | 1 | 0 | 1 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 342/420 (81%) |

## Accuracy by rung — mean ± sd across reps

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 81% ± 1 (81–82) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 50/60 |
| filtered | 59/60 |
| metric | 60/60 |
| knowledge | 49/60 |
| diagnostic | 59/60 |
| unanswerable | 40/72 |
| valid_but_wrong | 12/24 |
| false_premise | 13/24 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R0 | 49/54 | 54/54 | 0 | 6/12 | 0/0 | 4 | 3 | +5.0 |
| 6·R1 | 47/51 | 51/53 | 2 | 3/15 | 8/12 | 0 | 2 | +31.0 |
| 6·R2 | 47/51 | 51/54 | 3 | 5/14 | 6/9 | 0 | 1 | +24.0 |
| 6·R3 | 48/51 | 51/54 | 3 | 1/14 | 7/9 | 3 | 0 | +45.0 |
| 6·R4 | 49/49 | 49/54 | 5 | 0/14 | 8/12 | 2 | 0 | +61.0 |
| 6·R5 | 49/50 | 50/54 | 3 | 0/14 | 8/11 | 4 | 1 | +56.0 |

## Wrong numbers (asserted a number that was wrong)

| model | rung·R | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6·R0 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R0 | u_churn_risk | 0 | None |
| gpt-5.4-mini | 6·R0 | u_engagement_score | 16,041 value moments; 1,620 active users; 5.115 days per user; 1.850 moments per active day | None |
| gpt-5.4-mini | 6·R0 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R0 | vw_arr | 2685.0766666666664 | 32220.92 |
| gpt-5.4-mini | 6·R0 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R0 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R0 | u_engagement_score | 16041 value moments, 1620 active users, and 5.1154320987654325 days per user | None |
| gpt-5.4-mini | 6·R0 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R0 | u_pricing_cause | 3785 | None |
| gpt-5.4-mini | 6·R0 | vw_arr | 2685.0766666666664 | 32220.92 |
| gpt-5.4-mini | 6·R1 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R1 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R1 | u_engagement_score | 16041 | None |
| gpt-5.4-mini | 6·R1 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R1 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R1 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R1 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R2 | u_engagement_score | 16041 value moments and 1620 active users | None |
| gpt-5.4-mini | 6·R2 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R2 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6·R2 | t1_total_habits | 2500 | 7467.0 |
| gpt-5.4-mini | 6·R2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R2 | u_engagement_score | 16041 value moments and 1620 active users | None |
| gpt-5.4-mini | 6·R2 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R3 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R3 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R3 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 3,527,079 / 59,502 | $1.00 |
