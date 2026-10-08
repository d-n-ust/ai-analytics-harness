# Trace (stage 3)

Run `20261007-101406-01_parameter_grounding`. One row per slot of each question's query.

## q_001_android_opens_june

"How many times did Android users open the app in June 2026?" — answer, correct

| slot | value | settled by | outcome |
|---|---|---|---|
| metric | app_opens | the agent alone | proceed |
| metric_filter | activity__is_internal = false | the metric's definition (code) | disclose |
| filter platform | activity__platform = android | the question (decision model), 1.00 | proceed |
| period | 2026-06 | the question (decision model), 0.99 | proceed |

## q_002_android_opens_trend_h1

"How did Android app opens change over the first half of 2026?" — answer, correct

| slot | value | settled by | outcome |
|---|---|---|---|
| metric | app_opens | the agent alone | proceed |
| metric_filter | activity__is_internal = false | the metric's definition (code) | disclose |
| filter platform | activity__platform = android | the question (decision model), 1.00 | proceed |
| group_by | ['metric_time'] | the question (decision model), 1.00 | proceed |
| period | 2026-H1 | the question (decision model), 0.98 | proceed |
| time grain | month | the agent alone | proceed (governed rule not applied) |

## q_003_android_opens_by_segment_june

"How did Android app opens break down by segment in June 2026?" — answer, correct

| slot | value | settled by | outcome |
|---|---|---|---|
| metric | app_opens | the agent alone | proceed |
| metric_filter | activity__is_internal = false | the metric's definition (code) | disclose |
| filter platform | activity__platform = android | the question (decision model), 1.00 | proceed |
| group_by | ['activity__region', 'activity__channel'] | a governance rule (code), 0.97 | disclose |
| period | 2026-06 | the question (decision model), 0.99 | proceed |
