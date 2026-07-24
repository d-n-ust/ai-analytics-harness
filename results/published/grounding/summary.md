# Results — AI analytics harness

_1500 runs: 2 models (gpt = GPT-5.6, mini = GPT-5.4-mini) x 6 rungs x 25 questions x 5 reps._
_The aggregates below are the committed record; regenerate the raw per-run rows with `make eval`._

## Accuracy by rung (pooled over reps)

| rung | gpt | mini |
|---|---|---|
| 1 · messy data | 50/125 (40%) | 27/125 (22%) |
| 2 · star schema | 57/125 (46%) | 43/125 (34%) |
| 3 · semantic layer | 82/125 (66%) | 67/125 (54%) |
| 4 · + verified examples | 101/125 (81%) | 96/125 (77%) |
| 5 · + knowledge base | 98/125 (78%) | 94/125 (75%) |
| 6 · + metric tree | 115/125 (92%) | 98/125 (78%) |

## Accuracy by rung — mean ± sd across reps

| rung | gpt | mini |
|---|---|---|
| 1 · messy data | 40% ± 6 (32–48) | 22% ± 2 (20–24) |
| 2 · star schema | 46% ± 4 (40–48) | 34% ± 4 (32–40) |
| 3 · semantic layer | 66% ± 4 (60–68) | 54% ± 7 (44–60) |
| 4 · + verified examples | 81% ± 2 (80–84) | 77% ± 4 (72–84) |
| 5 · + knowledge base | 78% ± 2 (76–80) | 75% ± 3 (72–80) |
| 6 · + metric tree | 92% ± 3 (88–96) | 78% ± 5 (72–84) |

## Question-type unlock — gpt (correct-rate by tier x rung)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 24/25 | 20/25 | 25/25 | 25/25 | 25/25 | 25/25 |
| filtered | 14/25 | 19/25 | 25/25 | 25/25 | 25/25 | 25/25 |
| metric | 10/25 | 18/25 | 25/25 | 25/25 | 25/25 | 25/25 |
| knowledge | 2/25 | 0/25 | 4/25 | 25/25 | 23/25 | 22/25 |
| diagnostic | 0/25 | 0/25 | 3/25 | 1/25 | 0/25 | 18/25 |

## Question-type unlock — mini (correct-rate by tier x rung)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 19/25 | 20/25 | 19/25 | 23/25 | 21/25 | 20/25 |
| filtered | 7/25 | 20/25 | 19/25 | 25/25 | 25/25 | 25/25 |
| metric | 1/25 | 2/25 | 19/25 | 25/25 | 25/25 | 25/25 |
| knowledge | 0/25 | 1/25 | 7/25 | 20/25 | 22/25 | 20/25 |
| diagnostic | 0/25 | 0/25 | 3/25 | 3/25 | 1/25 | 8/25 |

## Confidently wrong (a number, not an abstention, but wrong)

A representative sample; regenerate the full list with `make eval`.

| model | rung | qid | answer | gold |
|---|---|---|---|---|
| gpt | 1 | t3_active_users_last_week | 919 | 886.0 |
| gpt | 1 | t3_activation_rate_june | 76.85% | 0.5322 |
| gpt | 1 | t2_paid_search_spend_q2 | 27166.93 | 36875.98 |
| gpt | 1 | t4_apac_value_moments_q2 | 4355 | 3852.0 |
| gpt | 2 | t3_activation_rate_june | 100.0% | 0.5322 |
| gpt | 2 | t3_power_users | 184 | 151.0 |
| mini | 1 | t3_mrr | 11448.08 | 2685.08 |
| mini | 1 | t3_activation_rate_june | 76.85% | 0.5322 |
| mini | 1 | t1_ios_value_moments_june | 16209 | 5648.0 |
| mini | 1 | t4_real_acquisition_spend_june | 21013.20 | 18267.17 |
| mini | 3 | t1_spend_june | 210940.52 | 21013.2 |
| mini | 6 | t1_total_habits | 2500 | 7467.0 |

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt | 3,442,227 / 190,312 | $6.21 |
| mini | 4,095,728 / 191,791 | $1.41 |
