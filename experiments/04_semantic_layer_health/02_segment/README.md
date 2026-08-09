# Study 01 — a segment promoted to a metric

> Two governed metrics share an entity, a base table, a grain and a measure, and differ only in
> which population they count. That is one measure and two segments, shipped as two metrics. The
> agent must choose between two metric **names** where it should be choosing between two values of
> one **argument**.

This study carries two instances of that defect. They were separate studies until they were merged,
because they fill the same row of `../primitives_matrix.md` with the same three interventions, and
because two studies agreeing is a weaker claim than one study with an internal replication. The
merge also took the item count from four to eight, which is the binding constraint on everything in
this experiment.

---

## Instance one — the population hides in the NAME (rule S1)

```yaml
value_moments:        # entity value_moments · agg sum(moments) · segment all
real_value_moments:   # entity value_moments · agg sum(moments) · segment active, NOT is_internal
```

Identical in source, aggregation and grain. They differ in **segment** and nothing else, and the
catalogue never renders a segment — so the fact survives only where a description happens to mention
it. Nothing in the metric name says which population it counts; `real_` is a prefix, not a
declaration.

## Instance two — the population hides in the AGGREGATE (rule S4)

**Incorrect, and this is what the layer ships:**

```yaml
power_users:
  agg: "count(distinct case when moments >= 5 then user_id end)"   # a segment inside a CASE
  base: agg_active_days
```

The predicate `moments >= 5` decides who is counted. It is a segment implemented as arithmetic, and
no reader — human or machine — can see it as one.

**Correct:**

```yaml
power_users:
  agg: "count(distinct user_id)"      # aggregation only
  segments: [power]
  default_segment: power              # so a bare call still means what it always meant
```

---

## Why an incorrect selection is difficult to detect

The two metrics in instance one are **3.8–4.4% apart**. At the default 2% tolerance a swap fails the
numeric check, but a reader looking at the answer sees a plausible number. This is the near-miss
case: a wrong pick still looks like an answer.

Instance two behaves differently on purpose. Its threshold trap produces a **15×** error, because
the two studies were designed to test opposite ends of the same question — whether a wrong pick
happens at all when the fact is unstated, and whether it is noticed when the error is small.

### The defect is not visible to the check meant to find it

Provable from the YAML at no cost, with no model involved. The repository's ambiguity lint compares
declared facets, and a segment welded into `agg` declares nothing:

| version | classification | severity |
|---|---|---|
| shipped | `different_measure` | **low** |
| repaired | `scope_only` | **high** |

A lint that reads declarations cannot see a fact that was never declared.

---

## The arms

| arm | what it does |
|---|---|
| `A_absent` | the population fact removed from **both** instances — nothing the agent can read states who is counted, or what the threshold is |
| `B_prose` | the layer exactly as it ships; an empty patch, so "prose is the shipped layer" is true by construction |
| `C_segment` | both repairs: the twin deleted and the population offered as a segment argument; the threshold moved out of `agg` into a named segment |
| `B_prose_swapped` | the shipped layer with the twin pair reordered — a position control, expected null |

The arms compose without conflict. Instance one's strip removes **who is counted**; instance two's
removes **the threshold**; their repairs touch different metrics.

## The questions

Eight, pooled from both instances.

| id | instance | what it tests |
|---|---|---|
| `p_pop_customers_week` / `p_pop_all_week` | name | the same measure, opposite populations, one week |
| `p_pop_customers_june` / `p_pop_all_june` | name | the same pair over a different period |
| `q_thresh_day_week` | aggregate | the threshold matches the metric exactly |
| `q_thresh_lower_bar` | aggregate | grain correct, threshold misread — 3+ against a metric counting 5+ |
| `q_thresh_named_week` | aggregate | ceiling anchor: "power users" is a synonym in every arm |
| `q_control_paid_search` | control | untouched by every arm, and unanswerable from the tool schema alone |

Each population question is paired with its opposite, so an arm that always picks one metric gets
exactly one of the two right.

**The `mrr` control was dropped in the merge.** It was documented as broken: `mrr` is nameable
straight off the `query_metric` enum, so every arm answered it without ever entering the catalogue.
The paid-search control cannot be answered that way, because "paid search" must be resolved to the
governed member `paid_search`, which only the catalogue carries.

---

## Status

Three repetitions, eight questions, four arms.

| arm | correct | confidently wrong |
|---|---|---|
| A_absent | 18/24 | 5 |
| B_prose | 21/24 | 3 |
| **C_segment** | **23/24** | **1** |
| B_prose_swapped | 19/24 | 4 |

Three of thirty-two cells disagree with themselves across identical repetitions, against a five-point
spread between the worst and best arm. **This is the first comparison in this experiment where the
gap is wider than the instability**, and pooling the two instances is what bought that.

### Two reasons not to quote `C_segment` yet

**The vocabulary confound is still there, and is deliberately not repaired.** On the `p_pop_*`
questions, `C_segment` declares synonyms — "including staff", "excluding staff" — that appear in the
questions word for word, sharing a nine-token span. Its win on those items cannot be attributed to
structure. Deleting the synonyms would make the study look clean and destroy the evidence for why
the control exists, so the confound is **pinned by a test** instead.

**`C_segment` also offers one metric fewer**, because its repair deletes the twin. Under random
choice between two confusable options that is worth points before any treatment exists. The arm
declares `changes_candidate_count: true`, and a test asserts that it is the only arm that shrinks.

The two arms that would settle both questions are not built: a version with the bespoke synonyms
removed, and a prose arm with an unrelated metric deleted so it offers the same count.

### What this contradicts

`../prelim_summary_part1.md` reports that declaring a fact bought nothing over describing it, based
on these two instances measured separately with one or two discriminating items each. Pooled, the
declared arm leads. That earlier reading should be treated as superseded rather than reconciled —
but not replaced by this one until the two confounds above are removed.

---

## Running it

```bash
./bench study 02_segment --describe
./bench study 02_segment --mock --reps 1
./bench study 02_segment --reps 3 --concurrency 8
```

Read the vocabulary audit before the results. It prints the longest verbatim span each question
shares with each arm's catalogue, and it is the check that would have caught this study's confound
before the money was spent rather than six weeks afterwards.

`02_segment__mf` runs instance one on **dbt MetricFlow**. It stays a separate study
because it tests engine portability rather than the defect, and it covers only the name instance.
