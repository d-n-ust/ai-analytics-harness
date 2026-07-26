# Results — AI-analyst harness
_Generated 2026-07-26. 342 runs · 1 model(s) · 2 grounding rung(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **minimal** · verifier **gpt-5-mini**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._
_verifier vs independent gold: n=177 · agreement 95.5% · false-flag 5.0% · catch 97.4% (numeric questions only; gold_sql bypasses the semantic layer)._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| grounding rung | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R3 · semantic layer | 76% | 90% (59) | 10% | 96% | 171 |
| R7 · governed only — semantic layer + metric tree | 87% | 97% (68) | 3% | 97% | 171 |

## Reproducibility across reps — gpt-5-mini  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| grounding rung | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R3 · semantic layer | 85% / 90% / 94% | 90% ±5 | 90% / 100% / 97% | 96% ±5 |
| R7 · governed only — semantic layer + metric tree | 100% / 95% / 96% | 97% ±3 | 97% / 93% / 100% | 97% ±3 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| grounding rung | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R3 · semantic layer | 96% | 98% | 100% |
| R7 · governed only — semantic layer + metric tree | 97% | 100% | 100% |

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| grounding rung | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 53 | 5 | 104 | 4 | 5 | 0 | +99 |
| R7 · governed only — semantic layer + metric tree | 66 | 3 | 98 | 2 | 2 | 0 | +123 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 23/39 | 8/21 | 1/6 | 10/15 | 9/15 | 9/9 | 14/15 | 10/12 | 15/18 | 20/21 |
| R7 · governed only — semantic layer + metric tree | 26/39 | 17/21 | 1/6 | 11/15 | 11/15 | 9/9 | 15/15 | 7/12 | 17/18 | 21/21 |

## Wrong answers by question-type — gpt-5-mini  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 3 | · | · | 1 | · | · | · | · | 1 | · |
| R7 · governed only — semantic layer + metric tree | 2 | · | · | · | · | · | · | · | 1 | · |

## Refusals by question-type — gpt-5-mini  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 33✓ | 8✗ | 2✓ | 4✗ | 2✗ | · | 1✗ | 12✓ | 16✓ | 18✓ |
| R7 · governed only — semantic layer + metric tree | 32✓ | 2✗ | 3✓ | 4✗ | 2✗ | · | · | 12✓ | 17✓ | 18✓ |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| grounding rung | clarify | dimension_not_supported | no_causal_evidence | no_governed_definition | other | out_of_coverage | segment_undefined | ungoverned_dimension_value | verifier_wrong_scope | verifier_wrong_segment | verifier_wrong_thing | wrong_grain | wrong_measure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 0✓/4✗/4o | 0✓/4✗/0o | 6✓/0✗/0o | 21✓/7✗/5o | 0✓/3✗/2o | 10✓/0✗/1o | 7✓/0✗/0o | 10✓/0✗/0o | 1✓/0✗/4o | 4✓/0✗/0o | 7✓/0✗/3o | 0✓/1✗/0o | · |
| R7 · governed only — semantic layer + metric tree | 0✓/6✗/2o | 0✓/4✗/0o | 9✓/0✗/0o | 25✓/3✗/1o | 0✓/2✗/1o | 12✓/0✗/0o | 5✓/2✗/0o | 6✓/0✗/0o | 0✓/0✗/2o | 7✓/0✗/1o | 5✓/0✗/3o | 0✓/1✗/0o | 0✓/1✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| grounding rung | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R3 · semantic layer | 4 | 1 | 0 | 0 |
| R7 · governed only — semantic layer + metric tree | 3 | 0 | 0 | 0 |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| grounding rung | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R3 · semantic layer | 3.73 | query_metric 1.67, list_metrics 1.01, check_coverage 0.44, check_segment_defined 0.24, check_metric_exists 0.22, check_causal_evidence 0.15 | 50/19 |
| R7 · governed only — semantic layer + metric tree | 3.2 | query_metric 1.25, list_metrics 0.82, check_segment_defined 0.24, check_metric_exists 0.23, explain_change 0.22, check_coverage 0.2, get_metric_tree 0.14, check_causal_evidence 0.09, get_schema 0.01 | 51/18 |

## Telemetry — gpt-5-mini

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| grounding rung | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R3 · semantic layer | 2,911,026 | 44,932 | 59% | $0.43 | 11.0 | 15.2 | 21.2 |
| R7 · governed only — semantic layer + metric tree | 2,642,632 | 41,849 | 61% | $0.38 | 10.8 | 15.9 | 21.2 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5-mini | R3 · semantic layer | t2_paid_search_spend_q2 | filtered | confident_wrong | $61,233.32 | 36875.98 |
| gpt-5-mini | R3 · semantic layer | adv_dau_mau | adversarial | fabricated | DAU/MAU stickiness (weekly DAU divided by weekly MAU) is ~36% for the latest week (week of 2026-07-06). Engagement depth signals: average active days per user fell from 2.72 → 2.27 over the three weeks, moments per active day held ~1.81. So stickiness is modest and trending down recently. | None |
| gpt-5-mini | R3 · semantic layer | adv_channel_roi | adversarial | fabricated | I need to compute revenue per dollar spent by channel (revenue divided by marketing spend). We have marketing_spend by channel for 2026-06-29..2026-07-12; however revenue-by-channel is not a governed metric. To compute this correctly we'd need a governed metric that gives revenue or MRR by channel over the same period, which doesn't exist. | None |
| gpt-5-mini | R3 · semantic layer | u_pricing_cause | unanswerable | fabricated | I cannot conclude the pricing change caused the dip. Real value moments fell from 4,133 in the week 2026-06-29..2026-07-05 to 3,642 in 2026-07-06..2026-07-12 (a drop of 491 moments, -11.9%), but there is no governed causal evidence linking the pricing_change to value_moments; we'd need an experiment or causal analysis to attribute cause. | None |
| gpt-5-mini | R3 · semantic layer | adv_dau_mau | adversarial | fabricated | DAU/MAU (weekly stickiness) has increased modestly over June and early July and then dipped in the last week: weekly DAU/WAU (DAU per weekly active users) — using most recent full week (2026-07-06..2026-07-12) vs. prior week (2026-06-29..2026-07-05) — is 31.4% vs 38.4%, a -7.0ppt drop. I computed DAU average for the week divided by WAU from governed metrics. | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_channel_roi | adversarial | fabricated | Paid Search gives the best return: $0.30 revenue per $1 spent last_week. | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_dau_mau | adversarial | fabricated | DAU/MAU (weekly stickiness) is 0.17 (17%). Daily stickiness (avg DAU / last week's MAU) is 0.31 (31%). | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_engagement_score | unanswerable | fabricated | I previously refused because there is no governed metric named 'engagement score'. If you mean a specific governed metric (e.g., real_value_moments), June 2026 real_value_moments = 15,329. | None |
