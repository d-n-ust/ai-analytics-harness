# Experiment 2 — the reliability ladder

**Question:** the grounding ladder makes the agent *capable*; how many *guardrails* does it take to
make it *trustworthy* — answer when the data supports it, and **refuse with a typed reason** when it
does not, instead of serving a confident wrong number?

```bash
bench run --rungs 3 --rrungs 0,1,2,3,4,5,6,7,8,9    # hold grounding fixed, climb the guardrail ladder
bench run --rungs 3 --cells R9,R9-resolve            # any ablation cell (leave-one-out, Shapley, …)
```

## The ladder (R0–R9)

Each rung switches on one guardrail. The set that is on is one `GuardrailSet` value
(`agent/guardrails/__init__.py`) — a ladder preset (`LADDER[n]`) and an arbitrary ablation cell are the same
primitive, so any coherent configuration is expressible and self-describing.

| rung | guardrail | what it stops | where it runs |
|---|---|---|---|
| R0 | — | (baseline: must answer, no refusal channel) | — |
| R1 | `abstain` | adds the typed `refuse` tool (coded reason + what's missing) | prompt + protocol |
| R2 | `check_tools` | answerability checks the model may call first | tools |
| R3 | `coverage_check` | blocks out-of-coverage / ungoverned governed calls | **input** (pre-execution) |
| R4 | `tool_restriction` | removes raw SQL; every data path is a governed call | **input** |
| R5 | `resolve` | filter values must resolve to a governed member | input (query-time) |
| R6 | `transparency` | shows the compiled SQL + a plain scope line | output (soft) |
| R7 | `governed_numbers` | the served number must **be** a governed result, or a comparison of two of the **same** metric — never a composition of different ones | **output** (`agent/guardrails/after.py`) |
| R8 | `output_validation` | the value must be well-formed (non-empty, in range) | **output** |
| R9 | `trajectory_verify` | an LLM critic checks the metric actually answers the question | **output** |

Input guardrails (R3–R5) stop a bad number being **computed**; output guardrails (R7–R9) stop one
being **served**. The coverage check and the tool restriction are *structural* — they hold regardless of what the model
does, and are proven exhaustively without an LLM (`tests/test_structural.py`).

## The typed refusal protocol

Every run ends through exactly one terminal tool — `answer` / `refuse` / `clarify` — so the outcome
is a typed field, never a phrase to grep. A refusal carries a **coded reason** from a governed
vocabulary (`REASON_MEANINGS` in `agent/outcomes.py`, which also states what each code means to
the model) and names the specific missing thing. This is
selective prediction *extended with a typed reject option*: we score not just *that* it abstained,
but *which* reason and whether it was the right one.

## Wrong-metric detection is now the LLM verifier

The hardest failure is a **real, correctly-computed** metric that answers a *slightly different*
question (active users reported as the user total). Two mechanisms once guarded this: a deterministic
4-slot spec comparison and an LLM **trajectory verifier**. The deterministic 4-slot subsystem has
been **retired** — the trajectory verifier subsumes it. So wrong-metric selection is now judged
*entirely by one LLM critic* (`agent/guardrails/judge.py`): it inspects the metric, its definition, the
compiled SQL, and the analyst's added filters, and finds a concrete reason the number does not answer
the question (THING / KIND / SCOPE / DEFINITION / SEGMENT). It is refuse-only — it can downgrade a
confident answer, never rescue a refusal, so it can only add safety.

**This trades a provable guarantee for a measured rate.** The verifier is therefore validated against
held-out human labels, and its error rate is a **standing, first-class number** — revalidated
whenever its prompt changes. A refuse-only critic you cannot score is just another opinion.

The deterministic core that *survives* is `governed_numbers` (R7) and the
output-validation check (R8) — both live in `agent/guardrails/after.py` alongside the trajectory judge, and
both are provable without a model (`tests/test_semantic.py`).

## How it's reported

Rates are never pooled across the answerable / unanswerable split. Per config, `evals/report.py` emits:

- a **selective-prediction operating point** — coverage (share answered) and risk (error among
  answered); the ladder traces a *frontier* as guardrails tighten (not a threshold-swept curve, so no
  AURC headline).
- the **three correctness axes**, kept separate — groundedness (computed not invented) · answer-
  correctness (right value) · answer-relevancy (answers the asked question).
- the **failure-mode reason pivot** — refusals by coded reason, split matched / wrong-reason /
  over-refused.
- **two-level agent metrics** — the per-tool call profile (call-level) + the trajectory verdicts
  (task-level).

`summary.json` is the machine-readable contract; `summary.md` is the human view. The confusion counts
are primary; the cost-weighted `score` is one derived view with its cost stated.

## What the verifier actually fires on (2026-07-26)

Two questions were asked of the R9 judge. One had a negative answer; the other found
something the ladder's framing hides.

**Is the asymmetric stance what makes it fire?** Its opening paragraph tells it to find a
reason to reject and to pass only if it fails — chosen to resist sycophancy, but also a known
over-rejection instruction. Run as a two-level treatment (`VERIFIER_STANCE`), R9 at rung 5,
gpt-5-mini, 57 questions × 3 reps per arm:

| stance | fired | coverage | precision | grounded |
|---|---|---|---|---|
| `skeptical` (shipped) | 37/91 = 41% | 72% | 100% | 99% |
| `even_handed` | 29/83 = 35% | 72% | 98% | 100% |

Two-proportion z = 0.78 — not significant at this n. **Rewriting the stance is not the lever.**

**What it fires on is the finding.** Of the 19 answerable attempts the skeptical judge killed,
none was a `metric_answer` question. All 19 were `diagnostic` or `keywords` — 13 of 15
diagnostic attempts and 6 of 6 keywords. The even-handed arm has the same shape.

That is a scope mismatch rather than a calibration problem. The judge is handed a metric, its
compiled SQL and one number, and asked whether that number answers the question. For a numeric
lookup that is the right frame. For *"why did weekly value moments drop"* it is the wrong one:
the answer is a narrative, so a judge looking for the metric that answers the question will
always find that none does.

It is also where the published coverage cliff comes from. On the article's own run (rung 3),
R8 → R9 loses **13 of 13** diagnostic answers and **3 of 3** keywords answers — every one —
alongside 12 of 52 numeric. The piece reads that cliff as the price of safety; part of it is
the verifier judging question types it was never designed for.

**Open, and needing a matched pair to settle.** "Did a kill destroy a correct answer" cannot be
scored from these rows: diagnostic and keywords questions carry no numeric gold, so the
comparison is silent rather than reassuring. Settling it needs R8 and R9 run over the same
questions and reps, so each conversion has its own counterfactual.
