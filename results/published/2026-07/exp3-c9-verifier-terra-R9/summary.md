# Results — AI-analyst harness
_Generated 2026-07-26. 171 runs · 1 model(s) · 1 guardrail config(s) · 57 questions · 3 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._
_treatment: main reasoning **minimal** · verifier **gpt-5.6-terra**@low · row schema v14._
_verifier validated: n=37 · miss-rate 0.059 · false-flag 0.1 (audit 2026-07-25) ⚠ INVALIDATED — 7 of the 37 cases were judged on the wrong number — _provenance handed the judge a breakdown's FIRST row instead of the row the answer served (e.g. V027/V029 t2_paid_search_spend_q2: judge shown 10643.22, answer served 36875.98). The blind sheet carried the same wrong `query_result`, so the human labels were formed against it too. Both sides of the comparison used corrupted evidence, so the 92% agreement / 6% miss / 10% false-flag rates below do not describe the judge as it now runs.; re-draw and re-label._
_verifier vs independent gold: n=189 · agreement 93.7% · false-flag 5.0% · catch 90.0% (numeric questions only; gold_sql bypasses the semantic layer)._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| guardrail config | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| R9 | 87% | 99% (68) | 1% | 97% | 171 |

## Reproducibility across reps — gpt-5-mini  (3 reps)

_Precision and grounded measured **separately per rep**, then mean ±sample-std. If two rungs' means sit within each other's ±band, the step between them is inside the noise._

| guardrail config | precision / rep | mean ±sd | grounded / rep | mean ±sd |
|---|---|---|---|---|
| R9 | 95% / 100% / 100% | 98% ±3 | 97% / 97% / 97% | 97% ±0 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| guardrail config | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| R9 | 97% | 100% | 100% |

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| guardrail config | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| R9 | 67 | 3 | 96 | 1 | 4 | 0 | +125 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 25/39 | 20/21 | 0/6 | 10/15 | 10/15 | 9/9 | 15/15 | 10/12 | 17/18 | 21/21 |

## Wrong answers by question-type — gpt-5-mini  (wrong count by tier)

_Which KINDS of question produced a wrong answer at each rung (· = none). Read with the failure-mode table below (fabricated / confident-wrong / off-governance) for the how._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 3 | · | · | · | · | · | · | · | · | · |

## Refusals by question-type — gpt-5-mini  (✓ refused a trap / ✗ over-refused an answerable)

_The refusal split by question kind: ✓ = correctly refused an unanswerable/trap; ✗ = over-refused a question that had an answer (lost coverage). · = no refusals._

| guardrail config | adversarial | diagnostic | false_premise | filtered | knowledge | lookup | metric | rt_phantom | unanswerable | valid_but_wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 32✓ | · | 5✓ | 5✗ | 3✗ | · | · | 12✓ | 17✓ | 18✓ |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| guardrail config | clarify | dimension_not_supported | no_causal_evidence | no_governed_definition | other | out_of_coverage | result_empty | segment_undefined | ungoverned_dimension_value | verifier_wrong_definition | verifier_wrong_scope | verifier_wrong_segment | verifier_wrong_thing |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R9 | 0✓/2✗/2o | 0✓/3✗/1o | 6✓/1✗/0o | 26✓/7✗/0o | 0✓/2✗/0o | 11✓/0✗/1o | 0✓/1✗/0o | 7✓/0✗/0o | 10✓/0✗/0o | 1✓/0✗/0o | 0✓/0✗/5o | 5✓/0✗/0o | 4✓/0✗/1o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

_The first three columns **partition** every wrong answer — they sum to ❌ wrong. **fabricated** = invented a number where none exists (groundedness); **confident-wrong** = asserted a wrong number (correctness); **off-governance** = right digits reached off the governed path when the answer was to refuse. **wrong-metric** is a *subset* of confident-wrong (a relevancy miss), scored only where the model declares source_metric (R7+)._

| guardrail config | fabricated | confident-wrong | off-governance | of which wrong-metric |
|---|---|---|---|---|
| R9 | 3 | 0 | 0 | 0 |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| guardrail config | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| R9 | 3.31 | query_metric 1.17, list_metrics 0.81, explain_change 0.33, check_metric_exists 0.28, check_segment_defined 0.27, check_coverage 0.2, get_metric_tree 0.16, check_causal_evidence 0.08, get_schema 0.01 | 50/16 |

## Telemetry — gpt-5-mini

_USD reflects the **measured** prompt-cache discount (cache hits billed at 10% of input). **cached** = share of input tokens served from the prompt cache. Latency is wall-clock on a shared API; a concurrent run (--concurrency > 1) overlaps requests, so p50/p90/p99 include queueing under load — read the delta BETWEEN cells, not the absolute._

| guardrail config | in tok | out tok | cached | est. USD | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|---|
| R9 | 2,720,475 | 40,243 | 72% | $0.32 | 7.3 | 13.0 | 17.4 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | question-type | failure | answer | gold |
|---|---|---|---|---|---|---|
| gpt-5-mini | R9 | adv_dau_mau | adversarial | fabricated | DAU/MAU (7-day avg DAU divided by trailing 28-day MAU) = 33.2% | None |
| gpt-5-mini | R9 | adv_price_lift | adversarial | fabricated | I need to know whether you want (A) the immediate point-in-time lift in MRR when the March price change went live, or (B) the cumulative additional MRR since the price change through our last full week of data (2026-07-12). Tell me A or B. | None |
| gpt-5-mini | R9 | adv_yoy_june | adversarial | fabricated | June 2026 active users: 1,620; June 2025 active users: not available in coverage (data begins 2025-09-01) | None |
