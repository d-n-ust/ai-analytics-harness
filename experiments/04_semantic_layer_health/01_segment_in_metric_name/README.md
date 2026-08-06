# Study 01 — the segment is encoded in the metric name

> **Rule S1.** The metric name encodes which users are included, instead of exposing that choice
> as an argument. The agent must select between two metrics when it should be selecting between
> two values of one argument.

## The problem

Two metrics measure the same quantity, over the same rows, at the same grain. They differ only in
which users they include, and the only indication of that difference is one word in the name.

**Incorrect — the common pattern**

```yaml
metrics:
  value_moments:
    description: "Number of value moments in the period. Includes all users."
    agg: "sum(moments)"
    base: agg_active_days

  real_value_moments:
    description: "Value moments from real users (excludes internal/test accounts)."
    agg: "sum(moments)"                      # identical
    base: agg_active_days                    # identical
    default_filters: ["NOT is_internal"]     # the only real difference
```

**Correct — the segment is an argument**

```yaml
metrics:
  value_moments:
    description: "Number of value moments in the period."
    agg: "sum(moments)"
    base: agg_active_days
    segments: [everyone, real_users]         # the caller selects one

governance:
  segments:
    everyone:
      description: "Every account, including internal and test users."
      where: []
    real_users:
      description: "Real users only — excludes internal and test accounts."
      where: ["NOT is_internal"]
```

Given the question "how many habits did our customers complete last week?":

```
Incorrect   query_metric(metric="value_moments")     # or real_value_moments? The agent must guess.
Correct     query_metric(metric="value_moments", segment="real_users")
```

In the first version the choice is not visible in the catalogue, and selecting the wrong metric
still produces a valid query. In the second version the choice is an explicit argument with two
documented values.

## Why an incorrect selection is difficult to detect

The two metrics differ by only 3.8% to 4.4%, so selecting the wrong one returns a plausible result.

| | everyone | real users |
|---|---|---|
| last week | 3,785 | 3,642 |
| June 2026 | 16,041 | 15,329 |

This small margin is intentional. The study covers the case where an incorrect answer still looks
correct. Study 02 covers the opposite case, where the error is large.

## The arms

| | What the agent sees | Expected result |
|---|---|---|
| `A_absent` | Two metric names. No statement of which users are included. | Approximately 50% incorrect, reported with confidence. |
| `B_prose` | The difference stated in each description. *(the layer as currently shipped)* | Better, but it depends on the agent reading the descriptions carefully. |
| `C_segment` | The correct version above. The second metric is removed. | High accuracy, because no incorrect selection is available. |
| `B_prose_swapped` | `B_prose` with the two metrics listed in the opposite order. | No difference. This is a position control: any change is caused by ordering, not content. |

## The questions

Two pairs and one control. Each pair requests the same measure for the opposite set of users, so an
agent that always selects the same metric answers exactly one question in each pair correctly.

| | requests | question |
|---|---|---|
| `p_pop_customers_week` | real users | "how many habits did our customers complete last week?" |
| `p_pop_all_week` | everyone | "…across every account, including our own internal and test users" |
| `p_pop_customers_june` | real users | "excluding staff and test accounts, how many in June 2026?" |
| `p_pop_all_june` | everyone | "…in total, counting every account we have" |
| `p_pop_control_mrr` | — | current MRR. Should not change between arms. |

## Status: the result cannot be attributed

Twelve runs are stored in `results/probes/` (4 arms, 5 questions, 1 repetition). `C_segment` scored
highest. That result should not be relied on, for three reasons.

1. **Only one of the five questions distinguished between the arms.** With one discordant pair, the
   lowest achievable p-value is 1.0000. Additional repetitions cannot change this, because
   repetitions measure variation within a question while the effect under test appears across
   questions. Six discordant questions are required for p < 0.05. The set needs more questions, not
   more repetitions.
2. **`C_segment` shares wording with the questions.** Its segment synonyms include `customers`,
   `genuine users` and `excluding staff`, which appear in no other arm. It shares a 9-word verbatim
   sequence with one question, where the other arms share 2 words. Its advantage may therefore come
   from text matching rather than from structure.
3. **`C_segment` offers one metric fewer**, because the repair removes the second metric. When
   selecting at random between two similar options, removing one is worth approximately 50
   percentage points before any treatment is applied.

Both confounds have been retained rather than corrected. Correcting them would change what the
twelve stored runs measured. The runner now reports both automatically on every run. Resolving them
requires two additional arms that have not yet been built: `C_segment_neutral` (the same structure
without the added synonyms) and `B_prose_minus` (prose, with an unrelated metric removed so that it
also offers 14).

**The control question is also ineffective.** All four arms answered the MRR question without
reading the catalogue, because `mrr` can be selected directly from the tool schema. A control that
can be answered without the treatment surface does not control for anything. Correcting this
requires a change to the tool schema, not a different question.

This study should be treated as instrument development. Study 02 is the clean replication.

## Running it

```bash
./bench study 01_segment_in_metric_name --mock            # checks wiring, no cost
./bench study 01_segment_in_metric_name --reps 3          # full run
./bench study 01_segment_in_metric_name --arms C_segment --only p_pop_customers_week --reps 1
./bench study --describe 01_segment_in_metric_name        # each arm's patch and what it changes
```

`study.yml` contains the pre-registered readings and the full record of the problems above.
`cases.yml` contains each question's expected answer and the reason it was selected.
