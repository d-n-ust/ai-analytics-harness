# Experiment 5 — preflight ambiguity benefit

Does fixing what the preflight ambiguity detector finds make the agent measurably more trustworthy —
and does the effect scale with how ambiguous the layer is? Full rationale and the honest boundary are
in `scratchpad/ambiguity/EXPERIMENT-05-DESIGN.md`; this directory is the implementation.

## The four environments — three grounding layers each

Each env is a directory with all three layers a primitive can ground in (the repair-matrix mapping):

| layer | file | primitives it grounds |
|---|---|---|
| documentation | `docs.md` | grain, segments |
| dim/fact tables | `warehouse.sql` | entity, measure |
| semantic layer | `semantic.yml` | additive + higher-level metrics |

preflight reads all three and reports confusions **within** a layer and **across** them (a term the
docs define two ways that also names a metric and a column). The four environments:

| env | ambiguity |
|---|---|
| small_before | the governed layer, as shipped — few (a well-modelled layer still carries a trap) |
| small_after | + preflight's findings fixed — none |
| high_before | a pressured team's accretion, across all three layers — many |
| high_after | + preflight's findings fixed — none |

`high_before` is authored to look real: three teams' `mrr`/`recurring_revenue`, five active-user
definitions, gross vs net revenue (semantic); `moments` overloaded across three tables, two internal
flags, `active_date`/`event_date`/`day` grain drift (warehouse); `active user` and `value moment`
each documented two ways (docs).

## Method (dose-response + before/after)

1. **Dose** — `python scan.py` runs preflight over each layer and tabulates the confusions it flags
   (`scan.md`). small ≪ high.
2. **Fix** — resolve exactly the flagged confusions (rename to encode scope, drop a decoy, reconcile a
   definition) to produce the `_after` layers. preflight re-scans them to ~0.
3. **Measure** — run the harness agent on all four environments over a pre-registered question set and
   read the core indicators: **silent-error rate** (down), **balanced accuracy** (up), **coverage**
   (the trade). Hypotheses: a small improvement on the governed layer, a large one on the pressured
   layer (the dose-response); the improvement concentrates on questions that touch a flagged metric.

Use the **embedding gate** for the reported numbers — the lexical fallback misses synonym-based
confusions (`mrr ~ recurring_revenue`, `active_users ~ engaged_users`), which are the pressure-built
kind. Gold answers are written by three LLM judges (escalate to a human on disagreement), from
business intent, before the fixes, so the answer key cannot drift toward what we changed.

## Status

- [x] `high_before` authored across all three layers to exercise every finding type; `small_before`
      = governed layer.
- [x] `scan.py` + `scan.md` — the dose measurement (embedding gate). The report groups findings by
      layer with live progress; `--detail` cites each to `file:line` and prints the offending source
      line (`scan.md` is the full cited record). `high_before` spans DEFINITION_DIVERGENCE (docs),
      NAME_COLLISION (warehouse `moments` overload), GRAIN_MISMATCH / SCOPE_TRAP / DUPLICATE / SIBLING
      (semantic), and **cross-layer doc+sem** collisions — the full range across all three layers.
- [x] `_after` layers (the fixes) + re-scan. **Dose-response: small 1 → 0, high 18 → 0.**
      The fixes converge the pressured layers on the governed layer: the value_moments SCOPE_TRAP is
      resolved by making scope an argument (one `value_moments`, segment=all|active) rather than a
      bare metric beside a scoped one; the duplicate/sibling/grain metrics collapse to one governed
      definition each; the warehouse consolidates `moments` to one canonical fact with one grain
      column and one internal flag; the docs give one definition per term, matching the governed
      metric it grounds.
- [x] pre-registered question set + gold — `cases.yml` (13 questions: 10 flagged across FIVE families,
      3 clean controls), authored by **three independent, blind red teams** (revenue / users /
      activity-habits) and verified against the star. Gold is a deterministic `gold_sql` oracle
      (`compute_gold`), NOT an LLM judgement. `family` groups correlated items so results read
      per-trap. Two honest lessons shaped the final set: v1 explicit-intent questions found NO effect
      (the trap must be a name-match); and the red teams' SLICED traps (a country / category / plan
      cut) conflate metric SELECTION with filter APPLICATION — the agent botches the filter even on
      the governed layer, so those items scored high on every layer and were dropped. The final tier
      is STRUCTURAL whole-population traps only, where the sole variable is which metric is picked.
- [x] benefit runner — `benefit.py` (Option B: a bespoke runner, since the declarative engine's
      same-numbers guard would fight a before/after design). Runs the agent on each layer over the
      question set (`--reps`), grades, and reports coverage / silent-error / balanced-accuracy via
      `selective()`, split flagged vs clean AND per family; persists per layer so a long run survives
      interruption. `--mock` validates the whole pipeline with no key.
- [x] **agent runs — the result** (on dbt MetricFlow; two models; reps=3). The headline is the
      **high_before → high_after** contrast: `small` is demoted to a cited baseline because its
      before/after was 0 → 0 on wrong-selection (a well-governed layer's one residual trap does not
      bite — the agent navigates it, so static overestimates runtime there).

      SER decomposes into wrong-SELECTION (Mode 1, preflight's lane) + wrong-CONSTRUCTION (Mode 2):

      | model | layer | SER | coverage | wrong-SELECTION | wrong-CONSTRUCTION | clean-SER |
      |---|---|---|---|---|---|---|
      | gpt-5-mini | high_before | 0.30 | 1.00 | **0.43** | 0.00* | 0.11 |
      | gpt-5-mini | high_after | 0.17 | 1.00 | **0.00** | 0.17 | 0.00 |
      | sonnet-5 | high_before | 0.33 | 0.87 | **0.29** | 0.21 | 0.00 |
      | sonnet-5 | high_after | 0.07 | 0.92 | **0.00** | 0.04 | 0.00 |

      \*0 only because those questions are already wrong-selection on high_before, which masks the
      construction slip (the agent picks the wrong metric before it can fumble the right one's query).

      Per-family wrong-selection on high_before (which traps bite): recurring_revenue **1.00**,
      new_users **1.00**, value_moments **0.22**, habits/actives 0 (gpt-5-mini); the value_moments
      cluster bites on the sprawled layer but not the governed one — same finding, different outcome.

      Three things hold: **wrong-selection reproduces on both models** (0.43 / 0.29) and the fix drives
      it to **0** on both (model-robust — the harm preflight predicts); it **concentrates on the flagged
      tier** (clean controls ~0); and **SER falls (0.30→0.17, 0.33→0.07)** as the fix removes the
      selection half. The sharper agent (sonnet-5) makes less construction noise and **abstains more on
      the sprawl** (coverage 0.87) rather than answering confidently wrong. Results in
      `benefit_result_mf__<model>.json`.

Notes: same materialised star for every layer (rung 3); only the shown semantic layer changes. The
sprawled `high_before` has descriptions stripped (bare names), so the agent disambiguates by name.
Stock metrics (mrr, paying_users, active_habits) are modelled from monthly snapshots (semi-additive),
so a stray period does not shrink them; the residual construction harm is genuine agent query-building,
not a fixture artifact. Sample is modest (10 flagged questions x 3 reps). The bespoke three-layer
version (with warehouse + docs cross-layer findings) is retained under `layers/` and `benefit_result.json`
as the proof-of-concept that motivated the MetricFlow port.
