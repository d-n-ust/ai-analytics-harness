# Results — AI-analyst harness
_Generated 2026-07-24. 384 runs · 1 model(s) · 32 guardrail config(s) · 12 questions · 1 rep(s). Every number labelled with its n; rates never pooled across answerable/unanswerable._

## Selective prediction — gpt-5-mini

_Each cell is one operating point: **coverage** = share of answerable questions answered; **precision** = correct among those answered; **risk** = 1 − precision. **grounded** = share of unanswerable questions NOT fabricated. Not a threshold-swept curve — the ladder traces a frontier, so no single AURC._

| guardrail config | coverage | precision (answered) | risk | grounded (unanswerable) | n |
|---|---|---|---|---|---|
| abstain+check_tools+transparency | 100% | 100% (1) | 0% | 73% | 12 |
| abstain+check_tools+transparency+output_validation | 100% | 100% (1) | 0% | 82% | 12 |
| abstain+check_tools+resolve+transparency | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+resolve+transparency+output_validation | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+tool_restriction+transparency | 100% | 100% (1) | 0% | 82% | 12 |
| abstain+check_tools+tool_restriction+transparency+output_validation | 100% | 100% (1) | 0% | 82% | 12 |
| abstain+check_tools+tool_restriction+transparency+single_metric | 100% | 100% (1) | 0% | 91% | 12 |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 100% | 100% (1) | 0% | 100% | 12 |
| R6-gate | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 100% | 100% (1) | 0% | 91% | 12 |
| R7-gate | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 100% | 100% (1) | 0% | 100% | 12 |
| R8-gate | 100% | 100% (1) | 0% | 100% | 12 |
| R9-gate | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+gate+transparency | 100% | 100% (1) | 0% | 91% | 12 |
| abstain+check_tools+gate+transparency+output_validation | 100% | 100% (1) | 0% | 91% | 12 |
| R6-tool_restriction | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+gate+resolve+transparency+output_validation | 100% | 100% (1) | 0% | 100% | 12 |
| R6-resolve | 100% | 100% (1) | 0% | 91% | 12 |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 100% | 100% (1) | 0% | 91% | 12 |
| R7-resolve | 100% | 100% (1) | 0% | 100% | 12 |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 100% | 100% (1) | 0% | 100% | 12 |
| R8-resolve | 100% | 100% (1) | 0% | 100% | 12 |
| R9-resolve | 100% | 100% (1) | 0% | 91% | 12 |
| R6 | 100% | 100% (1) | 0% | 100% | 12 |
| R8-single_metric | 100% | 100% (1) | 0% | 100% | 12 |
| R7 | 100% | 100% (1) | 0% | 100% | 12 |
| R9-output_validation | 100% | 100% (1) | 0% | 100% | 12 |
| R8 | 100% | 100% (1) | 0% | 100% | 12 |
| R9 | 100% | 100% (1) | 0% | 100% | 12 |

## Correctness axes — gpt-5-mini  (never pooled)

_**groundedness**: is the number computed, not invented (RAG faithfulness). **correctness**: is the value right. **relevancy**: does the metric answer the asked question (wrong-metric selection). Different failures, different columns._

| guardrail config | groundedness | answer-correctness | answer-relevancy |
|---|---|---|---|
| abstain+check_tools+transparency | 73% | 100% | — |
| abstain+check_tools+transparency+output_validation | 82% | 100% | — |
| abstain+check_tools+resolve+transparency | 100% | 100% | — |
| abstain+check_tools+resolve+transparency+output_validation | 100% | 100% | — |
| abstain+check_tools+tool_restriction+transparency | 82% | 100% | — |
| abstain+check_tools+tool_restriction+transparency+output_validation | 82% | 100% | — |
| abstain+check_tools+tool_restriction+transparency+single_metric | 91% | 100% | 100% |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 100% | 100% | 100% |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 100% | 100% | 100% |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 100% | 100% | 100% |
| R6-gate | 100% | 100% | — |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 91% | 100% | — |
| R7-gate | 100% | 100% | 100% |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 100% | 100% | 100% |
| R8-gate | 100% | 100% | 100% |
| R9-gate | 100% | 100% | 100% |
| abstain+check_tools+gate+transparency | 91% | 100% | — |
| abstain+check_tools+gate+transparency+output_validation | 91% | 100% | — |
| R6-tool_restriction | 100% | 100% | — |
| abstain+check_tools+gate+resolve+transparency+output_validation | 100% | 100% | — |
| R6-resolve | 91% | 100% | — |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 91% | 100% | — |
| R7-resolve | 100% | 100% | 100% |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 100% | 100% | 100% |
| R8-resolve | 100% | 100% | 100% |
| R9-resolve | 91% | 100% | 100% |
| R6 | 100% | 100% | — |
| R8-single_metric | 100% | 100% | — |
| R7 | 100% | 100% | 100% |
| R9-output_validation | 100% | 100% | 100% |
| R8 | 100% | 100% | 100% |
| R9 | 100% | 100% | 100% |

## Outcomes — gpt-5-mini

_Counts, primary. `score` is a derived cost-weighted view (a wrong number costs 4 refusals)._

| guardrail config | ✅ right | ❌ wrong | 🤷 idk | deferred | other | err | score |
|---|---|---|---|---|---|---|---|
| abstain+check_tools+transparency | 1 | 10 | 1 | 0 | 0 | 0 | -27 |
| abstain+check_tools+transparency+output_validation | 1 | 7 | 4 | 0 | 0 | 0 | -19 |
| abstain+check_tools+resolve+transparency | 1 | 7 | 4 | 0 | 0 | 0 | -9 |
| abstain+check_tools+resolve+transparency+output_validation | 1 | 7 | 4 | 0 | 0 | 0 | -10 |
| abstain+check_tools+tool_restriction+transparency | 1 | 8 | 3 | 0 | 0 | 0 | -15 |
| abstain+check_tools+tool_restriction+transparency+output_validation | 1 | 8 | 3 | 0 | 0 | 0 | -23 |
| abstain+check_tools+tool_restriction+transparency+single_metric | 1 | 6 | 5 | 0 | 0 | 0 | -21 |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 1 | 0 | 11 | 0 | 0 | 0 | +8 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 1 | 3 | 8 | 0 | 0 | 0 | -7 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 1 | 0 | 10 | 0 | 1 | 0 | +8 |
| R6-gate | 1 | 6 | 5 | 0 | 0 | 0 | -17 |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 1 | 6 | 5 | 0 | 0 | 0 | -8 |
| R7-gate | 1 | 3 | 8 | 0 | 0 | 0 | -6 |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 1 | 0 | 11 | 0 | 0 | 0 | +8 |
| R8-gate | 1 | 4 | 7 | 0 | 0 | 0 | -11 |
| R9-gate | 1 | 0 | 11 | 0 | 0 | 0 | +9 |
| abstain+check_tools+gate+transparency | 1 | 7 | 4 | 0 | 0 | 0 | -18 |
| abstain+check_tools+gate+transparency+output_validation | 1 | 7 | 4 | 0 | 0 | 0 | -19 |
| R6-tool_restriction | 1 | 7 | 4 | 0 | 0 | 0 | -9 |
| abstain+check_tools+gate+resolve+transparency+output_validation | 1 | 7 | 4 | 0 | 0 | 0 | -12 |
| R6-resolve | 1 | 8 | 3 | 0 | 0 | 0 | -19 |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 1 | 7 | 4 | 0 | 0 | 0 | -23 |
| R7-resolve | 1 | 3 | 8 | 0 | 0 | 0 | -8 |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 1 | 0 | 11 | 0 | 0 | 0 | +7 |
| R8-resolve | 1 | 4 | 7 | 0 | 0 | 0 | -13 |
| R9-resolve | 1 | 1 | 10 | 0 | 0 | 0 | +3 |
| R6 | 1 | 7 | 4 | 0 | 0 | 0 | -12 |
| R8-single_metric | 1 | 6 | 5 | 0 | 0 | 0 | -8 |
| R7 | 1 | 3 | 8 | 0 | 0 | 0 | -4 |
| R9-output_validation | 1 | 0 | 11 | 0 | 0 | 0 | +10 |
| R8 | 1 | 4 | 7 | 0 | 0 | 0 | -9 |
| R9 | 1 | 0 | 11 | 0 | 0 | 0 | +8 |

## Question-type coverage — gpt-5-mini  (correct / n by tier)

| guardrail config | rt_phantom | valid_but_wrong |
|---|---|---|
| abstain+check_tools+transparency | 0/4 | 1/8 |
| abstain+check_tools+transparency+output_validation | 0/4 | 1/8 |
| abstain+check_tools+resolve+transparency | 2/4 | 1/8 |
| abstain+check_tools+resolve+transparency+output_validation | 1/4 | 1/8 |
| abstain+check_tools+tool_restriction+transparency | 0/4 | 1/8 |
| abstain+check_tools+tool_restriction+transparency+output_validation | 0/4 | 1/8 |
| abstain+check_tools+tool_restriction+transparency+single_metric | 0/4 | 3/8 |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 0/4 | 8/8 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 0/4 | 5/8 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 0/4 | 8/8 |
| R6-gate | 2/4 | 1/8 |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 2/4 | 2/8 |
| R7-gate | 2/4 | 4/8 |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 1/4 | 7/8 |
| R8-gate | 2/4 | 3/8 |
| R9-gate | 2/4 | 7/8 |
| abstain+check_tools+gate+transparency | 0/4 | 2/8 |
| abstain+check_tools+gate+transparency+output_validation | 0/4 | 1/8 |
| R6-tool_restriction | 2/4 | 1/8 |
| abstain+check_tools+gate+resolve+transparency+output_validation | 3/4 | 1/8 |
| R6-resolve | 0/4 | 1/8 |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 0/4 | 1/8 |
| R7-resolve | 0/4 | 4/8 |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 0/4 | 7/8 |
| R8-resolve | 0/4 | 3/8 |
| R9-resolve | 0/4 | 7/8 |
| R6 | 3/4 | 1/8 |
| R8-single_metric | 3/4 | 1/8 |
| R7 | 3/4 | 5/8 |
| R9-output_validation | 2/4 | 8/8 |
| R8 | 3/4 | 4/8 |
| R9 | 2/4 | 6/8 |

## Refusals by coded reason — gpt-5-mini

_The typed reject option: not just *that* it refused, but *which* reason and whether it was the RIGHT one (matched-expected / wrong-reason / over-refused-an-answerable)._

| guardrail config | dimension_not_supported | no_governed_definition | out_of_scope | result_empty | segment_undefined | ungoverned_dimension_value | wrong_measure |
|---|---|---|---|---|---|---|---|
| abstain+check_tools+transparency | · | · | · | 0✓/1✗/0o | · | · | · |
| abstain+check_tools+transparency+output_validation | · | · | · | 0✓/2✗/0o | · | · | 0✓/1✗/0o |
| abstain+check_tools+resolve+transparency | 0✓/1✗/0o | · | · | · | · | 2✓/0✗/0o | · |
| abstain+check_tools+resolve+transparency+output_validation | 0✓/1✗/0o | · | · | · | 0✓/2✗/0o | 1✓/0✗/0o | · |
| abstain+check_tools+tool_restriction+transparency | 0✓/1✗/0o | · | · | · | 0✓/2✗/0o | · | · |
| abstain+check_tools+tool_restriction+transparency+output_validation | 0✓/1✗/0o | · | · | 0✓/1✗/0o | · | · | · |
| abstain+check_tools+tool_restriction+transparency+single_metric | 0✓/1✗/0o | 2✓/2✗/0o | · | · | · | · | · |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 0✓/1✗/0o | 7✓/1✗/0o | · | 0✓/1✗/0o | 0✓/1✗/0o | · | · |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 0✓/1✗/0o | 4✓/1✗/0o | · | 0✓/1✗/0o | 0✓/1✗/0o | · | · |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 0✓/1✗/0o | 7✓/0✗/0o | 0✓/1✗/0o | 0✓/1✗/0o | · | · | · |
| R6-gate | 0✓/1✗/0o | · | · | · | 0✓/1✗/0o | 2✓/0✗/0o | · |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | · | 1✓/0✗/0o | · | · | 0✓/1✗/0o | 2✓/0✗/0o | · |
| R7-gate | 0✓/1✗/0o | 3✓/0✗/0o | · | · | · | 2✓/0✗/0o | · |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 0✓/1✗/0o | 6✓/0✗/0o | · | · | 0✓/1✗/0o | 1✓/0✗/0o | 0✓/1✗/0o |
| R8-gate | 0✓/1✗/0o | 2✓/0✗/0o | · | · | 0✓/1✗/0o | 2✓/0✗/0o | · |
| R9-gate | 0✓/1✗/0o | 6✓/0✗/0o | · | · | · | 2✓/0✗/0o | 0✓/1✗/0o |
| abstain+check_tools+gate+transparency | 0✓/2✗/0o | 1✓/0✗/0o | · | · | 0✓/1✗/0o | · | · |
| abstain+check_tools+gate+transparency+output_validation | 0✓/1✗/0o | · | · | 0✓/1✗/0o | 0✓/1✗/0o | · | · |
| R6-tool_restriction | 0✓/1✗/0o | · | · | · | 0✓/1✗/0o | 2✓/0✗/0o | · |
| abstain+check_tools+gate+resolve+transparency+output_validation | 0✓/1✗/0o | · | · | · | · | 3✓/0✗/0o | · |
| R6-resolve | 0✓/1✗/0o | · | · | 0✓/1✗/0o | 0✓/1✗/0o | · | · |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 0✓/1✗/0o | · | · | 0✓/2✗/0o | · | · | · |
| R7-resolve | 0✓/1✗/0o | 3✓/2✗/0o | · | · | 0✓/1✗/0o | · | · |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 0✓/1✗/0o | 6✓/3✗/0o | · | · | · | · | 0✓/1✗/0o |
| R8-resolve | 0✓/1✗/0o | 2✓/1✗/0o | · | 0✓/2✗/0o | · | · | · |
| R9-resolve | 0✓/1✗/0o | 6✓/0✗/0o | · | 0✓/1✗/0o | 0✓/1✗/0o | · | 0✓/1✗/0o |
| R6 | 0✓/1✗/0o | · | · | · | · | 3✓/0✗/0o | · |
| R8-single_metric | 0✓/1✗/0o | · | · | · | · | 3✓/0✗/0o | · |
| R7 | 0✓/1✗/0o | 4✓/0✗/0o | · | · | · | 3✓/0✗/0o | · |
| R9-output_validation | 0✓/1✗/0o | 7✓/1✗/0o | · | · | · | 2✓/0✗/0o | · |
| R8 | 0✓/1✗/0o | 3✓/0✗/0o | · | · | · | 3✓/0✗/0o | · |
| R9 | 0✓/1✗/0o | 5✓/0✗/0o | · | · | 0✓/1✗/0o | 2✓/0✗/0o | 0✓/1✗/0o |

_key: matched✓ / wrong-reason✗ / over-refused-answerable-o_

## Wrong answers by type — gpt-5-mini

| guardrail config | fabricated (grounded) | confident-wrong (correct) | wrong-metric (relevant) |
|---|---|---|---|
| abstain+check_tools+transparency | 3 | 4 | 0 |
| abstain+check_tools+transparency+output_validation | 2 | 3 | 0 |
| abstain+check_tools+resolve+transparency | 0 | 3 | 0 |
| abstain+check_tools+resolve+transparency+output_validation | 0 | 3 | 0 |
| abstain+check_tools+tool_restriction+transparency | 2 | 2 | 0 |
| abstain+check_tools+tool_restriction+transparency+output_validation | 2 | 4 | 0 |
| abstain+check_tools+tool_restriction+transparency+single_metric | 1 | 5 | 0 |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 0 | 0 | 0 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 0 | 3 | 0 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 0 | 0 | 0 |
| R6-gate | 0 | 5 | 0 |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 1 | 2 | 0 |
| R7-gate | 0 | 3 | 0 |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 0 | 0 | 0 |
| R8-gate | 0 | 4 | 0 |
| R9-gate | 0 | 0 | 0 |
| abstain+check_tools+gate+transparency | 1 | 4 | 0 |
| abstain+check_tools+gate+transparency+output_validation | 1 | 4 | 0 |
| R6-tool_restriction | 0 | 3 | 0 |
| abstain+check_tools+gate+resolve+transparency+output_validation | 0 | 4 | 0 |
| R6-resolve | 1 | 4 | 0 |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 1 | 5 | 0 |
| R7-resolve | 0 | 3 | 0 |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 0 | 0 | 0 |
| R8-resolve | 0 | 4 | 0 |
| R9-resolve | 1 | 0 | 0 |
| R6 | 0 | 4 | 0 |
| R8-single_metric | 0 | 3 | 0 |
| R7 | 0 | 3 | 0 |
| R9-output_validation | 0 | 0 | 0 |
| R8 | 0 | 4 | 0 |
| R9 | 0 | 0 | 0 |

## Agent behaviour — gpt-5-mini

_**tools/run**: which tools the model uses and how often (call-level, from the trace). **verifier**: the trajectory judge's pass/fail (task-level), where it ran._

| guardrail config | tool-calls/run | tool profile (per run) | verifier pass/fail |
|---|---|---|---|
| abstain+check_tools+transparency | 3.5 | query_metric 1.33, list_metrics 1.0, check_metric_exists 0.33, run_sql 0.25, check_coverage 0.25, describe_table 0.17, check_segment_defined 0.08, get_schema 0.08 | — |
| abstain+check_tools+transparency+output_validation | 3.25 | query_metric 1.33, list_metrics 1.0, check_metric_exists 0.33, check_segment_defined 0.17, check_coverage 0.17, run_sql 0.08, get_schema 0.08, describe_table 0.08 | — |
| abstain+check_tools+resolve+transparency | 2.58 | query_metric 1.25, list_metrics 1.0, check_segment_defined 0.17, check_metric_exists 0.17 | — |
| abstain+check_tools+resolve+transparency+output_validation | 3.33 | query_metric 1.25, list_metrics 0.92, check_coverage 0.33, check_segment_defined 0.25, check_metric_exists 0.17, get_schema 0.17, run_sql 0.17, describe_table 0.08 | — |
| abstain+check_tools+tool_restriction+transparency | 3.58 | query_metric 1.67, list_metrics 1.0, check_metric_exists 0.25, check_segment_defined 0.17, check_coverage 0.17, describe_table 0.17, get_schema 0.17 | — |
| abstain+check_tools+tool_restriction+transparency+output_validation | 2.83 | query_metric 1.17, list_metrics 0.92, check_coverage 0.33, check_metric_exists 0.25, check_segment_defined 0.17 | — |
| abstain+check_tools+tool_restriction+transparency+single_metric | 2.42 | query_metric 1.25, list_metrics 0.92, check_coverage 0.08, check_segment_defined 0.08, check_metric_exists 0.08 | — |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 2.58 | query_metric 1.33, list_metrics 0.92, check_segment_defined 0.17, check_coverage 0.08, check_metric_exists 0.08 | 1/5 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 2.92 | query_metric 1.25, list_metrics 1.0, check_metric_exists 0.42, check_coverage 0.17, check_segment_defined 0.08 | — |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 2.83 | query_metric 1.5, list_metrics 0.83, check_metric_exists 0.33, check_segment_defined 0.08, check_coverage 0.08 | 1/4 |
| R6-gate | 2.67 | query_metric 1.25, list_metrics 1.0, check_segment_defined 0.17, check_metric_exists 0.17, check_coverage 0.08 | — |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 3.17 | query_metric 1.33, list_metrics 0.92, check_segment_defined 0.33, check_metric_exists 0.33, check_coverage 0.17, get_schema 0.08 | — |
| R7-gate | 2.67 | list_metrics 1.0, query_metric 1.0, check_segment_defined 0.42, check_metric_exists 0.25 | — |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 2.92 | query_metric 1.17, list_metrics 1.0, check_segment_defined 0.42, check_metric_exists 0.25, check_coverage 0.08 | 1/5 |
| R8-gate | 2.42 | query_metric 0.92, list_metrics 0.92, check_segment_defined 0.33, check_metric_exists 0.25 | — |
| R9-gate | 2.75 | query_metric 1.08, list_metrics 1.0, check_metric_exists 0.33, check_segment_defined 0.25, check_coverage 0.08 | 1/5 |
| abstain+check_tools+gate+transparency | 3.58 | query_metric 1.42, list_metrics 0.92, check_metric_exists 0.75, check_coverage 0.17, check_segment_defined 0.17, run_sql 0.08, get_schema 0.08 | — |
| abstain+check_tools+gate+transparency+output_validation | 3.0 | query_metric 1.17, list_metrics 0.92, check_metric_exists 0.25, check_coverage 0.17, run_sql 0.17, get_schema 0.17, check_segment_defined 0.08, describe_table 0.08 | — |
| R6-tool_restriction | 2.5 | query_metric 0.92, list_metrics 0.83, check_segment_defined 0.33, check_metric_exists 0.25, get_schema 0.08, run_sql 0.08 | — |
| abstain+check_tools+gate+resolve+transparency+output_validation | 2.83 | query_metric 1.25, list_metrics 1.0, check_segment_defined 0.33, check_metric_exists 0.17, run_sql 0.08 | — |
| R6-resolve | 3.33 | query_metric 1.67, list_metrics 0.83, check_metric_exists 0.33, check_segment_defined 0.25, check_coverage 0.17, describe_table 0.08 | — |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 2.67 | query_metric 1.25, list_metrics 1.0, check_segment_defined 0.17, check_coverage 0.17, check_metric_exists 0.08 | — |
| R7-resolve | 2.42 | query_metric 1.17, list_metrics 0.67, check_metric_exists 0.25, check_segment_defined 0.17, check_coverage 0.17 | — |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 2.5 | query_metric 1.17, list_metrics 0.92, check_coverage 0.17, check_metric_exists 0.17, check_segment_defined 0.08 | 1/5 |
| R8-resolve | 2.5 | query_metric 1.25, list_metrics 0.83, check_metric_exists 0.25, check_coverage 0.08, check_segment_defined 0.08 | — |
| R9-resolve | 2.67 | query_metric 1.5, list_metrics 0.75, check_segment_defined 0.17, check_metric_exists 0.17, check_coverage 0.08 | 2/5 |
| R6 | 2.25 | query_metric 1.33, list_metrics 0.83, check_segment_defined 0.08 | — |
| R8-single_metric | 2.83 | query_metric 1.42, list_metrics 0.83, check_segment_defined 0.33, check_metric_exists 0.25 | — |
| R7 | 1.92 | query_metric 0.92, list_metrics 0.67, check_metric_exists 0.25, check_segment_defined 0.08 | — |
| R9-output_validation | 1.92 | list_metrics 0.92, query_metric 0.92, check_metric_exists 0.08 | 1/4 |
| R8 | 2.0 | query_metric 1.0, list_metrics 0.75, check_segment_defined 0.17, check_coverage 0.08 | — |
| R9 | 2.42 | query_metric 1.0, list_metrics 0.83, check_segment_defined 0.25, check_coverage 0.17, check_metric_exists 0.17 | 1/4 |

## Telemetry — gpt-5-mini

_USD is **estimated** (★ = placeholder price). Latency is wall-clock from a SEQUENTIAL harness on a shared API — read the delta BETWEEN cells, not the absolute._

| guardrail config | in tok | out tok | est. USD * | lat p50 | p90 | p99 |
|---|---|---|---|---|---|---|
| abstain+check_tools+transparency | 206,725 | 2,568 | $0.02 * | 8.7 | 19.2 | 20.7 |
| abstain+check_tools+transparency+output_validation | 193,404 | 2,291 | $0.02 * | 8.0 | 12.3 | 22.5 |
| abstain+check_tools+resolve+transparency | 156,353 | 1,870 | $0.01 * | 6.5 | 9.0 | 10.2 |
| abstain+check_tools+resolve+transparency+output_validation | 194,958 | 2,271 | $0.02 * | 9.7 | 16.4 | 16.6 |
| abstain+check_tools+tool_restriction+transparency | 218,249 | 2,701 | $0.02 * | 9.9 | 16.1 | 20.4 |
| abstain+check_tools+tool_restriction+transparency+output_validation | 173,989 | 2,182 | $0.02 * | 8.1 | 10.8 | 12.9 |
| abstain+check_tools+tool_restriction+transparency+single_metric | 158,107 | 1,876 | $0.01 * | 4.4 | 9.2 | 10.6 |
| abstain+check_tools+tool_restriction+transparency+single_metric+trajectory_verify | 175,781 | 2,317 | $0.02 * | 9.3 | 11.2 | 14.1 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | 192,491 | 2,295 | $0.02 * | 5.1 | 10.1 | 10.1 |
| abstain+check_tools+tool_restriction+transparency+single_metric+output_validation+trajectory_verify | 195,158 | 6,520 | $0.02 * | 10.2 | 13.2 | 54.2 |
| R6-gate | 159,162 | 1,917 | $0.01 * | 6.4 | 10.3 | 14.1 |
| abstain+check_tools+tool_restriction+resolve+transparency+output_validation | 189,655 | 2,391 | $0.02 * | 9.8 | 14.5 | 17.4 |
| R7-gate | 188,978 | 2,127 | $0.02 * | 6.3 | 11.7 | 18.0 |
| abstain+check_tools+tool_restriction+resolve+transparency+single_metric+trajectory_verify | 194,674 | 2,127 | $0.02 * | 9.6 | 13.1 | 16.5 |
| R8-gate | 161,656 | 1,949 | $0.01 * | 5.6 | 10.5 | 10.6 |
| R9-gate | 198,157 | 2,108 | $0.02 * | 11.0 | 20.6 | 22.8 |
| abstain+check_tools+gate+transparency | 234,020 | 2,831 | $0.02 * | 8.9 | 13.2 | 16.6 |
| abstain+check_tools+gate+transparency+output_validation | 186,748 | 2,401 | $0.02 * | 7.4 | 13.2 | 13.4 |
| R6-tool_restriction | 168,503 | 2,027 | $0.01 * | 6.6 | 9.3 | 14.2 |
| abstain+check_tools+gate+resolve+transparency+output_validation | 186,222 | 2,234 | $0.02 * | 6.2 | 11.1 | 15.6 |
| R6-resolve | 213,848 | 2,649 | $0.02 * | 9.1 | 12.7 | 15.8 |
| abstain+check_tools+gate+tool_restriction+transparency+output_validation | 166,784 | 2,374 | $0.01 * | 6.3 | 12.9 | 13.8 |
| R7-resolve | 170,607 | 2,472 | $0.02 * | 6.3 | 12.7 | 13.1 |
| abstain+check_tools+gate+tool_restriction+transparency+single_metric+trajectory_verify | 164,413 | 1,775 | $0.01 * | 8.6 | 10.6 | 11.0 |
| R8-resolve | 168,217 | 2,184 | $0.01 * | 5.9 | 10.5 | 12.0 |
| R9-resolve | 209,027 | 2,474 | $0.02 * | 10.1 | 17.1 | 17.3 |
| R6 | 139,766 | 1,734 | $0.01 * | 6.5 | 9.7 | 10.5 |
| R8-single_metric | 181,723 | 2,186 | $0.02 * | 7.7 | 15.5 | 17.2 |
| R7 | 138,355 | 1,685 | $0.01 * | 4.9 | 8.1 | 8.3 |
| R9-output_validation | 137,595 | 1,599 | $0.01 * | 6.5 | 9.8 | 11.5 |
| R8 | 136,873 | 1,620 | $0.01 * | 5.0 | 10.5 | 11.1 |
| R9 | 184,778 | 2,125 | $0.02 * | 8.7 | 11.1 | 15.7 |

## Wrong numbers (asserted a number that was wrong)

| model | cell | qid | type | answer | gold |
|---|---|---|---|---|---|
| gpt-5-mini | abstain+check_tools+transparency | rt_ipados_open_rate | fabricated | iOS: 40.27% vs Android: 37.75% | None |
| gpt-5-mini | abstain+check_tools+transparency | rt_north_america_actives | fabricated | 24,182 | None |
| gpt-5-mini | abstain+check_tools+transparency | rt_mexico_signups | fabricated | 0 | None |
| gpt-5-mini | abstain+check_tools+transparency | t1_total_habits | confident_wrong | 7467 | 7467.0 |
| gpt-5-mini | abstain+check_tools+transparency | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+transparency | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | abstain+check_tools+transparency | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+transparency | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+transparency | rt_activation_count_june | confident_wrong | 0.5322283609576427 | 289.0 |
| gpt-5-mini | abstain+check_tools+transparency | rt_arpu_annual | confident_wrong | $7.24 per month (≈ $86.85 per year) | 86.85 |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | rt_ipados_open_rate | fabricated | iOS: 40.27% ; iPadOS: not separately reported —  platform-level data only reports 'ios' and 'android' | None |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | rt_mexico_signups | fabricated | 0 | None |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | rt_activation_count_june | confident_wrong | 289 | 289.0 |
| gpt-5-mini | abstain+check_tools+transparency+output_validation | rt_arpu_annual | confident_wrong | 7.237403414195867 | 86.85 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | vw_total_users | confident_wrong | 2500 | 2500.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | rt_activation_count_june | confident_wrong | 289 | 289.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency | rt_arpu_annual | confident_wrong | 86.8488409699504 | 86.85 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | t1_total_habits | confident_wrong | 7,467 | 7467.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | vw_arr | confident_wrong | 32220.92000000001 | 32220.92 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | vw_total_users | confident_wrong | 2,500 | 2500.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | rt_activation_count_june | confident_wrong | 289 | 289.0 |
| gpt-5-mini | abstain+check_tools+resolve+transparency+output_validation | rt_arpu_annual | confident_wrong | 7.237403414195867 | 86.85 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | rt_north_america_actives | fabricated | 49,213 | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | rt_paid_social_activation | fabricated | 21.3% | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | vw_total_users | confident_wrong | 2500 | 2500.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | rt_activation_count_june | confident_wrong | 294 | 289.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency | rt_arpu_annual | confident_wrong | 87.00 | 86.85 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | rt_ipados_open_rate | fabricated | iOS: 40.27%, iPadOS: (no separate iPadOS rows) | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | rt_north_america_actives | fabricated | 125,482 | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | rt_activation_count_june | confident_wrong | 53.22283609576427 | 289.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+output_validation | rt_arpu_annual | confident_wrong | 86.85 | 86.85 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | rt_ipados_open_rate | fabricated | iPadOS: 40.35% vs iOS: 40.35% (over last 30 days) | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric | rt_activation_count_june | confident_wrong | 53.22% | 289.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | vw_total_subscriptions | confident_wrong | 371 active subscriptions | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+transparency+single_metric+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-gate | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | R6-gate | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | R6-gate | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-gate | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-gate | rt_activation_count_june | confident_wrong | 0.5322283609576427 | 289.0 |
| gpt-5-mini | R6-gate | rt_arpu_annual | confident_wrong | 7.237403414195867 | 86.85 |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | rt_ipados_open_rate | fabricated | iOS: 40.87% vs iPadOS: no governed segment | None |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | rt_activation_count_june | confident_wrong | 294 | 289.0 |
| gpt-5-mini | abstain+check_tools+tool_restriction+resolve+transparency+output_validation | rt_arpu_annual | confident_wrong | $7.24 per month → $86.85 per year | 86.85 |
| gpt-5-mini | R7-gate | t1_total_habits | confident_wrong | 67,132 habits have been created in total. | 7467.0 |
| gpt-5-mini | R7-gate | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R7-gate | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-gate | t1_total_habits | confident_wrong | Total habits created (value moments / completed habits): 67,132 | 7467.0 |
| gpt-5-mini | R8-gate | vw_total_subscriptions | confident_wrong | 371 active subscriptions | 457.0 |
| gpt-5-mini | R8-gate | rt_total_subs_ever | confident_wrong | 371 subscriptions active now (active_subscriptions) | 457.0 |
| gpt-5-mini | R8-gate | rt_arpu_annual | confident_wrong | 7.2374034141958665 | 86.85 |
| gpt-5-mini | abstain+check_tools+gate+transparency | rt_paid_social_activation | fabricated | 20.4% | None |
| gpt-5-mini | abstain+check_tools+gate+transparency | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+gate+transparency | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency | rt_activation_count_june | confident_wrong | 53.22% | 289.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency | rt_arpu_annual | confident_wrong | 86.85 | 86.85 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | rt_north_america_actives | fabricated | 18,742 | None |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | t1_total_habits | confident_wrong | 7467 | 7467.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | rt_activation_count_june | confident_wrong | 53.22% | 289.0 |
| gpt-5-mini | abstain+check_tools+gate+transparency+output_validation | rt_arpu_annual | confident_wrong | $7.237403414195867 | 86.85 |
| gpt-5-mini | R6-tool_restriction | t1_total_habits | confident_wrong | 7467 | 7467.0 |
| gpt-5-mini | R6-tool_restriction | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | R6-tool_restriction | vw_total_users | confident_wrong | 2,500 users | 2500.0 |
| gpt-5-mini | R6-tool_restriction | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-tool_restriction | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-tool_restriction | rt_activation_count_june | confident_wrong | 0.5322283609576427 | 289.0 |
| gpt-5-mini | R6-tool_restriction | rt_arpu_annual | confident_wrong | $7.24 per month (≈ $86.85 per year) | 86.85 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | t1_total_habits | confident_wrong | 67132 | 7467.0 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | rt_activation_count_june | confident_wrong | 289 | 289.0 |
| gpt-5-mini | abstain+check_tools+gate+resolve+transparency+output_validation | rt_arpu_annual | confident_wrong | 86.85 | 86.85 |
| gpt-5-mini | R6-resolve | rt_north_america_actives | fabricated | 184,732 | None |
| gpt-5-mini | R6-resolve | t1_total_habits | confident_wrong | 67132 | 7467.0 |
| gpt-5-mini | R6-resolve | vw_arr | confident_wrong | 32221. - ARR = MRR * 12 | 32220.92 |
| gpt-5-mini | R6-resolve | vw_total_users | confident_wrong | 2,100 | 2500.0 |
| gpt-5-mini | R6-resolve | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-resolve | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6-resolve | rt_activation_count_june | confident_wrong | 293 | 289.0 |
| gpt-5-mini | R6-resolve | rt_arpu_annual | confident_wrong | 86.85 | 86.85 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | rt_ipados_open_rate | fabricated | iOS: 0.4026931709 (40.27%); iPadOS: not available in governed platform breakdown | None |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | t1_total_habits | confident_wrong | 67132 | 7467.0 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | rt_activation_count_june | confident_wrong | 0.5322283609576427 | 289.0 |
| gpt-5-mini | abstain+check_tools+gate+tool_restriction+transparency+output_validation | rt_arpu_annual | confident_wrong | $7.237403414195867 per month (ARPU - average MRR per paying user). | 86.85 |
| gpt-5-mini | R7-resolve | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | R7-resolve | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R7-resolve | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-resolve | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | R8-resolve | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-resolve | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-resolve | rt_activation_count_june | confident_wrong | 53.22283609576427% | 289.0 |
| gpt-5-mini | R9-resolve | rt_north_america_actives | fabricated | 0 | None |
| gpt-5-mini | R6 | t1_total_habits | confident_wrong | 67132 | 7467.0 |
| gpt-5-mini | R6 | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | R6 | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | R6 | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6 | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R6 | rt_activation_count_june | confident_wrong | 289 | 289.0 |
| gpt-5-mini | R6 | rt_arpu_annual | confident_wrong | $7.24 per month, which annualizes to $86.85 per paying customer per year | 86.85 |
| gpt-5-mini | R8-single_metric | t1_total_habits | confident_wrong | 67,132 | 7467.0 |
| gpt-5-mini | R8-single_metric | vw_arr | confident_wrong | 32220.92 | 32220.92 |
| gpt-5-mini | R8-single_metric | vw_total_subscriptions | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-single_metric | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8-single_metric | rt_activation_count_june | confident_wrong | 293 | 289.0 |
| gpt-5-mini | R8-single_metric | rt_arpu_annual | confident_wrong | $7.24 per month → $86.85 per year | 86.85 |
| gpt-5-mini | R7 | vw_total_users | confident_wrong | We have 2,100 distinct active users (non-internal) in total. | 2500.0 |
| gpt-5-mini | R7 | vw_total_subscriptions | confident_wrong | We have 371 active subscriptions in total. | 457.0 |
| gpt-5-mini | R7 | rt_total_subs_ever | confident_wrong | 371 | 457.0 |
| gpt-5-mini | R8 | t1_total_habits | confident_wrong | 67,132 habits (value moments) have been created in total. | 7467.0 |
| gpt-5-mini | R8 | vw_total_users | confident_wrong | 2100 | 2500.0 |
| gpt-5-mini | R8 | vw_total_subscriptions | confident_wrong | 371 active subscriptions (point-in-time). | 457.0 |
| gpt-5-mini | R8 | rt_total_subs_ever | confident_wrong | 371 subscriptions sold since launch (currently active subscriptions). | 457.0 |
