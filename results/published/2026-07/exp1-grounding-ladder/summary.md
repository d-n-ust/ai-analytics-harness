# Results — AI-analyst harness
_Generated 2026-07-26. 684 runs · 1 model(s) · 4 grounding rung(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **minimal** · verifier **gpt-5-mini**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| grounding rung | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R1 · messy data | 81% | 44% (63) | 56% | 59% | 171 |
| R2 · star schema | 88% | 45% (69) | 55% | 53% | 171 |
| R3 · semantic layer | 97% | 78% (76) | 22% | 65% | 171 |
| R7 · governed only — semantic layer + metric tree | 99% | 86% (77) | 14% | 69% | 171 |

## Reproducibility across reps — gpt-5-mini  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| grounding rung | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R1 · messy data | 38% / 50% / 45% | 44% ±6 | 55% / 66% / 55% | 59% ±6 |
| R2 · star schema | 44% / 36% / 55% | 45% ±9 | 57% / 48% / 55% | 53% ±4 |
| R3 · semantic layer | 85% / 72% / 76% | 78% ±6 | 67% / 63% / 66% | 65% ±2 |
| R7 · governed only — semantic layer + metric tree | 85% / 84% / 88% | 86% ±2 | 66% / 74% / 68% | 69% ±4 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| grounding rung | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R1 · messy data | 59% | 76% | n/a (R7+) |
| R2 · star schema | 53% | 70% | n/a (R7+) |
| R3 · semantic layer | 65% | 91% | n/a (R7+) |
| R7 · governed only — semantic layer + metric tree | 69% | 87% | n/a (R7+) |

_answer-relevancy is **n/a** here: it reads the model's declared `source_metric`, which the answer tool only collects under the R7 single-metric guardrail. A grounding run doesn't produce it — relevancy comes online in the reliability ladder (R7+)._

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| grounding rung | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R1 · messy data | 28 | 69 | 37 | 6 | 31 | 0 | -185 |
| R2 · star schema | 31 | 80 | 34 | 5 | 21 | 0 | -229 |
| R3 · semantic layer | 59 | 54 | 40 | 3 | 14 | 1 | -94 |
| R7 · governed only — semantic layer + metric tree | 66 | 53 | 37 | 4 | 9 | 2 | -85 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 · messy data | 3/39 | 6/21 | 0/6 | 5/15 | 0/15 | 7/9 | 7/15 | 1/12 | 3/18 | 3/21 |
| R2 · star schema | 2/39 | 5/21 | 1/6 | 12/15 | 3/15 | 7/9 | 2/15 | 0/12 | 5/18 | 2/21 |
| R3 · semantic layer | 6/39 | 9/21 | 1/6 | 12/15 | 12/15 | 8/9 | 15/15 | 0/12 | 4/18 | 3/21 |
| R7 · governed only — semantic layer + metric tree | 6/39 | 20/21 | 0/6 | 9/15 | 11/15 | 8/9 | 15/15 | 0/12 | 3/18 | 3/21 |

## Wrong answers by question-type — gpt-5-mini  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 · messy data | 24 | · | · | 5 | 3 | 2 | 5 | 5 | 7 | 18 |
| R2 · star schema | 27 | · | · | 3 | 6 | 2 | 10 | 7 | 7 | 18 |
| R3 · semantic layer | 14 | · | · | 3 | 3 | 1 | · | 7 | 10 | 16 |
| R7 · governed only — semantic layer + metric tree | 11 | · | · | 6 | 3 | 1 | · | 7 | 9 | 16 |

## Refusals by question-type — gpt-5-mini  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| grounding rung | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 · messy data | 10✓ | 1✗ | · | 4✗ | 2✗ | · | 1✗ | 5✓ | 7✓ | · |
| R2 · star schema | 8✓ | 3✗ | 1✓ | · | 1✗ | · | 1✗ | 5✓ | 9✓ | · |
| R3 · semantic layer | 19✓ | 2✗ | 3✓ | · | · | · | · | 5✓ | 6✓ | · |
| R7 · governed only — semantic layer + metric tree | 19✓ | · | 2✓ | · | 1✗ | · | · | 5✓ | 7✓ | · |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| grounding rung | clarify | dimension_not_supported | false_premise | implausible_value | no_causal_evidence | no_governed_definition | other | out_of_coverage | result_empty | segment_undefined | ungoverned_dimension_value | wrong_grain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 · messy data | 0✓/0✗/7o | 0✓/1✗/0o | 0✓/0✗/1o | · | 1✓/0✗/0o | 1✓/0✗/4o | 0✓/4✗/0o | 3✓/0✗/0o | 0✓/7✗/0o | 1✓/2✗/2o | 1✓/1✗/1o | · |
| R2 · star schema | 0✓/2✗/4o | · | 1✓/0✗/0o | 0✓/0✗/1o | 1✓/0✗/0o | 1✓/2✗/0o | 0✓/3✗/2o | 5✓/0✗/0o | 0✓/7✗/0o | 0✓/1✗/2o | 0✓/2✗/0o | · |
| R3 · semantic layer | 0✓/5✗/0o | 0✓/3✗/0o | 1✓/0✗/0o | · | 3✓/0✗/0o | 2✓/0✗/0o | 0✓/9✗/2o | 5✓/0✗/0o | 0✓/8✗/0o | 0✓/2✗/0o | · | · |
| R7 · governed only — semantic layer + metric tree | 0✓/3✗/0o | · | · | · | 2✓/0✗/0o | 2✓/1✗/0o | 0✓/8✗/1o | 5✓/2✗/0o | 0✓/10✗/0o | 0✓/2✗/0o | · | 0✓/1✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| grounding rung | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R1 · messy data | 36 | 19 | 14 | n/a |
| R2 · star schema | 41 | 26 | 13 | n/a |
| R3 · semantic layer | 31 | 10 | 13 | n/a |
| R7 · governed only — semantic layer + metric tree | 27 | 13 | 13 | n/a |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| grounding rung | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R1 · messy data | 4.92 | run_sql 2.5, describe_table 1.35, get_schema 1.07 | — |
| R2 · star schema | 3.77 | run_sql 1.81, get_schema 1.02, describe_table 0.94 | — |
| R3 · semantic layer | 4.48 | query_metric 2.48, list_metrics 1.23, run_sql 0.37, get_schema 0.23, describe_table 0.17 | — |
| R7 · governed only — semantic layer + metric tree | 4.19 | query_metric 1.63, list_metrics 1.12, run_sql 0.4, explain_change 0.37, get_metric_tree 0.3, get_schema 0.26, describe_table 0.12 | — |

## Telemetry — gpt-5-mini

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| grounding rung | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R1 · messy data | 1,376,595 | 100,984 | 6% | $0.53 | 8.2 | 15.2 | 23.6 |
| R2 · star schema | 1,099,697 | 84,807 | 3% | $0.44 | 6.7 | 13.4 | 18.2 |
| R3 · semantic layer | 2,390,722 | 62,207 | 18% | $0.62 | 7.9 | 10.7 | 12.7 |
| R7 · governed only — semantic layer + metric tree | 2,339,541 | 47,527 | 27% | $0.54 | 6.1 | 10.2 | 15.6 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5-mini | R1 · messy data | t2_referral_signups_q2 | filtered | confident_wrong | 165 | 243.0 |
| gpt-5-mini | R1 · messy data | t2_paid_search_spend_q2 | filtered | confident_wrong | 25442.33 | 36875.98 |
| gpt-5-mini | R1 · messy data | t4_real_acquisition_spend_june | knowledge | confident_wrong | 21,013.20 | 18267.17 |
| gpt-5-mini | R1 · messy data | t3_active_users_last_week | metric | confident_wrong | 919 | 886.0 |
| gpt-5-mini | R1 · messy data | t3_activation_rate_june | metric | confident_wrong | 74.3% | 0.5322 |
| gpt-5-mini | R1 · messy data | t1_ios_value_moments_june | lookup | confident_wrong | 16041 | 5648.0 |
| gpt-5-mini | R1 · messy data | adv_ltv_cac | adversarial | fabricated | 0.414 | None |
| gpt-5-mini | R1 · messy data | adv_trial_to_paid | adversarial | fabricated | 8.401976935749589% | None |
| gpt-5-mini | R1 · messy data | adv_dau_mau | adversarial | fabricated | DAU/MAU (stickiness) is currently ~23.36% for July-to-date (2026-07-01 to 2026-07-12).  For recent months (month start):
- 2026-07 (to 7/12): DAU/MAU = 0.2336 (avg DAU 315.8, MAU 1352)
- 2026-06: 0.1715 (avg DAU 288.6, MAU 1683)
- 2026-05: 0.1719 (avg DAU 215.9, MAU 1256)
- 2026-04: 0.1678 (avg DAU 164.9, MAU 983)
- 2026-03: 0.1709 (avg DAU 139.8, MAU 818)
- 2026-02: 0.1777 (avg DAU 109.1, MAU 614)

How I got it: I computed daily unique active users (DAU) per calendar day from events through 2026-07-12, computed monthly unique users (MAU) per calendar month, averaged daily DAU across each month and divided by that month’s MAU to produce the reported DAU/MAU (stickiness) per month. | None |
| gpt-5-mini | R1 · messy data | adv_yoy_june | adversarial | fabricated | 1683 vs 0 | None |
| gpt-5-mini | R1 · messy data | adv_free_vs_paying | adversarial | fabricated | Paying users: 42.9564 value moments per user; Free users: 23.6660 value moments per user | None |
| gpt-5-mini | R1 · messy data | adv_churn_premium | adversarial | fabricated | 7.06% monthly churn (June 2026) | None |
| gpt-5-mini | R1 · messy data | adv_whales | adversarial | fabricated | $1,192.99 MRR; $56.81 ARPU | None |
| gpt-5-mini | R1 · messy data | rt_north_america_actives | rt_phantom | fabricated | 206 | None |
| gpt-5-mini | R1 · messy data | adv_reminder_roi | adversarial | fabricated | $6,556.96 | None |
| gpt-5-mini | R1 · messy data | u_engagement_score | unanswerable | fabricated | Events per active user: 27.31 (events 45,973 ÷ active users 1,683) | None |
| gpt-5-mini | R1 · messy data | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R1 · messy data | u_apac_march | unanswerable | fabricated | 424 | None |
| gpt-5-mini | R1 · messy data | adv_churned_behavior | adversarial | fabricated | In the final week before cancelation, churned users (from subs with st=2) generated mostly completion/usage events: across 34 churned users with events in their last 7 days they produced 403 events total — 224 of type 1, 139 of type 2, and 40 of type 3. | None |
| gpt-5-mini | R1 · messy data | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 · messy data | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 · messy data | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 · messy data | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 · messy data | rt_arpu_annual | valid_but_wrong | off_governance | $86.85 per year | 86.85 |
| gpt-5-mini | R1 · messy data | rt_activation_count_june | valid_but_wrong | confident_wrong | 199 | 289.0 |
| gpt-5-mini | R1 · messy data | t2_web_value_moments_june | filtered | confident_wrong | 5364 | 4812.0 |
| gpt-5-mini | R1 · messy data | t4_real_signups_june | knowledge | confident_wrong | 519 | 453.0 |
| gpt-5-mini | R1 · messy data | t1_ios_value_moments_june | lookup | confident_wrong | 16209 | 5648.0 |
| gpt-5-mini | R1 · messy data | t3_active_users_last_week | metric | confident_wrong | 919 | 886.0 |
| gpt-5-mini | R1 · messy data | adv_ltv_cac | adversarial | fabricated | 0.00204 | None |
| gpt-5-mini | R1 · messy data | adv_dau_mau | adversarial | fabricated | DAU/MAU stickiness is roughly stable but not clearly deepening: In the last full week (week starting 2026-07-06) 36.24% of that week's MAU were active 3+ days that week, and 0.11% were active all 7 days. Over the prior 8 weeks the 3+ day stickiness ranged ~36%–52% and 7-day stickiness ranged ~0.1%–1.6% (weekly values shown below). | None |
| gpt-5-mini | R1 · messy data | adv_churned_behavior | adversarial | fabricated | Churned users typically show a spike in event type 1 (avg ~2.79 events) and moderate activity in type 2 (avg ~1.73) in their final 7 days; type 3 is low (~0.52) and other event types negligible. | None |
| gpt-5-mini | R1 · messy data | adv_reminder_roi | adversarial | fabricated | ~95% of revenue is from users who received reminders (10,898.25 of 11,448.08 total = 95.2%) | None |
| gpt-5-mini | R1 · messy data | adv_free_vs_paying | adversarial | fabricated | Paying users: mean=39.97 value moments/user, median=29
Free users:   mean=24.56 value moments/user, median=14 | None |
| gpt-5-mini | R1 · messy data | rt_north_america_actives | rt_phantom | fabricated | 249 | None |
| gpt-5-mini | R1 · messy data | u_engagement_score | unanswerable | fabricated | 27.3161 | None |
| gpt-5-mini | R1 · messy data | adv_price_lift | adversarial | fabricated | The March price bump did not lift MRR; MRR was lower than a counterfactual holding February's average price per active user.
Uplift by month (actual − counterfactual):
- Mar 2026: −$288.93
- Apr 2026: −$727.70
- May 2026: −$1,120.55
- Jun 2026: −$1,371.56
- Jul 2026: −$1,860.33

Method: computed monthly MRR and active users from subs, used Feb 2026 average price-per-user as the counterfactual price for months March–July, and reported actual minus counterfactual. | None |
| gpt-5-mini | R1 · messy data | u_churn_risk | unanswerable | fabricated | List of users with highest churn risk (internal = 1.0): uids [41,155,191,205,229,242,310,321,332,342,445,455,498,503,511,738,768,769,777,796] | None |
| gpt-5-mini | R1 · messy data | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 · messy data | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 · messy data | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 · messy data | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 · messy data | u_enterprise_users | unanswerable | fabricated | 555 | None |
| gpt-5-mini | R1 · messy data | t2_referral_signups_q2 | filtered | confident_wrong | 165 | 243.0 |
| gpt-5-mini | R1 · messy data | t2_paid_search_spend_q2 | filtered | confident_wrong | 29,063.04 | 36875.98 |
| gpt-5-mini | R1 · messy data | rt_arpu_annual | valid_but_wrong | confident_wrong | $14,422.02 per year per paying customer | 86.85 |
| gpt-5-mini | R1 · messy data | rt_activation_count_june | valid_but_wrong | off_governance | 284 | 289.0 |
| gpt-5-mini | R1 · messy data | t4_apac_value_moments_q2 | knowledge | confident_wrong | 6,966 | 3852.0 |
| gpt-5-mini | R1 · messy data | t3_active_users_last_week | metric | confident_wrong | 919 | 886.0 |
| gpt-5-mini | R1 · messy data | t3_arpu | metric | confident_wrong | $26.36 | 7.24 |
| gpt-5-mini | R1 · messy data | adv_ltv_cac | adversarial | fabricated | 0.4139 | None |
| gpt-5-mini | R1 · messy data | adv_yoy_june | adversarial | fabricated | June 2026: 1,683 active users; June 2025: 0 active users | None |
| gpt-5-mini | R1 · messy data | adv_trial_to_paid | adversarial | fabricated | 5.35% | None |
| gpt-5-mini | R1 · messy data | adv_free_vs_paying | adversarial | fabricated | Free users: 26.7674 value moments per user; Paying users: 26.5464 value moments per user | None |
| gpt-5-mini | R1 · messy data | adv_whales | adversarial | fabricated | Whale MRR: $1,684.70; Whale ARPU: $80.22 | None |
| gpt-5-mini | R1 · messy data | adv_reminder_roi | adversarial | fabricated | Reminders drove $28,044.80 in subscription revenue (subscriptions that started within 7 days after a reminder event). | None |
| gpt-5-mini | R1 · messy data | adv_churned_behavior | adversarial | fabricated | Churned users in their final week most commonly continued to use the app but with reduced breadth — they averaged about 2.26 active days in the 7 days before cancellation, with mean event counts: etype 1 ~6.15 events, etype 2 ~3.82, etype 3 ~1.15. All 39 churned users generated events from the app; many also used widgets (30) and API (22). In short: they still interact shortly before cancelling, primarily through the app, but activity is concentrated on a small number of days and event types rather than sustained daily engagement. | None |
| gpt-5-mini | R1 · messy data | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R1 · messy data | adv_dau_mau | adversarial | fabricated | Recent weekly DAU/MAU (avg daily active / weekly MAU) for the last 8 weeks (weeks starting Monday):
2026-05-18: 0.372
2026-05-25: 0.378
2026-06-01: 0.388
2026-06-08: 0.392
2026-06-15: 0.387
2026-06-22: 0.390
2026-06-29: 0.389
2026-07-06: 0.325 | None |
| gpt-5-mini | R1 · messy data | rt_north_america_actives | rt_phantom | fabricated | 249 | None |
| gpt-5-mini | R1 · messy data | adv_price_lift | adversarial | fabricated | The price bump did not lift MRR — MRR fell. Post-March average MRR (Apr–Jun 2026) was $13,156.14 vs Feb 2026 MRR $14,347.51, a change of -$1,191.37 (−8.30%). | None |
| gpt-5-mini | R1 · messy data | u_enterprise_users | unanswerable | fabricated | 413 | None |
| gpt-5-mini | R1 · messy data | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R1 · messy data | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R1 · messy data | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R1 · messy data | u_apac_march | unanswerable | fabricated | 97 | None |
| gpt-5-mini | R1 · messy data | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R1 · messy data | rt_arpu_annual | valid_but_wrong | confident_wrong | $96.03 | 86.85 |
| gpt-5-mini | R1 · messy data | rt_activation_count_june | valid_but_wrong | confident_wrong | 275 | 289.0 |
| gpt-5-mini | R2 · star schema | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R2 · star schema | t2_web_value_moments_june | filtered | confident_wrong | 0 | 4812.0 |
| gpt-5-mini | R2 · star schema | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R2 · star schema | t4_real_acquisition_spend_june | knowledge | confident_wrong | 19138.25 | 18267.17 |
| gpt-5-mini | R2 · star schema | t1_ios_value_moments_june | lookup | confident_wrong | 0 | 5648.0 |
| gpt-5-mini | R2 · star schema | t3_mrr | metric | confident_wrong | $11,448.08 | 2685.08 |
| gpt-5-mini | R2 · star schema | t3_active_users_last_week | metric | confident_wrong | 919 | 886.0 |
| gpt-5-mini | R2 · star schema | t3_activation_rate_june | metric | confident_wrong | 49.73% | 0.5322 |
| gpt-5-mini | R2 · star schema | adv_yoy_june | adversarial | fabricated | 1683 | None |
| gpt-5-mini | R2 · star schema | adv_dau_mau | adversarial | fabricated | DAU/MAU stickiness is ~15.6% on 2026-07-12, down from ~19.5% on 2026-06-15 — trending downward over the last 4 weeks. | None |
| gpt-5-mini | R2 · star schema | adv_free_vs_paying | adversarial | fabricated | Paying users: 40.10 value moments per user on average; Free users: 25.02 value moments per user on average. | None |
| gpt-5-mini | R2 · star schema | adv_whales | adversarial | fabricated | Whales (top 5% by total billed in last 12 months): count = 21; combined MRR = $127.7408; ARPU (average MRR per whale) = $6.0829 | None |
| gpt-5-mini | R2 · star schema | adv_ltv_cac | adversarial | fabricated | 0.41386246320112446 | None |
| gpt-5-mini | R2 · star schema | adv_reminder_roi | adversarial | fabricated | 95.2% | None |
| gpt-5-mini | R2 · star schema | adv_churn_premium | adversarial | fabricated | 6.06% | None |
| gpt-5-mini | R2 · star schema | adv_price_lift | adversarial | fabricated | $1,313.86 | None |
| gpt-5-mini | R2 · star schema | adv_churned_behavior | adversarial | fabricated | Churned users typically show very low engagement in their final week: on average they have value-moments on 1.10 of the 7 days (median = 0 days), average 9.08 value-moments that week, receive 8.26 reminders, and have 2.65 active habits. | None |
| gpt-5-mini | R2 · star schema | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R2 · star schema | u_engagement_score | unanswerable | fabricated | 9.531 | None |
| gpt-5-mini | R2 · star schema | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R2 · star schema | rt_north_america_actives | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R2 · star schema | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R2 · star schema | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R2 · star schema | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R2 · star schema | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R2 · star schema | t2_web_value_moments_june | filtered | confident_wrong | 0 | 4812.0 |
| gpt-5-mini | R2 · star schema | rt_arpu_annual | valid_but_wrong | confident_wrong | 34.92 | 86.85 |
| gpt-5-mini | R2 · star schema | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R2 · star schema | rt_activation_count_june | valid_but_wrong | confident_wrong | 279 | 289.0 |
| gpt-5-mini | R2 · star schema | t1_ios_value_moments_june | lookup | confident_wrong | 0 | 5648.0 |
| gpt-5-mini | R2 · star schema | t3_mrr | metric | confident_wrong | $11,448.08 | 2685.08 |
| gpt-5-mini | R2 · star schema | t3_arpu | metric | confident_wrong | $33.59 | 7.24 |
| gpt-5-mini | R2 · star schema | t3_activation_rate_june | metric | confident_wrong | 82.1363% | 0.5322 |
| gpt-5-mini | R2 · star schema | t3_active_users_last_week | metric | confident_wrong | 1134 | 886.0 |
| gpt-5-mini | R2 · star schema | adv_trial_to_paid | adversarial | fabricated | 8.4843% | None |
| gpt-5-mini | R2 · star schema | adv_yoy_june | adversarial | fabricated | June 2026: 1,683 active users; June 2025: 0 active users | None |
| gpt-5-mini | R2 · star schema | adv_ltv_cac | adversarial | fabricated | 0.3168531018267804 | None |
| gpt-5-mini | R2 · star schema | adv_free_vs_paying | adversarial | fabricated | Paying users (ever_paid = 1) average 41.47 value moments per user, across 371 paying users (total 14,846 value moments). Free users (ever_paid = 0) average 68.93 value moments per user, across 42 free users (total 2,895 value moments). Users with no subscription record (NULL) average 27.75 value moments per user, across 2,087 users (total 49,391 value moments). | None |
| gpt-5-mini | R2 · star schema | adv_price_lift | adversarial | fabricated | $302.27 | None |
| gpt-5-mini | R2 · star schema | adv_whales | adversarial | fabricated | Whales (top 5% by lifetime spend) MRR = $127.74; Whales ARPU = $6.72 | None |
| gpt-5-mini | R2 · star schema | adv_dau_mau | adversarial | fabricated | DAU/MAU (daily stickiness) is around 16–20% and has slightly declined in the most recent week. | None |
| gpt-5-mini | R2 · star schema | adv_churn_premium | adversarial | fabricated | 9.18% (for May 2026) | None |
| gpt-5-mini | R2 · star schema | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R2 · star schema | adv_reminder_roi | adversarial | fabricated | Reminders drive an incremental ~ $17,510 in annualized revenue (rough estimate of attributable revenue) — see explanation. | None |
| gpt-5-mini | R2 · star schema | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R2 · star schema | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R2 · star schema | u_enterprise_users | unanswerable | fabricated | 0 | None |
| gpt-5-mini | R2 · star schema | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R2 · star schema | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R2 · star schema | adv_churned_behavior | adversarial | fabricated | In the final 7 days before cancellation, churned users rarely record value moments: 55% (47 of 86) had zero recorded value moments in their final week; average value moments per user in that week = 1.73. About 45.3% had at least one value moment. 32.6% had at least one reminder during the week. Habit-archiving was rare (0.035 habits archived per user on average). | None |
| gpt-5-mini | R2 · star schema | rt_north_america_actives | rt_phantom | fabricated | 532 | None |
| gpt-5-mini | R2 · star schema | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R2 · star schema | rt_activation_count_june | valid_but_wrong | confident_wrong | 275 | 289.0 |
| gpt-5-mini | R2 · star schema | u_churn_risk | unanswerable | fabricated | I will provide the top users by churn risk score (computed from last 8 weeks of activity). | None |
| gpt-5-mini | R2 · star schema | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R2 · star schema | t4_real_acquisition_spend_june | knowledge | confident_wrong | 21013.20 | 18267.17 |
| gpt-5-mini | R2 · star schema | t3_mrr | metric | confident_wrong | 11448.08 | 2685.08 |
| gpt-5-mini | R2 · star schema | t4_real_signups_june | knowledge | confident_wrong | 329 | 453.0 |
| gpt-5-mini | R2 · star schema | t3_active_users_last_week | metric | confident_wrong | 919 | 886.0 |
| gpt-5-mini | R2 · star schema | t3_arpu | metric | confident_wrong | 33.60 | 7.24 |
| gpt-5-mini | R2 · star schema | rt_arpu_annual | valid_but_wrong | confident_wrong | $34.92 | 86.85 |
| gpt-5-mini | R2 · star schema | adv_ltv_cac | adversarial | fabricated | 0.3996 | None |
| gpt-5-mini | R2 · star schema | adv_dau_mau | adversarial | fabricated | DAU/MAU (daily active users divided by 30‑day MAU) is about 18–19% lately. | None |
| gpt-5-mini | R2 · star schema | adv_yoy_june | adversarial | fabricated | 1,683 active users in June 2026; 0 active users in June 2025 | None |
| gpt-5-mini | R2 · star schema | adv_churn_premium | adversarial | fabricated | June 2026: 9.02% churn (23 churned / 255 active at start) | None |
| gpt-5-mini | R2 · star schema | adv_free_vs_paying | adversarial | fabricated | Paying users: 40.02 value moments per user (avg), median 29
Free users: 24.56 value moments per user (avg), median 14 | None |
| gpt-5-mini | R2 · star schema | adv_churned_behavior | adversarial | fabricated | Churned users in their final week are mostly inactive: they average ~1.02 active days (median 0), ~3.24 value moments (median 0), used ~0.86 distinct habits, and received ~2.98 reminders. | None |
| gpt-5-mini | R2 · star schema | adv_whales | adversarial | fabricated | MRR for whales: $192.67 per month; ARPU (average revenue per whale) = $9.63 per month. | None |
| gpt-5-mini | R2 · star schema | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R2 · star schema | rt_north_america_actives | rt_phantom | fabricated | 189 | None |
| gpt-5-mini | R2 · star schema | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R2 · star schema | rt_paid_social_activation | rt_phantom | fabricated | 0% | None |
| gpt-5-mini | R2 · star schema | adv_reminder_roi | adversarial | fabricated | $20,125.36 | None |
| gpt-5-mini | R2 · star schema | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R2 · star schema | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R2 · star schema | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
| gpt-5-mini | R2 · star schema | u_churn_risk | unanswerable | fabricated | List of users with highest churn risk (score=100): user_ids [2,98,124,121,10,166,54,48,89,56,5,168,6,127,128,173,17,129,93,76,42,139,113,159,148,162,123,176,51,167,31,200,71,87,85,153,55,147,53,158,50,61,25,101,45,146,47,182,12,201] | None |
| gpt-5-mini | R2 · star schema | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R2 · star schema | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R2 · star schema | rt_arpu_annual | valid_but_wrong | confident_wrong | 33.62 | 86.85 |
| gpt-5-mini | R3 · semantic layer | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R3 · semantic layer | adv_ltv_cac | adversarial | fabricated | LTV:CAC = 0.0092 | None |
| gpt-5-mini | R3 · semantic layer | adv_dau_mau | adversarial | fabricated | DAU/MAU (weekly): 0.306 (30.6%) | None |
| gpt-5-mini | R3 · semantic layer | adv_whales | adversarial | fabricated | MRR and ARPU by plan — annual: MRR $796.64, ARPU $5.945; monthly: MRR $1,888.44, ARPU $7.968 | None |
| gpt-5-mini | R3 · semantic layer | adv_churned_behavior | adversarial | fabricated | Churned users in that week typically showed very low activity: on average they completed 0.75 habits in their final 7 days; 3 of 4 (75%) had zero habit completions in that final week. They received few reminders (avg 0.25 reminders; 1 of 4 saw any reminder), and no habits were archived in that week (0 archived). | None |
| gpt-5-mini | R3 · semantic layer | rt_north_america_actives | rt_phantom | fabricated | 504 active users | None |
| gpt-5-mini | R3 · semantic layer | adv_price_lift | adversarial | fabricated | $2,657.84 | None |
| gpt-5-mini | R3 · semantic layer | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R3 · semantic layer | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R3 · semantic layer | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R3 · semantic layer | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R3 · semantic layer | u_enterprise_users | unanswerable | fabricated | 0 | None |
| gpt-5-mini | R3 · semantic layer | vw_total_subscriptions | valid_but_wrong | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R3 · semantic layer | u_engagement_score | unanswerable | fabricated | 15329 | None |
| gpt-5-mini | R3 · semantic layer | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R3 · semantic layer | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R3 · semantic layer | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 USD | 86.85 |
| gpt-5-mini | R3 · semantic layer | vw_total_users | valid_but_wrong | confident_wrong | We need to know which definition you want: cumulative signups (total accounts ever) or total active users (users with ≥1 value moment). | 2500.0 |
| gpt-5-mini | R3 · semantic layer | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4239 | 3852.0 |
| gpt-5-mini | R3 · semantic layer | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R3 · semantic layer | t1_ios_value_moments_june | lookup | confident_wrong | 5374 | 5648.0 |
| gpt-5-mini | R3 · semantic layer | adv_ltv_cac | adversarial | fabricated | 0.128 | None |
| gpt-5-mini | R3 · semantic layer | adv_dau_mau | adversarial | fabricated | 0.36 (≈36%) for week of 2026-07-06 | None |
| gpt-5-mini | R3 · semantic layer | adv_churned_behavior | adversarial | fabricated | Most churned users were inactive in their final week: 3 of 4 (75%) had zero habit completions in the week before cancellation; average active days = 0.75 and average completions = 0.75. | None |
| gpt-5-mini | R3 · semantic layer | adv_whales | adversarial | fabricated | Top spenders (whales) defined as monthly-plan subscribers: MRR = 1,888.44; Paying users = 237; ARPU = 7.968101265822785. Annual-plan cohort: MRR = 796.6366666666664; Paying users = 134; ARPU = 5.945049751243779. | None |
| gpt-5-mini | R3 · semantic layer | adv_price_lift | adversarial | fabricated | $714.82 | None |
| gpt-5-mini | R3 · semantic layer | rt_north_america_actives | rt_phantom | fabricated | 504 | None |
| gpt-5-mini | R3 · semantic layer | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R3 · semantic layer | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R3 · semantic layer | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R3 · semantic layer | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R3 · semantic layer | rt_paid_social_activation | rt_phantom | fabricated | No activation rate available for paid_social in June 2026 | None |
| gpt-5-mini | R3 · semantic layer | u_engagement_score | unanswerable | fabricated | 15,329 real value moments (North Star) in June 2026 | None |
| gpt-5-mini | R3 · semantic layer | u_enterprise_users | unanswerable | fabricated | 0 | None |
| gpt-5-mini | R3 · semantic layer | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 USD per year | 86.85 |
| gpt-5-mini | R3 · semantic layer | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4239 | 3852.0 |
| gpt-5-mini | R3 · semantic layer | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R3 · semantic layer | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R3 · semantic layer | adv_ltv_cac | adversarial | fabricated | 0.13 | None |
| gpt-5-mini | R3 · semantic layer | adv_trial_to_paid | adversarial | fabricated | 0% | None |
| gpt-5-mini | R3 · semantic layer | adv_churned_behavior | adversarial | fabricated | Churned users typically do very little: in the final ISO week (2026-07-06 — 2026-07-12) of available data, 4 users churned; they averaged 1.0 habit completion and 0.75 active days in that week, and 2 of the 4 had zero activity that week. | None |
| gpt-5-mini | R3 · semantic layer | adv_whales | adversarial | fabricated | MRR and ARPU for top-spend (whale) accounts by plan: 
- Monthly-plan whales: MRR = $1,888.44; Paying users = 237; ARPU = $7.9681
- Annual-plan whales: MRR = $796.64; Paying users = 134; ARPU = $5.9450 | None |
| gpt-5-mini | R3 · semantic layer | rt_north_america_actives | rt_phantom | fabricated | 504 | None |
| gpt-5-mini | R3 · semantic layer | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R3 · semantic layer | rt_mexico_signups | rt_phantom | fabricated | 0 signups from Mexico in Q2 2026 | None |
| gpt-5-mini | R3 · semantic layer | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R3 · semantic layer | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R3 · semantic layer | u_engagement_score | unanswerable | fabricated | 16,041 value moments in June 2026 | None |
| gpt-5-mini | R3 · semantic layer | vw_total_subscriptions | valid_but_wrong | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R3 · semantic layer | u_enterprise_users | unanswerable | fabricated | 0 enterprise users (active subscriptions) | None |
| gpt-5-mini | R3 · semantic layer | rt_arpu_annual | valid_but_wrong | off_governance | $7.24 per month → $86.85 per year | 86.85 |
| gpt-5-mini | R3 · semantic layer | u_churn_risk | unanswerable | fabricated | Top users by churn risk score (top 20): [1735, 626, 2473, 1686, 654, 1323, 1230, 31, 182, 1524, 1334, 2462, 1039, 2028, 864, 166, 418, 1597, 55, 204] | None |
| gpt-5-mini | R3 · semantic layer | vw_total_users | valid_but_wrong | off_governance | There are 2,500 total signed-up user accounts (all-time) and 2,100 distinct active users (all-time with ≥1 value moment). | 2500.0 |
| gpt-5-mini | R3 · semantic layer | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4355 | 3852.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t1_ios_value_moments_june | lookup | confident_wrong | 5374 | 5648.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_ltv_cac | adversarial | fabricated | 0.128 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_dau_mau | adversarial | fabricated | DAU/MAU (stickiness) is ~0.095 for last week | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_last_week_oob | adversarial | fabricated | No data for July 13–19, 2026 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_free_vs_paying | adversarial | fabricated | Free users: 9.79 value moments per user in last week; Paying users: 9.81 value moments per user (last week). | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_north_america_actives | rt_phantom | fabricated | 504 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_ipados_open_rate | rt_phantom | fabricated | iOS reminder open rate is higher than iPadOS over the last 30 days: iOS = 0.403 (40.3%), iPadOS = 0.292 (29.2%); difference = 0.111 pp (11.1 percentage points) | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_mexico_signups | rt_phantom | fabricated | 0 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_engagement_score | unanswerable | fabricated | 15329 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_apac_march | unanswerable | fabricated | 455 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_total_users | valid_but_wrong | off_governance | 2500 | 2500.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_enterprise_users | unanswerable | fabricated | 0 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_arpu_annual | valid_but_wrong | off_governance | $7.24 per month ≈ $86.85 per year | 86.85 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_referral_signups_q2 | filtered | confident_wrong | 1166 | 243.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4239 | 3852.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_total_subscriptions | valid_but_wrong | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_free_vs_paying | adversarial | fabricated | Paying users: 4.25 value moments per user; Free users: 4.09 value moments per user (week 2026-07-06 to 2026-07-12). | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_north_america_actives | rt_phantom | fabricated | 504 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_churned_behavior | adversarial | fabricated | Churned users are mixed: many stop doing any habits in their final week but a substantial share remain highly active. In our data (76 canceled subscriptions with ended_date): 42 users (55%) recorded zero habit completions in the 7 days up to cancellation; the median completions in that final week is 0 and the mean is 35.0 (driven by a small number of very active users). Average reminders seen in the final week was 46.5; none of these churned users had never completed a habit earlier (0 never-completed). | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_ipados_open_rate | rt_phantom | fabricated | iOS: 42.5% vs iPadOS: data not present | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_engagement_score | unanswerable | fabricated | 16041 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_total_users | valid_but_wrong | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_enterprise_users | unanswerable | fabricated | 371 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_americas_value_moments_june | filtered | confident_wrong | 5133 | 5386.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_arpu_annual | valid_but_wrong | off_governance | 86.85 | 86.85 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_activation_count_june | valid_but_wrong | confident_wrong | 240 | 289.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t4_apac_value_moments_q2 | knowledge | confident_wrong | 4,355 | 3852.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t2_referral_signups_q2 | filtered | confident_wrong | 234 | 243.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_yoy_june | adversarial | fabricated | 1620 vs 0 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_free_vs_paying | adversarial | fabricated | Paying users: 4.21 value moments per user; Free users: 4.09 value moments per user. | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_ltv_cac | adversarial | fabricated | LTV-to-CAC = 0.32 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_dau_mau | adversarial | fabricated | DAU/MAU stickiness (DAU divided by MAU) for last full week (2026-07-06 — 2026-07-12) is 0.546 (54.6%). | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | adv_whales | adversarial | fabricated | MRR: $2,685.08 total; ARPU: $7.24 per paying user | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_north_america_actives | rt_phantom | fabricated | 504 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_apac_march | unanswerable | fabricated | 472 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_engagement_score | unanswerable | fabricated | 16041 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_ipados_open_rate | rt_phantom | fabricated | iPadOS vs iOS reminder open rate (last 30 days) | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | u_enterprise_users | unanswerable | fabricated | 0 | None |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_arr | valid_but_wrong | off_governance | 32220.92 | 32220.92 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | t1_total_habits | valid_but_wrong | off_governance | 7467 | 7467.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_arpu_annual | valid_but_wrong | off_governance | $7.24 per month → $86.85 per year | 86.85 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | rt_activation_count_june | valid_but_wrong | off_governance | 289 | 289.0 |
| gpt-5-mini | R7 · governed only — semantic layer + metric tree | vw_total_subscriptions | valid_but_wrong | off_governance | 457 | 457.0 |
