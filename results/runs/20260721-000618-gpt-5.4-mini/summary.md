# Results — AI analytics harness
_Generated 2026-07-21. 31 runs (1 models x 1 rungs x 31 questions x 1 reps)._

## Response mix — gpt-5.4-mini  (right / wrong / I-don't-know)

_Every response to every question, bucketed. Lower **wrong** is the goal; **right** should hold steady (proof it isn't just refusing everything)._

| round | ✅ right number | ❌ wrong number | 🤷 I don't know | other |
|---|---|---|---|---|
| R5 · +fence (no raw SQL) | 22 | 0 | 8 | 1 |

## Accuracy by rung (pooled over reps)

| rung | gpt-5.4-mini |
|---|---|
| 6 · + metric tree | 27/31 (87%) |

## Question-type unlock — gpt-5.4-mini (correct-rate by tier x rung)

| tier | r6 |
|---|---|
| lookup | 4/5 |
| filtered | 5/5 |
| metric | 5/5 |
| knowledge | 4/5 |
| diagnostic | 4/5 |
| unanswerable | 5/6 |

## Refusal & fabrication — gpt-5.4-mini

| rung·R | precision on answered | coverage | refused (answerable) | fabricated (unanswerable) | refused w/ right reason | clarified | errors | total score |
|---|---|---|---|---|---|---|---|---|
| 6·R5 | 22/22 | 22/24 | 2 | 0/6 | 4/5 | 1 | 1 | +27.0 |

## Confidently wrong (a number, not an abstention, but wrong)

| model | rung | qid | answer | gold |
|---|---|---|---|---|

## Cost

| model | total tokens (in/out) | est. USD |
|---|---|---|
| gpt-5.4-mini | 253,951 / 3,998 | $0.07 |
