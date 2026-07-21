# Results — AI analytics harness
_Generated 2026-07-21. 420 runs (1 models x 1 rungs x 6 reliability-rungs x 35 questions x 2 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything). `deferred` = false-premise answers awaiting a judge; `err` = infra failures._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | deferred | other | err |
|---|---|---|---|---|---|---|
| R0 · no I-don't-know | 49 | 9 | 6 | 2 | 3 | 1 |
| R1 · can refuse | 47 | 5 | 14 | 2 | 2 | 0 |
| R2 · +told cost | 49 | 5 | 14 | 0 | 1 | 1 |
| R3 · +can check | 50 | 1 | 17 | 1 | 1 | 0 |
| R4 · +gate (enforced) | 48 | 0 | 17 | 2 | 1 | 2 |
| R5 · +fence (no raw SQL) | 48 | 1 | 19 | 0 | 0 | 2 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 349/420 (83%) |

## Accuracy by rung — mean ± sd across reps

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 83% ± 1 (82–84) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 51/60 |
| filtered | 60/60 |
| metric | 60/60 |
| knowledge | 52/60 |
| diagnostic | 56/60 |
| unanswerable | 45/72 |
| valid_but_wrong | 12/24 |
| false_premise | 13/24 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R0 | 49/54 | 54/54 | 0 | 4/13 | 0/0 | 6 | 1 | +13.0 |
| 6·R1 | 47/51 | 51/54 | 3 | 2/14 | 7/11 | 0 | 0 | +38.0 |
| 6·R2 | 49/51 | 51/54 | 3 | 3/15 | 6/11 | 0 | 1 | +40.0 |
| 6·R3 | 50/52 | 52/54 | 2 | 0/15 | 10/12 | 3 | 0 | +58.0 |
| 6·R4 | 48/48 | 48/52 | 4 | 0/14 | 9/11 | 2 | 2 | +59.0 |
| 6·R5 | 48/49 | 49/53 | 4 | 0/15 | 9/13 | 2 | 2 | +57.0 |

## Wrong numbers (asserted a number that was wrong)

| model | rung·R | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6·R0 | t1_total_habits | 0 | 7467.0 |
| gpt-5.4-mini | 6·R0 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R0 | u_engagement_score | 156482 | None |
| gpt-5.4-mini | 6·R0 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R0 | vw_arr | 2685.0766666666664 | 32220.92 |
| gpt-5.4-mini | 6·R0 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R0 | u_engagement_score | 16041 value moments and 1620 active users | None |
| gpt-5.4-mini | 6·R0 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R0 | vw_arr | 2685.0766666666664 | 32220.92 |
| gpt-5.4-mini | 6·R1 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R1 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R1 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R1 | u_engagement_score | 16041 value moments; 1620 active users; 5.1154 days per user | None |
| gpt-5.4-mini | 6·R1 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R2 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R2 | u_apac_march | 472 | None |
| gpt-5.4-mini | 6·R2 | u_prelaunch_trend | 0 | None |
| gpt-5.4-mini | 6·R2 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R2 | u_engagement_score | 16041 | None |
| gpt-5.4-mini | 6·R3 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 3,380,615 / 58,312 | $0.96 |
