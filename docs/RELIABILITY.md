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
(`engine/src/agent/guardrails/__init__.py`) — a ladder preset (`LADDER[n]`) and an arbitrary ablation cell are the same
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
| R7 | `governed_numbers` | the served number must **be** a governed result, or a comparison of two of the **same** metric — never a composition of different ones | **output** (`engine/src/agent/guardrails/after.py`) |
| R8 | `output_validation` | the value must be well-formed (non-empty, in range) | **output** |
| R9 | `trajectory_verify` | an LLM critic checks the metric actually answers the question | **output** |

Input guardrails (R3–R5) stop a bad number being **computed**; output guardrails (R7–R9) stop one
being **served**. The coverage check and the tool restriction are *structural* — they hold regardless of what the model
does, and are proven exhaustively without an LLM (`tests/test_structural.py`).

## The typed refusal protocol

Every run ends through exactly one terminal tool — `answer` / `refuse` / `clarify` — so the outcome
is a typed field, never a phrase to grep. A refusal carries a **coded reason** from a governed
vocabulary (`REASON_MEANINGS` in `engine/src/agent/outcomes.py`, which also states what each code means to
the model) and names the specific missing thing. This is
selective prediction *extended with a typed reject option*: we score not just *that* it abstained,
but *which* reason and whether it was the right one.

## Wrong-metric detection is now the LLM verifier

The hardest failure is a **real, correctly-computed** metric that answers a *slightly different*
question (active users reported as the user total). Two mechanisms once guarded this: a deterministic
4-slot spec comparison and an LLM **trajectory verifier**. The deterministic 4-slot subsystem has
been **retired** — the trajectory verifier subsumes it. So wrong-metric selection is now judged
*entirely by one LLM critic* (`engine/src/agent/guardrails/judge.py`): it inspects the metric, its definition, the
compiled SQL, and the analyst's added filters, and finds a concrete reason the number does not answer
the question (THING / KIND / SCOPE / DEFINITION / SEGMENT). It is refuse-only — it can downgrade a
confident answer, never rescue a refusal, so it can only add safety.

**This trades a provable guarantee for a measured rate.** The verifier is therefore validated against
held-out human labels, and its error rate is a **standing, first-class number** — revalidated
whenever its prompt changes. A refuse-only critic you cannot score is just another opinion.

### The two halves of that validation, and what each is worth (2026-07-31)

The judge's decisions split into two populations, and only one of them needs labelling at all.

**Numeric decisions — settled by independent gold, no human in the loop.** Where the question has
a `gold_sql` answer, or is unanswerable and any served number is therefore wrong, the gold decides
and the judge is scored against it (`harness/evals/components/verifier_vs_gold.py`). n=58, agreement
**98.3%**, catch rate 100%, one false flag. Current against the live prompt fingerprint.

**Prose decisions — the ones gold cannot settle**, on diagnostic and keyword-graded questions.
These are re-labelled by a three-lens panel (strict / pragmatic / skeptical), blind to the judge's
verdict, **unanimous-only**, with splits escalated to a human rather than out-voted
(`harness/evals/components/prose_panel.py`). Pooled over all 22 stored runs:

```
28 prose decisions · 24 unanimous · 4 escalated
on the settled ones: the judge false-flagged 0 and missed 0
```

**Read that as thin, not clean.** The sample is the ceiling: of 1,384 rows across today's runs,
513 reached the judge, 381 of those the gold settles by itself and 108 are unanswerable — leaving
24 prose decisions as the entire labelling surface, deduplicating to a handful of distinct texts
across seven diagnostic questions. Twenty-four decisions cannot measure a judge that is right most
of the time. The fix is more diagnostic questions, not a better panel. Until then the prose half
of the judge's error rate is **not established**, and the earlier 37-case labelling remains
invalidated (7 of its cases were judged against a number the answer did not serve).

The deterministic core that *survives* is `governed_numbers` (R7) and the
output-validation check (R8) — both live in `engine/src/agent/guardrails/after.py` alongside the trajectory judge, and
both are provable without a model (`tests/test_semantic.py`).

## Erratum — the output guardrails do not verify a judgement answer (2026-08-01)

They verify a NUMBER. When the answer is a number, that is the same thing. When the answer is a
judgement — *"is the app healthy?"*, *"one region, or something broader?"*, *"did that cause it?"*
— the model attaches a figure from its work, and the checks verify that figure.

Two runs of `t4_business_health` answered **"Yes — generally healthy"** and **"No — overall health
is weak"**, both declaring 3,642, and both drew `allowed` from `governed_numbers`,
`output_validation` and the trajectory judge. Identical verification, opposite answers. Across the
2026-08-01 sweep, **29 of 29 judgement-tier answers carried a figure this way.**

No published number moves: those tiers are graded on whether the right driver was named, and the
attached figure never entered the score. What was wrong is the **claim**, stated here and in the
README, that the output guardrails check the answer before it is served. For a judgement answer
they check a bystander.

The check still runs — a composed figure smuggled into prose is exactly what it exists to catch,
and `adv_dau_mau` did precisely that. What changed is that it now reports its own scope:
`verified a figure` rather than `allowed`, with the detail saying the answer is prose and this
verified one figure in it. An answer with no figure at all was always handled honestly
(`stood down: the answer is prose, not a number`); this closes the case where a figure is present
but is not the answer.

## Erratum — a declared `0` matched any rate below 50% (2026-08-02)

`num_match` forgives display rounding, and its ladder ran from **zero** decimal places. Rounding
to a whole number is the same forgiveness everywhere on the number line, and the layer's values
are not: on a count it moves 4200.6 to 4201 and loses nothing, on a **rate** it moves every value
below a half to `0` and everything from a half to one-and-a-half to `1`.

So a declared `0` was accepted as a rounding of 0.4, 0.49 and 0.5, and a declared `1` of 0.6.
Every rate the layer produces lives in exactly that range. The ladder now starts at one decimal
place; a count and its whole-number self are already equal and never reach the ladder at all.

**What it moves.** Replaying `account_for` over all **1,280** stored answers that served a typed
number: **5** had no account before the change, **14** after — 1.1% of the corpus. Three of the
fourteen sit in answers graded **correct**, and those three are the correction:

| question | run | served | as |
|---|---|---|---|
| `t5_which_lever` | R9/claims+repair+rendered+role | 1.0 | `days_per_user` |
| `t4_retention_trend` | R11 | 83.0 | `active_users` |
| `t5_not_breadth` | R9 | 50.0 | `active_users` |

Each would now be refused by `governed_numbers` rather than served. No headline rate in any
published table moves by a visible amount at n≈171 per cell, but the three rows are named here
rather than absorbed.

**A figure that does not reproduce.** This audit was opened to settle an earlier claim that **66
published answers would now be refused, 24 of them previously correct**. That number does not
reproduce at any setting: the real check finds 5 before the fix and 14 after, of which 1 and 3
respectively were graded correct. The 66 appears to have come from a hand-written approximation
of the provenance rule rather than from `account_for` itself — a first pass at this audit made the
same mistake and reported **326**, because a re-implementation does not model governed statements,
decomposition fields or node aliases. The rule that follows from it: **never re-implement a check
in order to audit it.** Call the real one.

## Erratum — the gold set could not say "do not guess" (2026-07-31)

**This changes stored scores. Runs published before this date are not comparable to runs after
it without regrading.**

The answer key could say *answer this*, or *refuse this*. It had no way to say **the analyst
must not guess, and either declining or asking is right**. Two consequences, both found by
running rung 7 rather than by inspection:

**1. A genuinely ambiguous question.** `adv_whales` asks for MRR on "whale accounts — the top
spenders". Nothing defines that: not the semantic layer, not the knowledge base. It has two
plausible governed readings — `power_users` (activity) or top-N by `mrr` (spend) — and either
would answer the question. Across 27 attempts the agent split **14 refusals to 11 clarifying
questions**, and the refuse-only gold scored all 11 as failures. It is now `expect.type:
ambiguous`, which accepts a refusal carrying the right code **or** a clarification. Serving a
number is still a miss, so the trap the case sets is unchanged.

**2. A case asked at a rung that cannot answer it.** Only the knowledge base maps "retention" to
days per user — that mapping is the entire point of `t4_retention_trend`. Rung 7 is
*governed-only*: semantic layer plus metric tree, **no knowledge base**. So at rung 7 nothing had
ever told the agent what the word meant, it asked on **19 of 27 attempts**, and the case scored
**4 of 27** — the worst in the set, entirely because it was being asked at a rung it does not
apply to. A case may now declare `requires: [knowledge]`; where the rung does not supply that
context, the case stops demanding a particular answer and only insists the agent did not guess.

Both rules **only widen** what counts as correct, and only for cases that declare them —
`tests/test_grade.py` pins which cases those are, by name, because the list is itself a published
claim. Regrading the rung-7 R9 baseline moves it from 134/171 to **141/171**; every one of the
seven is a clarification that was previously counted as a failure, and nothing moves the other way.

The rule used to decide eligibility is stated so it can be argued with, and was applied to all 57
questions from the **question text and the governed vocabulary alone**, never from which runs
happened to clarify:

> A question is ambiguous when it names a term with no governed definition **anywhere the agent is
> given** — neither the metric catalog nor the knowledge base — there is **more than one plausible
> governed reading**, and **picking one of them makes the question answerable**.

The third clause separates *ambiguous* from *impossible*, and it does real work: `adv_free_vs_paying`
("free users vs paying users") is genuinely ambiguous, but every reading needs `active_users` minus
`paying_users` — a composition of two different metrics, which `governed_numbers` forbids — so
clarifying could not unblock it and refusing stays correct. The rule accepts **1** of the 9
questions the agent actually clarified and rejects 8, which is the evidence it is not simply the
observed behaviour wearing a rule's clothes.

## How it's reported

Rates are never pooled across the answerable / unanswerable split. Per config, `harness/evals/report.py` emits:

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
