# Results — AI-analyst harness
_Generated 2026-07-26. 171 runs · 1 model(s) · 1 guardrail config(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **low** · verifier **gpt-5-mini**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._
_verifier vs independent gold: n=189 · agreement 93.7% · false-flag 5.0% · catch 90.0% (numeric questions only; gold_sql bypasses the semantic layer)._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| guardrail config | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R9 | 83% | 97% (65) | 3% | 100% | 171 |

## Reproducibility across reps — gpt-5-mini  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| guardrail config | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R9 | 100% / 96% / 95% | 97% ±3 | 100% / 100% / 100% | 100% ±0 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| guardrail config | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R9 | 100% | 100% | 100% |

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| guardrail config | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R9 | 63 | 1 | 105 | 0 | 2 | 0 | +122 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 23/39 | 20/21 | 0/6 | 12/15 | 8/15 | 9/9 | 11/15 | 8/12 | 15/18 | 16/21 |

## Wrong answers by question-type — gpt-5-mini  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | · | · | · | · | · | · | · | · | · | 1 |

## Refusals by question-type — gpt-5-mini  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 28✓ | · | 6✓ | 3✗ | 4✗ | · | 1✗ | 10✓ | 17✓ | 15✓ |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| guardrail config | clarify | dimension_not_supported | no_causal_evidence | no_governed_definition | out_of_coverage | segment_undefined | ungoverned_dimension_value | verifier_wrong_scope | verifier_wrong_segment | wrong_grain | wrong_measure |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 0✓/16✗/5o | 0✓/2✗/0o | 5✓/0✗/0o | 27✓/3✗/1o | 10✓/0✗/2o | 9✓/5✗/1o | 8✓/1✗/0o | 0✓/0✗/3o | 0✓/0✗/1o | 0✓/4✗/0o | 0✓/2✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| guardrail config | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R9 | 0 | 0 | 1 | 0 |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| guardrail config | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R9 | 2.0 | query_metric 0.85, list_metrics 0.47, explain_change 0.21, check_segment_defined 0.15, check_metric_exists 0.12, get_metric_tree 0.1, check_coverage 0.06, check_causal_evidence 0.04, describe_table 0.01 | 42/4 |

## Telemetry — gpt-5-mini

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| guardrail config | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R9 | 1,407,487 | 63,962 | 69% | $0.26 | 8.0 | 15.7 | 23.2 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5-mini | R9 | vw_total_users | valid_but_wrong | off_governance | We have 2,500 total user accounts (all-time). | 2500.0 |
