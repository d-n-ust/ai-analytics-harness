# Leave-One-Out ablation — pre-registration

> **Outcome (2026-07-24):** the Stage-2 pilot falsified the input-guardrail predictions —
> removing them showed no effect because of **defense-in-depth redundancy** (a backstop covers
> for each). LOO from the full stack is confounded here; the design pivoted to the cumulative
> ladder + a restricted-Shapley attribution. Full write-up lives in the decisionspine repo:
> `docs/blog-research/component-attribution-findings.md`.


Registered **2026-07-24**, before any ablation run. Model under test: **gpt-5-mini / minimal**
(main) with **gpt-5-mini / low** verifier. Question set: the frozen 57 (`evaluation/evals/`).
This file is written first so the results below are predictions, not post-hoc stories.

## Objective

Measure what each reliability component contributes **once the rest of the system is present**
(necessity), by removing exactly one component from the full stack and comparing to it.

## Design

- **Reference = `R9`** (all 9 components on).
- **A cell = `R9` minus one component.** Only components nothing depends on can be cleanly
  removed from the top. The partial order (`harness/guardrails.incoherent`) forbids two single-LOO
  cells — `R9-tool_restriction` and `R9-single_metric` — because the output stack presupposes them;
  the runner **skips** these. Their contribution is read instead from the **cumulative ladder delta**
  (`R4`−`R3` for tool_restriction, `R7`−`R6` for single_metric).
- Grounding prompt and toolbox both key off the same guardrail set, so a cell never tells the model
  about a control that is off (the measurement can't vary with the treatment).

## Predictions and falsifiers (per LOO cell)

| cell (remove) | prediction (vs R9) | falsifier |
|---|---|---|
| `R9-check_tools` | ~no change; structure does the work | refusals or correctness drop materially → the model was leaning on the check tools |
| `R9-gate` | fabrication ↑ on `unanswerable` + `adversarial` (out-of-coverage / undefined served) | no fabrication rise → the gate is redundant with downstream checks |
| `R9-resolve` | **phantom fabrication returns** on `rt_phantom` (ungoverned members served, not refused) | `rt_phantom` still refuses → resolution isn't the control catching it |
| `R9-transparency` | ~no change (soft aid) | correctness/scope worsens → the SQL/scope echo was load-bearing |
| `R9-output_validation` | rare; only empty/impossible values slip (few questions reach it) | a broad change → it's doing more than well-formedness |
| `R9-trajectory_verify` | **valid-but-wrong floor returns** — confident-wrong ↑ on `valid_but_wrong` | `valid_but_wrong` confident-wrong stays ~0 → the verifier isn't what's holding the floor |

Foundational controls (ladder-delta, not LOO):
- **tool_restriction** (`R4`−`R3`): fabrication drops sharply once raw SQL is removed.
- **single_metric** (`R7`−`R6`): head-math / composed answers stop (confident-wrong on head-math cases → 0).

## Metrics (scored per cell, as a delta from R9)

Reported separately, never pooled (each on its own denominator):
`confident_wrong` (the safety headline) · coverage · answer-precision · reason-accuracy ·
fabrication · error. **Plus the error-transition matrix** vs R9 — which questions flipped
(`correct→refuse`, `wrong→refuse`, `correct→wrong`) — which is the real evidence of contribution.

## Staging (cheap first)

- **Stage 1** — mock (`--mock`, $0): cells build, incoherent ones skipped, `config` labels correct.
- **Stage 2** — targeted pilot (n=1, ~$0.1): the 6 LOO cells + R9 on the questions each should move
  (`rt_phantom`, `valid_but_wrong`, a few `unanswerable`/`adversarial`); confirm each moves in the
  predicted direction before spending on the full run.
- **Stage 3** — full LOO: 7 cells × 57 questions × n=3 (extend to n=5 only on cells that showed an
  effect).

## Standing caveat

Both models tested so far (gpt-5-mini, deepseek-v4-flash) are *careful* — they rarely commit the
valid-but-wrong error. So this LOO establishes **mechanism** (what each control *can* catch), not
the **magnitude** it matters in the wild; that needs a sloppier model or harder traps, and stays an
open question.
