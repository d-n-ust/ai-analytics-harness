# Rubric (stage 2)

Every fact a question can depend on is rated on two axes. Format (prose, JSON, a table) is not an
axis: in experiment 04 it moved results by at most one point (harness note F-27).

## Axis 1 · Where the fact lives

| level | anchor | example from this layer |
|---|---|---|
| **missing** | Nowhere: not in the layer, not in governance, not in code. | "iPhone" means `ios` |
| **prose** | Only in a description or comment, as a statement of what is true. A model must interpret it. | the platform description: "The registered client platform: android, ios, web, or unknown." |
| **prose, prescriptive** | Only in text that tells the agent what to do ("read a whole period directly; do not add months"). Counted apart because the agent applies it where it was not meant (F-17). | the app_opens description: "do not query each month and add them up" |
| **declared** | A field in the layer or governance file that a program can read: `meta.terms`, `meta.owner`, a governance rule. | `trend_granularity` in governance.yml |
| **modelled** | Carried by the shape of the data or the definition: a metric filter, an aggregation, a join, a value read from the data. | `app_opens` filter `is_internal = false`; `agg: sum` |
| **in our code only** | Decided by the harness's code, and stated nowhere in the layer or governance. Works here, travels nowhere. | "a question with no period must be asked for one" (`decisions.read`) |

## Axis 2 · Who consumes it

| level | anchor |
|---|---|
| **model** | Only a model reads it, as text: the agent, or the decision model. A declared field rendered into a prompt is still **model**. |
| **code** | A program acts on it: the engine applies it, a check blocks or rewrites a call, a lookup resolves a word. |
| **—** | Nothing consumes it (the fact is missing). |

## Kind of fact (given, not rated)

| kind | meaning | prediction from earlier experiments |
|---|---|---|
| vocabulary | what a word or value means, which metric a word names, who is counted | being present and read by the model is enough (F-14, F-22, F-10) |
| operation | how parts add up, which filters apply, which values or periods exist, which path to take | only code consumption lowers failures (F-08, F-17) |

## Decision rules

1. Rate what exists, not what should exist. A value list read from the data at run time is **modelled · code**, even though nothing declares the list.
2. A list inside a description is **prose**, even if some code happens to parse it.
3. A value code used as its own name (`ios`) is not a declared word for it.
4. A rule written in governance.yml and applied by the harness is **declared · code**. If the harness applies it only in some cases (for example only when the agent's call leaves the value out), say so in a note.
5. When a fact lives in two places, rate the strongest: code over model; within axis 1, declared or modelled over prose.
6. "Fixed by definition" is not a rating: it is the outcome for a dimension the metric's own filter settles. Rate the filter itself.
7. When a word equals a value code ("Android" for `android`), rate how the **word is mapped to the value**, not where the value list comes from.
8. **—** on axis 2 also covers a fact that is written somewhere but read by nothing (an unread governance note).
9. Code that only copies a fact into text that a model or a person reads (a disclosure sentence, a prompt) counts as **model**. **Code** means the fact changes a query, blocks or rewrites a call, or resolves a word.
10. Transformation code upstream of the layer (staging SQL) counts for which values exist, not for what they mean.
11. If a fact as worded is false, rate the true fact it points to, and correct the wording.
