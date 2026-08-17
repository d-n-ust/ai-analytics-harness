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
- [ ] pre-registered question set + gold (3 LLM judges).
- [ ] agent runs on the four environments; SER / balanced accuracy / coverage.

Note: `small_before` / `small_after` are semantic-only (a governed layer's residual is a semantic
trap); `high_*` carry all three layers. Matching `small` to three layers is only needed for the agent
runs, not the scan dose.
