# Test 1 — Frozen-prediction regrade

**Frozen prediction:** `2026-08-15-prior.yml` — engine/src/semantic/ambiguity.py @ 1650de3f56b93ddfa82e2c09b150b016b4dee2d3  
**Committed before any run read** (freeze). **Regraded run:** `20260726-224953-gpt-5-mini` (doc's `20260810-181508` does not exist; this is the most complete multi-arm run).  
**Rows joined:** 2736. **No model call, no warehouse, no new run.**

## Step 2 — contingency tables

### Structural prediction (scope_only)

```
predicted         answered  clarified  refused  error | mislabels  wrong%
--------------------------------------------------------------------------
clarify                171          1       20      0 |        51   29.8%
answer                 942         50       63      1 |        55    5.8%
refuse                 299        107     1076      6 |       299  100.0%
```
predicted-clarify cases (4): ['t1_ios_value_moments_june', 't2_americas_value_moments_june', 't2_web_value_moments_june', 't4_apac_value_moments_q2']

### Lexical baseline (name-overlap only)

```
predicted         answered  clarified  refused  error | mislabels  wrong%
--------------------------------------------------------------------------
clarify                362          1       21      0 |        55   15.2%
answer                 751         50       62      1 |        51    6.8%
refuse                 299        107     1076      6 |       299  100.0%
```
predicted-clarify cases (9): ['t1_ios_value_moments_june', 't2_active_annual_subs', 't2_americas_value_moments_june', 't2_biggest_absolute_user_growth', 't2_web_value_moments_june', 't3_active_users_last_week', 't3_power_users', 't4_apac_value_moments_q2', 'vw_paying_users']

## Step 3 — controls

Mislabels split by failure mode: **106** on answerable cases (the near-neighbour swaps this test is about) and **299** on designed-unanswerable cases (answering something that should be refused, a different and loud failure). Strict grader-escaped silent errors: **0**.

The concentration test runs on the **31 answerable cases** only, shuffling which k of them are labelled `clarify`.

```
                              k     gap  null %ile       p   mislabel share   %ile
structural (scope_only)       4   0.240      96.3%   0.038            0.481  99.5%
lexical (name-overlap)        9   0.084      85.1%   0.149            0.519  90.8%
```

Structural clarify captures **48%** of answerable mislabels with **4** case(s); lexical needs **9** cases to reach 52%. Null gap distribution (structural): mean 0.006, 95th pct 0.209.

### Per-case wrong-rate, all answerable cases (the null's population)

The concentration is driven by whichever cases sit at the top; n is small, so this shows exactly which cases carry it rather than hiding behind a pooled rate.

```
case                               S L answered mislabel  wrong%
t2_americas_value_moments_june     C C       38       22   57.9%
t2_referral_signups_q2             . .       36       20   55.6%
t4_apac_value_moments_q2           C C       41       22   53.7%
t4_retention_trend                 . .        3        1   33.3%
t5_not_breadth                     . .       36        9   25.0%
t5_reminder_caused_it              . .       48        8   16.7%
t2_paid_search_spend_q2            . .       43        6   14.0%
t2_web_value_moments_june          C C       46        4    8.7%
t4_real_acquisition_spend_june     . .       41        3    7.3%
t1_ios_value_moments_june          C C       46        3    6.5%
t3_active_users_last_week          . C       48        3    6.2%
t4_real_signups_june               . .       39        1    2.6%
t1_signups_june                    . .       42        1    2.4%
t5_region_or_broader               . .       45        1    2.2%
t5_masked_by_growth                . .       46        1    2.2%
t3_power_users                     . C       48        1    2.1%
t2_biggest_absolute_user_growth    . C        0        0    0.0%
t5_why_drop                        . .       47        0    0.0%
t4_business_health                 . .       46        0    0.0%
vw_paying_users                    . C       48        0    0.0%
t5_which_lever                     . .       47        0    0.0%
t5_offsetting_mid_may              . .        0        0    0.0%
t2_only_platform_improving_frequency . .        0        0    0.0%
t5_engagement_drop                 . .       47        0    0.0%
t3_arpu                            . .       47        0    0.0%
t3_mrr                             . .       48        0    0.0%
t2_only_region_improving_frequency . .        0        0    0.0%
t2_active_annual_subs              . C       47        0    0.0%
t3_activation_rate_june            . .       42        0    0.0%
t5_apac_growth_breadth             . .        0        0    0.0%
t1_spend_june                      . .       48        0    0.0%
```
`S`/`L` = predicted clarify by the Structural / Lexical rule.

## The discriminating 5 cases (structural says answer, lexical says clarify)

If these carry few mislabels, the structural stage was right to exclude them and it beats the fuzzy matcher; if they carry many, the extra precision cost real recall.

```
case                               trials answered mislabel  wrong%
t2_active_annual_subs                  48       47        0    0.0%
t2_biggest_absolute_user_growth         0        0        0    0.0%
t3_active_users_last_week              48       48        3    6.2%
t3_power_users                         48       48        1    2.1%
vw_paying_users                        48       48        0    0.0%
```

For contrast, the 4 structural-clarify cases:

```
case                               trials answered mislabel  wrong%
t1_ios_value_moments_june              48       46        3    6.5%
t2_americas_value_moments_june         48       38       22   57.9%
t2_web_value_moments_june              48       46        4    8.7%
t4_apac_value_moments_q2               48       41       22   53.7%
```

## Step 4 — clarifications currently filed as failures

On the predicted-clarify `metric_answer` cases, the agent clarified (graded as a miss because the case demands a number). Counts:

```
  t2_americas_value_moments_june     clarified 1 time(s)
```

## Mechanism — is each flagged mislabel a scope swap?

For each scope_only-flagged case, the dominant wrong number, how far off gold it is, and the metric the agent declared. A scope swap shows as a few-percent miss with the narrower metric (or `default_filters`) applied; a larger miss with the correct metric is a different error (coverage window, region filter).

```
case                                 gold   served   %off    declared metric  n
t1_ios_value_moments_june            5648     4412 -21.9%               None  1
t2_americas_value_moments_june       5386     5133 - 4.7%               None  9
t2_web_value_moments_june            4812     4524 - 6.0%               None  3
t4_apac_value_moments_q2             3852     4355 +13.1%      value_moments  14
t2_referral_signups_q2                243      234 - 3.7%               None  10
```
Direct read of the recorded explanations: `t2_web` and `t2_americas` say “filtered to non-internal” / declare `real_value_moments` — the scope swap the thesis predicts, 4.7–6% off and past every numeric check. `t4_apac` misses +13% with the **correct** metric declared: that is the APAC coverage window (pre-launch April rows), not a scope confusion — the case was flagged for a valid reason but its mislabels have another cause. `t2_referral_signups` is a genuine scope swap (agent welds `is_internal=false` onto `new_signups`) that the classifier cannot see, because no `real_new_signups` metric is named for it to pair against.

## Verdict

- **Hypothesis (mislabels concentrate on scope_only-predicted cases): MET.** Pooled wrong-rate gap 0.240 (clarify 29.8% vs answer 5.8%), shuffle p=0.038; the 4 clarify cases hold 48% of the 106 answerable mislabels (99th+ percentile of the null).
- **Kill condition (a lexical name-overlap baseline reproduces the concentration): NOT MET.** Lexical gap 0.084, p=0.149 (not significant); it needs 9 clarify cases to reach the same mislabel share the structural rule reaches with 4. The 5 cases lexical adds and structural excludes are near-clean, so the structural stage adds real precision rather than restating the name match.
- **Mechanism confirmed on 2 of the 4, refuted on 1 (see Mechanism above).** `t2_web` (6% off) and `t2_americas` (4.7% off) are genuine scope swaps — the agent applied the non-internal filter / declared `real_value_moments` on an all-users question, exactly the near-neighbour the thesis predicts. `t4_apac` (+13%, correct metric) is the coverage-window trap, not a scope swap, so ~22 of the 51 clarify-cell mislabels are a confound: the clean scope signal rests mainly on `t2_americas`.
- **A comparable, genuinely-scope mislabel source is unflagged.** `t2_referral_signups_q2` is wrong 55.6% of the time and is itself a scope swap (the agent welds `is_internal=false` onto `new_signups`), yet the classifier is silent because no `real_new_signups` metric is named to pair against. The detector sees scope confusion only when BOTH scopings exist as governed metrics; where the agent welds the filter, it is blind — the welded-scope limitation, observed.
- **Strict grader-escaped silent errors: 0.** Every wrong number in this run was caught by the harness's gold-based grade. The 'silence' the thesis means is relative to a downstream consumer without that gold, not to this grader.