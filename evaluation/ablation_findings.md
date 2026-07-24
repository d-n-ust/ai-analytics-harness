# Understanding each component's contribution — what we tried, found, and concluded

A research log (2026-07-24) for the question: **can we measure what each reliability component
contributes?** Kept for history so the reasoning behind the experimental design is recoverable.

## The question

The reliability stack is now 9 independent components (`harness/guardrails.py`), not a fixed
ladder. Natural next question: how much does each one contribute? We tried to answer it and hit —
then understood — a structural obstacle.

## Attempt 1 — Leave-One-Out (remove one from the full stack)

Pre-registered predictions in `loo_preregistration.md`. Ran a cheap targeted pilot (7 cells × 16
questions × n=1, ~$0.10 — the point of a pilot is to spend a dime before committing hours).

**Result: 1 prediction confirmed, 2 falsified — and the falsifiers were the finding.**

| cell | predicted | actual | mechanism (from the traces) |
|---|---|---|---|
| `R8` (remove verifier) | valid-but-wrong confident-wrong ↑ | **0 → 4** ✓ | nothing backstops the valid-but-wrong floor |
| `R9-resolve` | phantom fabrication returns | **no change** | `North America` → empty slice `(0,)` → **`output_validation` refuses** (`result_empty`) |
| `R9-gate` | out-of-coverage fabrication ↑ | **no change** | model queried pre-launch March APAC (got 472) but **refused via `check_tools`/KB** (`out_of_coverage`) |

**The finding: defense-in-depth redundancy.** Removing any single *input* guardrail shows ~no
effect because a different downstream control covers for it. LOO from the full stack therefore
*understates* each control's contribution — a naive counterfactual under interaction.

## Attempt 2 — independent Add-One (add one to the bare baseline) — rejected without running

The mirror failure: our components form a **dependency chain**, so most do nothing in isolation.
`single_metric`/`trajectory_verify` are `incoherent()` without their prerequisites; `gate`/`resolve`
are silently *bypassed* when raw SQL is available (no `tool_restriction`). So "bare + one control"
measures nothing for most controls.

**Conclusion from Attempts 1–2:** the **cumulative ladder (add-one in dependency order) is the
correct instrument** for marginal contribution — it adds each control where it functions and
*before* its backstops exist, so it is neither dependency-broken (add-one-independent) nor
redundancy-confounded (LOO). LOO is clean only for the top, un-backstopped control (the verifier).

## Research — this is a named, solved problem

- **Attribution under interaction.** "Naive counterfactuals underestimate total effects by failing to
  account for interactions" — exactly our LOO result. The principled fix is **Shapley values**: a
  component's importance = its *average marginal contribution over all orderings*, which splits
  shared credit between a control and its backstop instead of zeroing it.
  ([Shapley-attributed ablation, PLOS One](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0277975);
  [Shapley in ML survey](https://arxiv.org/pdf/2202.05594))
- **Dependencies** are handled by **Shapley with restricted coalitions / the Owen value**: average
  only over orderings that respect the precedence structure — our `incoherent()` constraint,
  formalized. ([restricted-coalitions Shapley, Springer](https://link.springer.com/article/10.1007/BF01240150))
- **Frontier / industry practice.** Layered **defense-in-depth** is the *intended* design:
  "no single control is reliable alone… complementary, not substitutable." So "no single input
  guardrail is individually necessary" is a *success*, not a measurement failure.
  ([industry survey](https://www.patronus.ai/ai-reliability/ai-guardrails);
  [trustworthy-agentic-AI survey](https://arxiv.org/pdf/2605.23989))

## Conclusion — three questions, three instruments

There is no single "importance" number; there are three, and their disagreement is the insight:

| question | instrument | note |
|---|---|---|
| "What did adding X buy, in deployment order?" | **cumulative ladder** | un-confounded marginal |
| "Is X removable without failure?" | **leave-one-out** | mostly *yes* → the defense-in-depth signal |
| "Order-independent importance under interaction" | **restricted Shapley** | the principled single number |

High ladder-marginal + low LOO-necessity ⇒ a **redundant layer** (the input guardrails);
high on both ⇒ **load-bearing** (the verifier). That contrast *is* the result.

## The distinctive opportunity

Exact Shapley is intractable for frontier models (NP-hard, huge component counts). **We have 9
components and the `--cells` machinery to run any coherent config, so exact restricted Shapley is
feasible for us** — rare in the agent-reliability literature, which ships naive ablations.

## Recommended experiment + sizing

Trim the Shapley to the **6 components that matter** (pilot showed `abstain`/`check_tools`/
`transparency` ~inert; hold them ON as constants). Chain constraint `tool_restriction < single_metric
< trajectory_verify`.

- **32 coherent configs** (over the 6), **120 legal orderings** → **EXACT** restricted Shapley,
  no Monte-Carlo sampling needed. Each config's metric is cached and run once; the Shapley average
  over the 120 orderings is a cheap post-computation.
- **Questions:** the ~24 reliability-tier questions (where guardrails actually change the outcome);
  skip clean lookups every config gets right.
- **Model:** `gpt-5-mini / minimal` (the *sloppy* setting — Shapley needs errors to attribute) with
  the `gpt-5-mini / low` verifier. A second model later for robustness.
- **Value function:** run it on the confident-wrong rate (safety) and, separately, on task-success
  (correct answer ∨ correct typed refusal) — two Shapley tables, never one pooled score.

| configs × questions × reps | runs | wall-clock | cost |
|---|---|---|---|
| 32 × 12 WMS × n=1 (proof) | 384 | ~0.5 h | ~$0.15 |
| 32 × 24 reliability × n=1 (pilot) | 768 | ~1.1 h | ~$0.30 |
| **32 × 24 reliability × n=3 (standard)** | **2,304** | **~3.2 h** | **~$0.90** |
| 32 × 57 × n=3 (full — not recommended) | 5,472 | ~7.6 h | ~$2.20 |

**Recommended:** the n=1 proof (384 runs, ~30 min) to validate the Shapley pipeline, then the n=3
standard (2,304 runs, ~3 h, ~$1).

## Standing caveat

Both models tested are *careful*, so the Shapley *magnitudes* are lower-bounds — on a careless
model (or with harder traps) each control has more error to prevent, so more attributable value.
The Shapley here establishes the **ranking and mechanism**; the magnitude in the wild needs a
sloppier model. Report the n with every number.
