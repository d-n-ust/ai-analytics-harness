# Experiment 2 — the reliability ladder

**Question:** the grounding ladder makes the agent *capable*; how many *guardrails* does it take to
make it *trustworthy* — answer when the data supports it, and **refuse with a typed reason** when it
does not, instead of serving a confident wrong number?

```bash
bench run --rungs 3 --rrungs 0,1,2,3,4,5,6,7,8,9    # hold grounding fixed, climb the guardrail ladder
bench run --rungs 3 --cells R9,R9-resolve            # any ablation cell (leave-one-out, Shapley, …)
```

## The ladder (R0–R9)

Each rung switches on one control. The set of controls that are on is one `Guardrails` value
(`agent/guardrails.py`) — a ladder preset (`LADDER[n]`) and an arbitrary ablation cell are the same
primitive, so any coherent configuration is expressible and self-describing.

| rung | guardrail | what it stops | where it runs |
|---|---|---|---|
| R0 | — | (baseline: must answer, no refusal channel) | — |
| R1 | `abstain` | adds the typed `refuse` tool (coded reason + what's missing) | prompt + protocol |
| R2 | `check_tools` | answerability checks the model may call first | tools |
| R3 | `gate` | blocks out-of-coverage / ungoverned governed calls | **input** (pre-execution) |
| R4 | `tool_restriction` | the *fence* — removes raw SQL; governed metrics only | **input** |
| R5 | `resolve` | filter values must resolve to a governed member | input (query-time) |
| R6 | `transparency` | shows the compiled SQL + a plain scope line | output (soft) |
| R7 | `single_metric` | the served number must **be** one governed result | **output** (`agent/verifier.py`) |
| R8 | `output_validation` | the value must be well-formed (non-empty, in range) | **output** |
| R9 | `trajectory_verify` | an LLM critic checks the metric actually answers the question | **output** |

Input guardrails (R3–R5) stop a bad number being **computed**; output guardrails (R7–R9) stop one
being **served**. The gate and the fence are *structural* — they hold regardless of what the model
does, and are proven exhaustively without an LLM (`tests/test_structural.py`).

## The typed refusal protocol

Every run ends through exactly one terminal tool — `answer` / `refuse` / `clarify` — so the outcome
is a typed field, never a phrase to grep. A refusal carries a **coded reason** from a governed
vocabulary (`REFUSAL_REASONS` in `agent/tools.py`) and names the specific missing thing. This is
selective prediction *extended with a typed reject option*: we score not just *that* it abstained,
but *which* reason and whether it was the right one.

## Wrong-metric detection is now the LLM verifier

The hardest failure is a **real, correctly-computed** metric that answers a *slightly different*
question (active users reported as the user total). Two mechanisms once guarded this: a deterministic
4-slot spec comparison and an LLM **trajectory verifier**. The deterministic 4-slot subsystem has
been **retired** — the trajectory verifier subsumes it. So wrong-metric selection is now judged
*entirely by one LLM critic* (`agent/verifier.py`): it inspects the metric, its definition, the
compiled SQL, and the analyst's added filters, and finds a concrete reason the number does not answer
the question (THING / KIND / SCOPE / DEFINITION / SEGMENT). It is refuse-only — it can downgrade a
confident answer, never rescue a refusal, so it can only add safety.

**This trades a provable guarantee for a measured rate.** The verifier is therefore validated against
held-out human labels, and its error rate is a **standing, first-class number** — revalidated
whenever its prompt changes. A refuse-only critic you cannot score is just another opinion.

The deterministic core that *survives* is the provenance / single-metric check (R7) and the
output-validation check (R8) — both live in `agent/verifier.py` alongside the trajectory judge, and
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
