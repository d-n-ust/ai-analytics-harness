# Experiment 4 — the repair matrix

**Question:** when a question that stacks several primitives fails, which primitive broke, and what
is the cheapest location where its grounding reliably holds? Freeze the agent and the 62 questions;
vary only the warehouse it reads, one grounding location at a time; watch which failures each
location removes.

```bash
./bench study 04_repair_matrix/00_primitive_load     # the flagship study
./bench study                                        # the tree: every study in the experiment
```

The first three experiments improve the agent. This one leaves the agent alone and changes the
data under it, so every delta is attributable to the warehouse.

## The five locations, and the arm that measures each

A **primitive** is one irreducible choice a question forces (segment, grain, join path,
measure/aggregation, additivity, answerability). Its **grounding** is the business fact that
settles it. The experiment places each grounding fact in one of five locations and measures what
the agent does:

| location | the fact lives in | arm (`arms/*.yml`) | short name |
|---|---|---|---|
| implicit | nowhere — raw tables, cryptic names | `A_implicit` | raw |
| documented | prose: column comments, docs | `B_documented` | raw + docs |
| modelled | star-schema structure and clean values | `C_modelled` / `C_modelled_documented` | star / star + docs |
| declared | a governed metric definition (MetricFlow) | `D_declared` | + semantic |
| enforced | a runtime rule the agent cannot bypass | `E_enforced` | + guardrails |

`E_enforced_verified` (short name: + LLM judge) re-runs the enforced arm with an answer judge. It
is a probe, not a verifier measurement — the judge was mis-briefed by design; see study FINDINGS
§31.7.

## The bench

62 items × 3 repetitions × 8 arms = 1,488 graded rows (run `20260810-181508`). 48 items are
answerable ladders that stack primitives rung by rung; 12 have no answer in the data; 2 are
controls. Repetition disagreement puts the noise floor at 25%, so single-cell differences are not
read, only patterns that repeat across a column or a family.

Headline metrics per arm, whole exam:

| arm | coverage | silent error | balanced accuracy | governed use |
|---|---|---|---|---|
| raw | 97% | 47% | 48% | — |
| raw + docs | 99% | 49% | 52% | — |
| star | 95% | 18% | 73% | — |
| star + docs | 99% | 9% | 85% | — |
| + semantic | 100% | 17% | 78% | 74% |
| + guardrails | 99% | 5% | 95% | 100% |
| + LLM judge | 71% | 2% | 82% | 100% |

## The matrix

Per primitive family, the cheapest location where the grounding measured reliable:

| primitive family | cheapest reliable location | the fix |
|---|---|---|
| segment: filter | documented | document the default and the meaning |
| segment: member | modelled | clean key plus readable label |
| grain | modelled | named-grain table and separate counts |
| join path | modelled | label on the dimension already queried |
| additivity | **enforced** | snapshot plus enforced metric route |
| answerability | **enforced** | coverage lookup plus refusal check |

Spending to the right of a row's check bought nothing measurable. The two bold rows are the
exceptions that define the experiment: no amount of modelling or documentation fixed them.

## What held across a model-tier sweep

Run `20260811-211447` repeats seven arms on `gpt-5.6-terra` (study FINDINGS §32). The findings
split cleanly:

- **Model-independent — properties of the data.** The prose arms scored 0 on additivity at both
  tiers (no model read the ÷12 rule out of a comment and applied it to arithmetic). The star's
  normalised values trap both models into writing `'Android'` against a column holding `android`.
  Misleading documentation hurts the stronger model more.
- **Model-dependent — properties of the agent.** The honesty flatline (36–47% refusal without
  enforcement) is a small-model property; the frontier model brings its own restraint.
  Enforcement calibrated for the weaker agent becomes a coverage tax on the stronger one.

The practitioner sentence: fix the data, not the model, because the data fixes are the ones the
next model upgrade does not refund — and re-cost the controls per tier.

## Where the detail lives

- `experiments/04_repair_matrix/00_primitive_load/FINDINGS.md` — the study ledger. §31 is the
  rebuilt instrument (nothing before it is comparable); §32 is the model-tier sweep.
- `experiments/04_repair_matrix/00_primitive_load/PRACTITIONER-NOTES.md` — the summary for a
  reader without this repository.
- `experiments/04_repair_matrix/experiment.yml` — the manifest: status, evidence paths, how runs
  are driven.

Companion essay on decisionspine.com: *The AI-Readiness Repair Matrix* (in draft).
