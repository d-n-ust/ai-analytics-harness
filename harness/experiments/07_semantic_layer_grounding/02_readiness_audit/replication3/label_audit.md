# Label audit of the third replication sealed set

Done after the run (results/20261010-201801-head_to_head.json, one repetition), as pre-registered.
Regraded with no model call by `regrade.py`, which reproduces the run's own totals on the labels as
written.

## Labels found wrong

| intent | problem | correction |
|---|---|---|
| i08 "Androd accounts … by channel" | `group_by` written beside `type`, not inside `params`, so the grader saw no split | `params.group_by: [channel]` |
| i09, i22 "trend of …" | the same | `params.group_by: [metric_time]` |
| i10, i11 "… by segment" | the same | `params.group_by: [platform, region, channel]` |
| i12 "monthly trend", i17 "weekly trend", i23 "daily trend" | the same, and the bucket size missing | `group_by: [metric_time]` with `time_grain` month, week, day |
| i02 "second half of 2025" | the data starts on 2025-09-05, so the period is partly covered; the label lacks `partial: true` | `partial: true` |

## Totals over 72 readings per reader (one repetition)

| reader | labels | correct | silent wrong | safe miss | wrong refusal |
|---|---|---|---|---|---|
| questionnaire | as written | 34 | 22 | 14 | 2 |
| typed | as written | 36 | 19 | 17 | 0 |
| questionnaire | corrected | 37 (51%) | 22 | 11 | 2 |
| typed | corrected | 57 (79%) | 1 | 14 | 0 |

The adoption rule is met under both. As written, 18 of the typed reader's 19 silent wrong readings
are the misplaced `group_by`; the one that remains is real (below).

## The one real silent wrong

i09, "Please provide the trend of app opens in Germani during the first quarter of 2026": the proposal
left "Germani" unmarked, accounting checked only exact listed words, and the round trip accepted "no
restriction". The total over every country was served. Fixed after the run: accounting treats a
misspelling of a listed value as that word (one edit, two on values of eight letters or more). The
three i09 wordings then read Germany with the correction stated (development check, $0.002).
