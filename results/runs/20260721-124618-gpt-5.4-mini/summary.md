# Results — AI analytics harness
_Generated 2026-07-21. 740 runs (1 models x 1 rungs x 2 reliability-rungs x 37 questions x 10 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything). `deferred` = false-premise answers awaiting a judge; `err` = infra failures._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | deferred | other | err |
|---|---|---|---|---|---|---|
| R4 · +gate (enforced) | 238 | 4 | 104 | 3 | 6 | 15 |
| R5 · +fence (no raw SQL) | 242 | 8 | 102 | 6 | 6 | 6 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 601/740 (81%) |

## Accuracy by rung — mean ± sd across reps

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 81% ± 2 (78–85) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 80/80 |
| filtered | 99/100 |
| metric | 100/100 |
| knowledge | 87/100 |
| diagnostic | 91/100 |
| unanswerable | 100/120 |
| valid_but_wrong | 23/100 |
| false_premise | 21/40 |

## Refusal & fabrication — gpt-5.4-mini

_`over-refused` = answerable questions the system declined (the price of the gate/fence); `fabricated` = a number asserted for a question with no valid answer._

| rung·R | precision on answered | coverage | over-refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R4 | 238/247 | 247/284 | 35 | 1/68 | 48/59 | 10 | 15 | +281.0 |
| 6·R5 | 242/255 | 255/286 | 29 | 0/72 | 46/62 | 11 | 6 | +272.0 |

## Valid-but-wrong tier — gpt-5.4-mini  (the correctness ceiling structure can't reach)

| rung·R | ✅ right | ❌ wrong number | 🤷 over-refused |
|---|---|---|---|
| 6·R4 | 13 | 3 | 32 |
| 6·R5 | 10 | 8 | 30 |

## Wrong numbers (asserted a number that was wrong)

| model | rung·R | qid | answer | gold |
|---|---|---|---|---|
| gpt-5.4-mini | 6·R4 | u_pricing_cause | 0 | None |
| gpt-5.4-mini | 6·R4 | vw_total_users | 2100 | 2500.0 |
| gpt-5.4-mini | 6·R4 | vw_total_subscriptions | 0 | 457.0 |
| gpt-5.4-mini | 6·R4 | vw_total_users | 2100 | 2500.0 |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R5 | vw_total_subscriptions | 371 | 457.0 |
| gpt-5.4-mini | 6·R5 | vw_total_subscriptions | 371 | 457.0 |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R5 | vw_total_users | 2100 | 2500.0 |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R5 | t1_total_habits | 67132 | 7467.0 |
| gpt-5.4-mini | 6·R5 | vw_total_subscriptions | 371 | 457.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 6,206,902 / 100,973 | $1.75 |
