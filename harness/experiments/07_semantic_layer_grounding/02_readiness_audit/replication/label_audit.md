# Label audit of the replication sealed set

Done after the run (results/20261009-224447-head_to_head.json), as pre-registered: every reading
whose outcome was not `correct` was checked against `author_brief.md`. The adoption decision uses
the labels as written; the corrected totals are reported beside them.

## Labels found wrong

| intent | wording | problem | correction |
|---|---|---|---|
| i02 | all 3 | the label sets `grain: day`. The brief defines no grain key; the grader reads an unknown key as a dimension filter, so every reading of both readers failed on it | `time_grain: day`. Every failing reading had no other error |
| i17 | all 3 | the same `grain: month` key | `time_grain: month`. No outcome changes: every reading fails for other reasons |
| i08 | 3rd | the wording writer turned "DE and FR" into "Germany and France"; the label kept the codes | `country_name: [Germany, France]`, the same rows |
| i10 | 2nd, 3rd | the writer turned "the States" into "US" and into "the United States", both listed values; the label still asks | `metric_answer` with `country: US`, and with `country_name: United States` |

The first two are a gap in the brief (it gave no format for a stated bucket size). The last two are
wording drift: the writer did not keep the intent's word, and the label belongs to the intent, not
to the wording.

## Totals over 216 readings per reader

| reader | labels | correct | silent wrong | safe miss | wrong refusal |
|---|---|---|---|---|---|
| questionnaire | as written | 123 (57%) | 39 (18%) | 54 | 0 |
| typed | as written | 140 (65%) | 20 (9%) | 53 | 3 |
| questionnaire | corrected | 135 (63%) | 27 (12.5%) | 54 | 0 |
| typed | corrected | 158 (73%) | 2 (0.9%) | 53 | 3 |

The adoption rule is met under both.

Limit: the stored rows hold each reading's filters, periods and group_by, but not its grain or its
decision record, so the i02 correction assumes the reader's grain matched "day"; it was not
recorded. The test runner now stores the grain and the decision record with each reading.
