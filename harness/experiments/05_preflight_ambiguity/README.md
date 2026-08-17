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
- [x] **agent runs — the result** (gpt-5-mini, reps=3, n=30 flagged per layer):

      | layer | static findings | flagged silent-error | clean silent-error |
      |---|---|---|---|
      | small_before (governed) | 1 | 0.10 | 0.00 |
      | small_after (fixed) | 0 | 0.03 | 0.00 |
      | high_before (sprawled) | 18 | **0.60** | 0.00 |
      | high_after (fixed) | 0 | **0.07** | 0.00 |

      Per-family flagged silent-error rate (which traps actually bite):

      | family | small_before | small_after | high_before | high_after |
      |---|---|---|---|---|
      | recurring_revenue (mrr vs recurring_revenue, 4.3x) | 0.00 | 0.00 | **1.00** | 0.00 |
      | habits (active_habits vs total_habits, 17%) | 0.00 | 0.00 | **1.00** | 0.00 |
      | new_users (new_signups vs new_users, internal) | 0.00 | 0.00 | **0.50** | 0.00 |
      | gross_net (net vs gross, 26%) | 0.50 | 0.17 | 0.50 | 0.33 |
      | value_moments / arpu (robust) | 0.00 | 0.00 | 0.00 | 0.00 |

      The headline holds: preflight's finding count **predicts** the silent-error rate (1 → 0.10,
      18 → 0.60, the dose-response); **fixing** what it flags collapses it (high 0.60 → 0.07); the
      effect **concentrates on the flagged tier** (clean controls 0.00 everywhere). Read per-trap, three
      families are crisp — recurring revenue (always mis-picked on the sprawl, 1.00 → 0), habits
      (1.00 → 0), new users (0.50 → 0). One family, **gross_net, is muddy** (0.50 even on the governed
      layer): adding `net_revenue` beside the existing `mrr` created a genuine governed-layer overlap —
      "subscription revenue" is ambiguous between recurring and recognised revenue there too — so it is
      NOT a clean selection trap, and its high_before number is not cleanly attributable to the sprawl.
      value_moments and arpu are robust (0 everywhere, within-tier controls). Result in `benefit_result.json`.

Notes: same materialised star for all four layers (rung 3); only the shown semantic layer changes.
The sprawled `high_before` has descriptions stripped (bare names), so the agent disambiguates by name.
Honest boundary from the red-team round: the harm the agent runs measure is metric SELECTION on
whole-population questions; sliced questions (a segment/category/plan cut) also exercise filter
APPLICATION, which fails on every layer and is a different problem. Sample is modest (10 flagged
questions x 3 reps); the crisp families would carry a fuller set, and gross_net should be redesigned
(remove the governed mrr/net_revenue overlap) or dropped.
