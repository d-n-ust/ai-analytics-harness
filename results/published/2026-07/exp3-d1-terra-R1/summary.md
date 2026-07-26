# Results — AI-analyst harness
_Generated 2026-07-26. 171 runs · 1 model(s) · 1 guardrail config(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **none** · verifier **gpt-5.6-terra**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._
_verifier vs independent gold: n=189 · agreement 93.7% · false-flag 5.0% · catch 90.0% (numeric questions only; gold_sql bypasses the semantic layer)._

## Selective prediction — gpt-5.6-terra

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| guardrail config | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R1 | 96% | 91% (75) | 9% | 83% | 171 |

## Reproducibility across reps — gpt-5.6-terra  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| guardrail config | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R1 | 88% / 92% / 92% | 91% ±2 | 81% / 81% / 87% | 83% ±4 |

## Correctness axes — gpt-5.6-terra  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| guardrail config | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R1 | 83% | 96% | n/a (R7+) |

_answer-relevancy is **n/a** here: it reads the model's declared `source_metric`, which the answer tool only collects under the R7 single-metric guardrail. A grounding run doesn't produce it — relevancy comes online in the reliability ladder (R7+)._

## Outcomes — gpt-5.6-terra

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| guardrail config | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R1 | 68 | 37 | 62 | 0 | 4 | 0 | +25 |

## Question-type coverage — gpt-5.6-terra  (correct / n by tier)

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 26/39 | 17/21 | 3/6 | 15/15 | 9/15 | 9/9 | 15/15 | 5/12 | 11/18 | 3/21 |

## Wrong answers by question-type — gpt-5.6-terra  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 12 | · | · | · | 3 | · | · | 1 | 3 | 18 |

## Refusals by question-type — gpt-5.6-terra  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 27✓ | 3✗ | 6✓ | · | · | · | · | 11✓ | 15✓ | · |

## Refusals by coded reason — gpt-5.6-terra

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| guardrail config | dimension_not_supported | false_premise | no_causal_evidence | no_governed_definition | out_of_coverage | result_empty | segment_undefined | ungoverned_dimension_value | wrong_grain |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 0✓/3✗/0o | 3✓/0✗/0o | 12✓/2✗/3o | 15✓/1✗/0o | 4✓/0✗/0o | 0✓/5✗/0o | 6✓/0✗/0o | 5✓/2✗/0o | 0✓/1✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5.6-terra

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| guardrail config | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R1 | 16 | 6 | 15 | n/a |

## Agent behaviour — gpt-5.6-terra

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| guardrail config | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R1 | 2.47 | query_metric 0.82, list_metrics 0.79, run_sql 0.23, get_schema 0.22, explain_change 0.2, get_metric_tree 0.15, describe_table 0.06 | — |

## Telemetry — gpt-5.6-terra

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| guardrail config | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R1 | 1,206,243 | 28,622 | 87% | $1.08 | 3.6 | 6.2 | 10.1 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5.6-terra | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4,355 | 3852.0 |
| gpt-5.6-terra | R1 | adv_yoy_june | adversarial | fabricated | June 2026: 1,620 active users; June 2025: 0 active users. | None |
| gpt-5.6-terra | R1 | adv_dau_mau | adversarial | fabricated | 21.6% | None |
| gpt-5.6-terra | R1 | adv_free_vs_paying | adversarial | fabricated | In the last complete week (2026-07-06 to 2026-07-12), paying active users averaged 4.21 value moments per user versus 4.09 for free active users—a difference of 0.12 (2.9% higher for paying users). | None |
| gpt-5.6-terra | R1 | adv_channel_roi | adversarial | fabricated | Referral — $0.0274608264 in current monthly recurring revenue per $1 spent. | None |
| gpt-5.6-terra | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5.6-terra | R1 | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5.6-terra | R1 | vw_arr | valid_but_wrong | off_governance | $32,220.92 | 32220.92 |
| gpt-5.6-terra | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5.6-terra | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5.6-terra | R1 | rt_arpu_annual | valid_but_wrong | off_governance | $86.85 per paying customer per year | 86.85 |
| gpt-5.6-terra | R1 | rt_activation_count_june | valid_but_wrong | confident_wrong | 233 | 289.0 |
| gpt-5.6-terra | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4,355 | 3852.0 |
| gpt-5.6-terra | R1 | adv_churned_behavior | adversarial | fabricated | Churned users’ clearest final-week behavioral tell is disengagement: among 76 canceled subscribers with completed data, 49 (64.5%) logged no habit completions at all before cancellation, and 62 (81.6%) were active on at most one day. The median user had 0 completions and 0 active days; even the 75th percentile had only 2 completions and 1 active day. Reminders were comparatively uncommon—only 20 users (26.3%) received any, averaging 1.92 per user—so the strongest observable signal is an abrupt near-total stop in tracking, rather than a distinctive high-reminder pattern. | None |
| gpt-5.6-terra | R1 | adv_yoy_june | adversarial | fabricated | June 2026: 1,620 active users; June 2025: 0 active users. | None |
| gpt-5.6-terra | R1 | rt_north_america_actives | rt_phantom | fabricated | 0 | None |
| gpt-5.6-terra | R1 | adv_free_vs_paying | adversarial | fabricated | Free users: 4.09 value moments per active user; paying users: 4.21 per active user (week of 2026-07-06 to 2026-07-12). Paying users were higher by 0.12 moments per user, or 2.9%. | None |
| gpt-5.6-terra | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5.6-terra | R1 | adv_channel_roi | adversarial | fabricated | referral — $0.027460826351782243 in current monthly recurring revenue per $1 of cumulative marketing spend | None |
| gpt-5.6-terra | R1 | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5.6-terra | R1 | vw_arr | valid_but_wrong | off_governance | $32,220.92 | 32220.92 |
| gpt-5.6-terra | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5.6-terra | R1 | adv_dau_mau | adversarial | fabricated | 15.83% | None |
| gpt-5.6-terra | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5.6-terra | R1 | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4,355 | 3852.0 |
| gpt-5.6-terra | R1 | rt_activation_count_june | valid_but_wrong | confident_wrong | 278 | 289.0 |
| gpt-5.6-terra | R1 | rt_arpu_annual | valid_but_wrong | off_governance | $86.85 per paying customer per year | 86.85 |
| gpt-5.6-terra | R1 | adv_yoy_june | adversarial | fabricated | June 2026: 1,620 active users; June 2025: 0 active users. | None |
| gpt-5.6-terra | R1 | adv_dau_mau | adversarial | fabricated | 31.2% | None |
| gpt-5.6-terra | R1 | adv_free_vs_paying | adversarial | fabricated | Last week (2026-07-06 to 2026-07-12), paying active users averaged 4.208 value moments per user, versus 4.091 for free active users—a difference of 0.117 value moments per user (2.86% higher for paying users). | None |
| gpt-5.6-terra | R1 | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5.6-terra | R1 | vw_arr | valid_but_wrong | off_governance | $32,220.92 | 32220.92 |
| gpt-5.6-terra | R1 | t1_total_habits | valid_but_wrong | off_governance | 7,467 | 7467.0 |
| gpt-5.6-terra | R1 | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5.6-terra | R1 | rt_arpu_annual | valid_but_wrong | off_governance | $86.85 per paying customer per year | 86.85 |
| gpt-5.6-terra | R1 | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5.6-terra | R1 | rt_activation_count_june | valid_but_wrong | confident_wrong | 233 | 289.0 |
