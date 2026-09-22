# Questions

`q_*` files are the calibration set: answerable, unambiguous questions. `t_*` files are trap
questions derived from them, each with one failure mode that can produce a wrong number. The design
and the reasons for it are in `../milestoneA.md` ("Measurement design").

Each file records the expected result under `expected`. The labels were written before any
three-arm run, and the reference values were computed directly from `runs/warehouse.duckdb`.

## Fields

| field | meaning |
|---|---|
| `arms` | which arms the question runs in: A raw agent, B raw agent + disclosure instruction, C grounding protocol |
| `variant_of` | (`t_*` only) the calibration question it was derived from |
| `failure_mode` | (`t_*` only) the failure the question is built to trigger |
| `expected.outcome` | `answer`, `answer_with_caveat`, `clarify_or_answer_both`, or `abstain_on_part` |
| `expected.metric` | the governed metric; absent when the metric itself is the ambiguous decision |
| `expected.decisions[]` | one entry per decision in the query, see below |
| `expected.value` | the correct number or numbers |
| `expected.acceptable` | answers scored as correct |
| `expected.incorrect` | answers scored as wrong; stating one of these as fact is a confident-wrong answer |

## `expected.decisions[]`

| field | meaning |
|---|---|
| `parameter` | `metric`, `filter`, `metric_filter`, `group_by`, `time_grain`, `period`, `total_aggregation` |
| `value` | the expected value; `null` means the decision should not be set |
| `basis` | `question`, `governed_declaration`, `governed_principle`, or `none` |
| `selectable` | `false` when the metric fixes the decision and the agent cannot change it. Such decisions count for answer trust, not agent reliability |
| `changes_number` | whether a different plausible value gives a different result |
| `alternative` | the result under the most likely alternative value, where it was computed |
| `must_disclose` | whether the answer must state this decision. True for decisions that change the number and that the reader would not assume |
