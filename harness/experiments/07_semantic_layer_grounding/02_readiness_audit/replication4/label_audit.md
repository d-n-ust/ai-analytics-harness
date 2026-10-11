# Label audit of the fourth replication sealed set (typed reader, one repetition)

Done after the run (results/20261011-140413-head_to_head.json), as pre-registered. Regraded from the
stored readings with no model call; the regrade on the labels as written reproduces the run's totals.

## Labels found wrong

| intent | problem | correction |
|---|---|---|
| i17 "app opens from andriod in Q2 2026" | the wording writer corrected the spelling in two of three wordings ("Android"), although told to keep every word; the label still expects a stated correction | `assumption` dropped for the two wordings without the misspelling |
| i07 "app opens in Brazil by segment during summer 2026" | the label (clarify: a southern season) omits the country and the split, so the reader's correct filters were counted as extra | `country_name: Brazil`, `group_by: [platform, region, channel]` added |
| i09 "web app opens in Indonesia during summer 2026" | the same: the country and the platform omitted | `country_name: Indonesia`, `platform: web` added |

## The three headline numbers (72 readings)

| labels | correct | silent wrong | balanced accuracy | coverage |
|---|---|---|---|---|
| as written | 61 | 3 (4.2%) | 80.2% | 96.3% |
| corrected | 68 | 1 (1.4%) | 95.4% | 96.3% |

## The reader's own misses

| reading | outcome | cause | fixed after the run (development) |
|---|---|---|---|
| "Weekly app opens first half 2026." | silent wrong: one total | the proposal filed "Weekly" as a split; the split check said no, and the alternative dropped it with the series it named | an alternative must pass the same accounting as the first reading; a time-unit word as a split is a series. Now asked about |
| "…in Brazil, segmented, for summer 2026." | wrong refusal | "segmented" did not match the rule word "segment" | split phrases matched by stem. Now correct |
| "Combined app opens from Android and iOS…" (one wording) | ask | the combined check said no to a correct reading | — |
| "App opens US vs BR May 2026" | ask | both proposals combined US and BR; the alternative was not confirmed | — |
