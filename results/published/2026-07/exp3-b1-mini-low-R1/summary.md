# Results — AI-analyst harness
_Generated 2026-07-26. 171 runs · 1 model(s) · 1 guardrail config(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **low** · verifier **gpt-5-mini**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._
_verifier vs independent gold: n=177 · agreement 95.5% · false-flag 5.0% · catch 97.4% (numeric questions only; gold_sql bypasses the semantic layer)._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| guardrail config | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R1 | 94% | 88% (73) | 12% | 90% | 171 |

## Reproducibility across reps — gpt-5-mini  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| guardrail config | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R1 | 88% / 83% / 92% | 88% ±4 | 93% / 90% / 87% | 90% ±3 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| guardrail config | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R1 | 90% | 89% | n/a (R7+) |

_answer-relevancy is **n/a** here: it reads the model's declared `source_metric`, which the answer tool only collects under the R7 single-metric guardrail. A grounding run doesn't produce it — relevancy comes online in the reliability ladder (R7+)._

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| guardrail config | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R1 | 64 | 34 | 70 | 1 | 2 | 0 | +29 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 14/39 | 19/21 | 2/6 | 9/15 | 9/15 | 9/9 | 15/15 | 5/12 | 12/18 | 3/21 |

## Wrong answers by question-type — gpt-5-mini  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 4 | · | · | 5 | 3 | · | · | 2 | 3 | 17 |

## Refusals by question-type — gpt-5-mini  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 20✓ | · | 5✓ | · | · | · | · | 8✓ | 14✓ | · |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| guardrail config | clarify | dimension_not_supported | false_premise | no_causal_evidence | no_governed_definition | other | out_of_coverage | result_empty | segment_undefined | ungoverned_dimension_value | wrong_grain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 0✓/18✗/5o | 0✓/2✗/0o | 2✓/2✗/0o | 7✓/0✗/0o | 8✓/3✗/0o | 0✓/1✗/0o | 8✓/0✗/0o | 0✓/2✗/0o | 3✓/0✗/0o | 5✓/1✗/0o | 0✓/3✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| guardrail config | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R1 | 9 | 8 | 17 | n/a |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| guardrail config | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R1 | 2.7 | list_metrics 0.92, query_metric 0.91, explain_change 0.29, get_schema 0.21, run_sql 0.19, get_metric_tree 0.14, describe_table 0.05 | — |

## Telemetry — gpt-5-mini

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| guardrail config | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R1 | 1,535,269 | 70,329 | 46% | $0.36 | 5.5 | 12.2 | 16.6 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5-mini | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R1 | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R1 | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R1 | adv_churned_behavior | adversarial | fabricated | Majority were inactive in their last week: 55.3% of churned users had zero completed habits in the 7 days before cancellation; 44.7% had ≥1. Among churners (n=76) median completed habits in final week = 0, mean = 100.45 (distribution heavily skewed). Of churners, average active days in final week = 1.05 for those with activity and overall; among those who opened reminders 31.6% had at least one reminder in that final week; 3.95% archived a habit in that week. | None |
| gpt-5-mini | R1 | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 | 86.85 |
| gpt-5-mini | R1 | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R1 | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R1 | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R1 | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R1 | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R1 | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 | 86.85 |
| gpt-5-mini | R1 | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R1 | adv_churned_behavior | adversarial | fabricated | Majority become inactive: 55% of churners (N=86) had zero habit completions in their final week before cancellation. Only ~27% showed a drop from the prior week — many churn without a clear gradual decline. Other signals: average active days rose from 1.02 (prior week) to 1.29 (final) driven by a small set of still-active churners; average reminders received also rose slightly (0.43 → 0.57). Habit creation/archival in final week is negligible. | None |
| gpt-5-mini | R1 | adv_dau_mau | adversarial | fabricated | 17.7% | None |
| gpt-5-mini | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R1 | adv_churned_behavior | adversarial | fabricated | Behavioral summary: In their final week before cancellation, most churned users stop completing habits — 55.26% had zero habit completions in the final 7 days. The mean completions is 35.01 (skewed by heavy tails), and 36.84% showed a drop in completions versus the prior week. They also received many reminders (avg 46.53 reminders in that final week). | None |
| gpt-5-mini | R1 | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R1 | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 | 86.85 |
| gpt-5-mini | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
