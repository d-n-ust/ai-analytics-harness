# Study 02 — the segment is defined inside the aggregate

> **Rule S4.** A filter that determines which users are counted is implemented inside the SQL
> aggregate expression instead of through the layer's segment mechanism. Neither the agent nor any
> automated check can see it.

## The problem

A threshold that determines which users are included is placed inside the aggregate expression
rather than declared as a segment.

**Incorrect — the layer as currently shipped**

```yaml
power_users:
  description: "Distinct real users who logged 5+ value moments in a single day."
  agg: "count(distinct case when moments >= 5 then user_id end)"   # a segment inside a CASE
  base: agg_active_days
```

**Correct — the threshold is a declared segment**

```yaml
power_users:
  description: "Distinct highly-engaged real users in the period."
  agg: "count(distinct user_id)"           # aggregation only
  base: agg_active_days
  segments: [power]
  default_segment: power                   # required — see below

governance:
  segments:
    power:
      description: "5+ value moments in a single day"
      where: ["moments >= 5"]
```

`default_segment` is required for the comparison to be fair. Without it, moving the threshold out
of the aggregate means a call that names no segment returns **886** instead of **21**. The repair
would then replace a hidden filter with a missing one, which is a worse defect than the original.
The restriction is part of the definition of `power_users`, so the metric declares it and a call
with no segment returns what it has always returned.

## Why this matters

The threshold's time grain is not stated anywhere. "5+ in a single day" and "5+ across the week"
are different questions, and both return plausible numbers:

| question | result |
|---|---|
| 5+ in a single day, last week — what the metric returns | **21** |
| 5+ summed across the whole week | **326**, a factor of 15 |
| 3+ in a single day | **337**, a factor of 16 |
| all active users, for scale | 886 |

An incorrect answer here is large rather than marginal, and it is still easy to produce. Study 01
covers the opposite case, where a 4% error is difficult to detect.

## The arms

All three arms offer the same fifteen metrics, so none of them gains the selection advantage that
affected study 01. `B_prose` and `C_segment` contain the identical sentence; only its location
differs.

| | What the agent sees | Expected result |
|---|---|---|
| `A_absent` | "Highly-engaged users." The threshold appears nowhere. | Incorrect, with no information available to detect it. |
| `B_prose` | The incorrect version above. *(the layer as currently shipped)* | Mostly correct, but liable to confuse per-day with per-week. |
| `C_segment` | The correct version above. | Correct, because the grain is part of the definition rather than a sentence. |

## The questions

One answerable question, two traps that fail in opposite directions, one anchor and one control.
The set is designed so that neither trivial strategy produces a good score:

| | question | correct response |
|---|---|---|
| `q_thresh_day_week` | "five or more habits in a single day last week?" | answer **21** |
| `q_thresh_week_total` | "five or more **in total over** last week?" | **refuse** — wrong grain (21 against 326) |
| `q_thresh_lower_bar` | "**three** or more in a single day?" | **refuse** — the threshold is 5 (21 against 337) |
| `q_thresh_named_week` | "how many power users last week?" | answer **21** *(anchor: correct in every arm)* |
| `q_control_paid_search` | "paid search spend in June 2026?" | answer *(control)* |

```
always answer 21  -> 2/5      always refuse -> 2/5      read the model correctly -> 5/5
```

## Status: run at 3 repetitions

gpt-5.6-terra, 45 runs. The score column applies a penalty of −4 for a confidently incorrect number:

| arm | correct | score | confidently incorrect |
|---|---|---|---|
| `A_absent` | 13/15 | **13** | 0 |
| `B_prose` | 15/15 | **15** | 0 |
| `C_segment` | 13/15 | **5** | **2** |

**`C_segment` performed worse than `B_prose`, by the mechanism recorded before the run.** Segments
are rendered in a global list that does not state which metric offers them, so the agent has to
associate `power` with `power_users` by name alone. On the grain trap it returned 21 against a true
value of 326 in 2 of 3 repetitions. In one of those it had explicitly selected `segment: power`
first, which suggests that selecting the segment is treated as satisfying the requirement rather
than as a fact to check. This is a result about the renderer: rendering offered segments on each
metric may be the effective repair.

**The prediction for `A_absent` was incorrect.** The expected failure was a confident 21 on the
grain trap. Instead it refused all three times, because with no threshold stated it could not
justify selecting any metric. It failed on the answerable question instead, over-refusing in 2 of 3
repetitions. Omitting the information reduces errors on trap questions and increases them on
answerable ones.

Two of the five questions distinguished between the arms, in opposite directions. This is why the
raw counts are equal for `A_absent` and `C_segment` at 13/15 while the scored totals differ by 8.

**This run is a pilot.** With three discriminating questions the lowest achievable two-sided
p-value is 0.25, and even if all five questions were discordant it would be 0.0625. Significance
requires six discordant questions, which means an additional question block rather than more
repetitions.

**The control question did not work.** In 8 of 9 control rows the catalogue was never read, because
the `metric` parameter of `query_metric` is an enum containing all fifteen names and the model can
select from it directly. No change to the question resolves this.

## Deterministic result, no model required

In the incorrect version, the repository's ambiguity lint classifies the pair
`active_users ~ power_users` as `different_measure` with **low** severity. In the correct version
the same pair is classified as `scope_only` with **high** severity. The defect is therefore not
visible to the check intended to find it, which can be demonstrated from the YAML at no cost.

## Running it

```bash
./bench study 02_segment_in_aggregate --mock              # checks wiring, no cost
./bench study 02_segment_in_aggregate --reps 3            # full run
./bench study 02_segment_in_aggregate --arms B_prose,C_segment --only q_thresh_week_total --reps 5
./bench study --describe 02_segment_in_aggregate          # each arm's patch and what it changes
```

To inspect the mechanism behind the result, comparing what each arm showed the model:

```bash
./bench context --run results/experiments/<dir> --diff B_prose,C_segment
```

`study.yml` contains the pre-registered predictions and the power calculation. `cases.yml` contains
each question's expected answer and the reason the accepted refusal codes are widened.
