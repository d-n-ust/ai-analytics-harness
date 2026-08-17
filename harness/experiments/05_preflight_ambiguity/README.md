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
- [x] pre-registered question set + gold — `cases.yml` (13 questions: 10 flagged across FIVE trap
      families, 3 clean controls). Gold is a deterministic independent `gold_sql` oracle run against
      the clean star (`compute_gold`), NOT an LLM judgement — so no judge panel is needed. Each
      flagged question is a **name-match trap**: its natural wording matches a WRONG metric that
      exists only on the sprawled layer and returns a clearly different number. `family` groups
      correlated items so results read per-trap, not pooled. v1 (explicit intent) found NO effect —
      recorded honestly as the reason for the trap design.
- [x] benefit runner — `benefit.py` (Option B: a bespoke runner, since the declarative engine's
      same-numbers guard would fight a before/after design). Runs the agent on each layer over the
      question set (`--reps`), grades, and reports coverage / silent-error / balanced-accuracy via
      `selective()`, split flagged vs clean AND per family; persists per layer so a long run survives
      interruption. `--mock` validates the whole pipeline with no key.
- [x] **agent runs — the result** (gpt-5-mini, reps=3, n=30 flagged per layer):

      | layer | static findings | flagged silent-error | clean silent-error |
      |---|---|---|---|
      | small_before (governed) | 1 | 0.07 | 0.00 |
      | small_after (fixed) | 0 | **0.00** | 0.00 |
      | high_before (sprawled) | 18 | **0.50** | 0.00 |
      | high_after (fixed) | 0 | **0.00** | 0.00 |

      Per-family flagged silent-error rate (which traps actually bite):

      | family | small_before | small_after | high_before | high_after |
      |---|---|---|---|---|
      | recurring_revenue (mrr vs recurring_revenue, 4.3x) | 0.00 | 0.00 | **1.00** | 0.00 |
      | habits (active_habits vs total_habits, 17%) | 0.00 | 0.00 | **0.83** | 0.00 |
      | subscription_rev (net vs gross, 26%) | 0.00 | 0.00 | 0.17 | 0.00 |
      | monthly_active (active_users vs mau, 4%) | 0.33 | 0.00 | 0.00 | 0.00 |
      | value_moments (robust) | 0.00 | 0.00 | 0.00 | 0.00 |

      Three things hold at once: preflight's static finding count **predicts** the agent's silent-error
      rate (1 → 0.07, 18 → 0.50, the dose-response); **fixing** what it flags drives silent errors to
      **zero** on both arms; and the effect **concentrates on the flagged tier** — the clean controls
      stay 0.00 on every layer, so it is the ambiguity, not noise. Read per-trap, the harm is
      driven by two clear traps (recurring revenue always mis-picked; habits mis-picked 5/6), one weak
      (subscription revenue), and two that do not bite (a near-miss and a robust name) — the honest
      shape of the effect, not a flat average. `monthly_active` at 0.33 on the governed small_before is
      the 4% internal-exclusion near-miss the governed layer itself carries. Result in `benefit_result.json`.

Notes: the agent runs on the SAME materialized star for all four layers (rung 3); only the semantic
layer it is shown changes. The sprawled `high_before` has its metric descriptions stripped (a pressured
team's bare names), so the agent must disambiguate by name — which is where the trap lands. The
governed layers gained `net_revenue` and the sprawl gained `total_habits` to enable the gross/net and
habits families (no warehouse change — the columns existed). Sample is modest (10 flagged questions x 3
reps); more items per family would tighten the weak/null cells.
