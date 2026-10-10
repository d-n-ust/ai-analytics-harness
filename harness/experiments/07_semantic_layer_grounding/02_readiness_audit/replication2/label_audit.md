# Label audit of the second replication sealed set

Done after the run (results/20261010-125356-head_to_head.json), as pre-registered: every reading not
`correct` was checked against `author_brief.md` (version 2). The adoption decision uses the labels as
written.

## Labels found wrong

| intent | problem | correction |
|---|---|---|
| i05 "trend of app opens from EMEA", no period | the label asks about the period but omits the series; the brief says a trend is `group_by: [metric_time]`. Both readers asked about the period and failed only on the split | add `group_by: [metric_time]` |
| i16 "trend of all app opens", no period | the same | add `group_by: [metric_time]` |
| i21 "app opens by segment in July 2026" | the data ends on 2026-07-12, so July 2026 is partly outside the data; the brief says refuse | `refuse` |
| i19 "app opens in Brazil during summer 2026" | two rules of the brief apply: summer 2026 is partly outside the data (refuse), and the figure is in the southern hemisphere (ask). The label chose one | `ambiguous` (refuse or ask) |

## Totals over 216 readings per reader

| reader | labels | correct | silent wrong | safe miss | wrong refusal |
|---|---|---|---|---|---|
| questionnaire | as written | 111 (51%) | 42 (19%) | 63 | 0 |
| typed | as written | 135 (62.5%) | 0 | 63 | 18 |
| questionnaire | corrected | 123 (57%) | 48 (22%) | 45 | 0 |
| typed | corrected | 171 (79%) | 0 | 45 | 0 |

The adoption rule is met under both. The typed reader served no wrong number under either label set.
As in the first set, the corrections favour the typed reader (24 correct readings net, against 12 for
the questionnaire), so the claim that does not depend on them is the silent-wrong count: 0 against 42.
