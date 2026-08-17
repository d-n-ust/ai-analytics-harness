# Experiment 5 — preflight ambiguity benefit

Does fixing what the preflight ambiguity detector finds make the agent measurably more trustworthy —
and does the effect scale with how ambiguous the layer is? Full rationale and the honest boundary are
in `scratchpad/ambiguity/EXPERIMENT-05-DESIGN.md`; this directory is the implementation.

## The four environments

Same habit-tracking domain and warehouse; the ambiguity lives in the semantic-layer definitions.

| env | layer | ambiguity |
|---|---|---|
| small_before | the governed layer, as shipped | few (a well-modelled layer still carries a trap or two) |
| small_after | + preflight's findings fixed | none |
| high_before | the layer a pressured team left — overlapping/renamed/undocumented metrics | many |
| high_after | + preflight's findings fixed | none |

`layers/` holds the four. `small_before` is the governed layer verbatim; `high_before` is authored to
look like real accretion (three teams' `mrr`/`recurring_revenue`/`monthly_recurring_revenue`, five
overlapping active-user definitions, gross vs net revenue, `signups` vs `new_signups`, ...).

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

- [x] `high_before` layer authored; `small_before` = governed layer.
- [x] `scan.py` — the dose measurement (see `scan.md`).
- [ ] `_after` layers (the fixes) + re-scan to ~0.
- [ ] pre-registered question set + gold.
- [ ] agent runs on the four environments; SER / balanced accuracy / coverage.
