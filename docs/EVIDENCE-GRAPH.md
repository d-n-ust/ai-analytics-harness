# Evidence graph — the case, from first principles

`EVIDENCE-GRAPH-DESIGN.md` says what changes. This says why, and why *this* rather than something
cheaper. It starts from what the harness is for, not from the paper.

## What this instrument is for

Ranked by what the repo has actually done, not by what a README would say:

1. **Believe your own numbers.** The integrity audit exists for nothing else, and it killed v1.
   `output_validation`'s own docstring reports its measured contribution as *zero, and structurally
   so.* This is a project that would rather publish a null than an unsound positive.
2. **Attributable deltas.** One change at a time, same 57 questions, every number recomputable.
3. **A legible reference architecture.** The directory tree *is* the anatomy.
4. **Agent capability.** Last, and downstream of the other three.

Any proposal that leads with "the agent gets better" is aimed at the wrong goal. The right frame is:
*what can this instrument not currently see, and why.*

## The first-principles problem

Between a business question and an answer sit roughly eight decisions:

what the question means · whether it is answerable · which measure answers it · at what scope ·
whether the computation is right · what the number means · whether that answers what was asked ·
how confident the reader should be

Each fails independently. **The harness observes their aggregate as one bit per question** —
right / wrong / idk.

Everything downstream is machinery for recovering the information that bit threw away:

| downstream work | what it is reconstructing | how |
|---|---|---|
| `account_for` | which result the number came from | matching numbers through a rounding ladder |
| `grade_diagnostic` | whether the right driver was identified | regex over concatenated prose |
| `causal_record` | what evidence backed a causal claim | rebuilding a dossier from the tree |
| Shapley over the lattice | which guardrail contributed what | ablating across 2⁹ cells, thousands of runs |

The agent *knew* all of this at the time. It knew which result it was reporting, why it drew the
conclusion, and how strong the evidence was. **The answer protocol discards it and keeps a string
plus one optional number.** Every item above is paid effort to recover what was thrown away.

```
  WHAT THE AGENT KNOWS              THE PROTOCOL              WHAT DOWNSTREAM REBUILDS
  ─────────────────────             ──────────                ────────────────────────

  which result it read      ─┐
  which metric / scope / SQL ┤                                account_for()
  which turn established it  ┤      answer:      "…"          → guess the source by
  why it concluded           ┼───►  explanation: "…"   ───►     matching numbers
  which premises it used     ┤      value:       4133.0
  how strong the evidence is ┤      source_metric: …          grade_diagnostic()
  what it could NOT support  ─┘     source_result: r2         → regex the prose

                                                              causal_record()
   ~8 independent decisions          1 string + 1 number      → rebuild the dossier

                                                              Shapley over 2⁹ cells
                                          ↓                   → ablate to attribute

                                     one bucket
                              right / wrong / idk / …
```

Everything in the right-hand column is an attempt to read the *process* out of the *product*. The
process is not in the string.

That is the root cause. It is not a missing guardrail.

## Three symptoms, one cause — all three already documented here

**1. The diagnostic tier is provably unmeasurable.** From `harness/experiments/02_reliability_ladder/notes/integrity-audit/README.md`:

> the gold cause-word was often **already in the model's context** (a tool result or the grounding)
> before it answered — so **a keyword grader cannot tell reasoning from echo**.

No better grader fixes this. When the output is prose, the information needed to distinguish
reasoning from echo is not present in it. And this is not a minor tier — rung 6 (the metric tree) is
the README's headline capability jump, *"the jump from what was the number to why it moved."* Its
measurement is known-unsound today.

**2. The R9 judge is asked an unanswerable question.** It receives one metric, one SQL, one number,
and a narrative question. It killed 13 of 15 diagnostic and 6 of 6 keywords attempts. `RELIABILITY.md`
already diagnoses this correctly as a scope mismatch. A narrative answer is several claims; the
protocol can only hand over one.

**3. Provenance is guessed.** `after.py` argues against its own mechanism:

> Matching numbers was only ever a way to guess the same thing, and a guess needs a tolerance, and
> every tolerance is wrong for some metric.

The by-reference path (`source_result`) exists but is optional, with two fallbacks behind it.

Three symptoms, one cause: **the answer protocol is lossy.**

## What "more capable" has to mean here

Not "answers more questions." The causality runs in one direction:

**declarative capacity → measurement resolution → capability**

- The agent can *say* more about what it did (which result, from which premises, how strong).
- So failures *localize* — to a claim, an edge, a step — instead of being inferred by ablation.
- So partial answers become servable, which is the first mechanism in this repo that can raise
  coverage rather than trade it away.

Every guardrail R1–R9 slides along the coverage/risk frontier. R9 says so: *"refuse-only … it can
only add safety, never coverage."* A three-quarters-grounded answer scores zero today. Per-claim
serving is the first thing that can move the frontier outward — but that is the third-order benefit,
not the case.

**The case is that the diagnostic tier becomes measurable for the first time.**

## The constraint that decides the architecture

There is a cheap version of this: leave the run alone, and have the `answer` tool take a list of
claims with sources and premises at the end. No new tools, no in-run state, small diff.

**It does not work, and the reason is a measurement argument.** A premise declared after the
conclusion is chosen is post-hoc rationalization, and post-hoc rationalization is indistinguishable
from echo — the exact failure the integrity audit found. If the model writes its premises at the end,
we are measuring narrative fluency again, with more structure and the same blindness.

So the claims have to be made **when the evidence arrives, before the conclusion is known**. That
forces incremental construction during the run, which forces run-scoped graph state, which forces
the tool and protocol changes in the design doc. The expensive option is the only one that meets the
goal.

It also buys something the paper does not have: **construction order is evidence.** Every node
carries the turn that created it. A conclusion whose premises were established three turns earlier
had material to reason from; one whose premises appear in the same turn as the conclusion did not.
That is a free, structural echo filter — necessary rather than sufficient, but it removes the
degenerate case that currently invalidates the whole tier.

## Why not just fix the graders

Because the ceiling is set by what the agent emits, not by how cleverly it is read. A grader can only
recover information the output contains. Prose does not contain "which result this number came from"
or "which premises this conclusion rests on" — those are facts about the agent's process, and the
process is not in the string.

Every grader improvement so far has been an attempt to read the process out of the product. The
audit is the record of that failing.

## What it costs, and what it saves

**Costs:** new tools in the action space, run-scoped state, a turn budget currently capped at 8, and
grading rework. The effect will also be smaller than the paper's, because their gains come from a
trained policy and we are in the prompted regime.

**Saves:** localized failures need less ablation to attribute. Shapley over a 2⁹ lattice exists
because contribution is not observable; some of it becomes observation rather than inference. It does
not replace the interaction terms, but it shrinks what must be recovered by brute force.

## What the finished thing actually buys

The output stops being an answer and becomes a **typed analytical artifact**: N claims, each bound to
a governed result or derived from stated premises, each carrying a strength and a verdict, exportable
as PROV-O. The prose is a *view* over it rather than the thing itself.

Against the failure taxonomy of an AI analyst, honestly ledgered:

| failure | today | after | change |
|---|---|---|---|
| illegal aggregation — "monthly actives" summed from weekly | **not caught at all** | additivity + typed edge | **new, deterministic** |
| causal claim on correlational evidence | model must *say* a hedge word; regex-graded | strength inherited from the tree edge | **new, deterministic** |
| refusal contradicting own evidence (run 1) | invisible | bound claim vs refusal text | **new, deterministic** |
| stale value — cite a number a later step replaced | tolerance match may accept either | the claim names one result | **new** |
| fabricated number | R7, by number-matching + rounding ladder | binding is a lookup | exact, not heuristic |
| composed metric (ARR = mrr × 12) | R7, after the fact | metric-algebra check, at bind time | earlier, names the missing metric |
| echo — right driver because it was in context | **unmeasurable** (integrity audit) | premises + construction order | **newly measurable** |
| partially grounded narrative | all-or-nothing refusal | serve what holds | **new coverage** |
| **wrong-metric selection** | LLM judge | LLM judge | **no change** |

The last row matters. The repo's own docs call wrong-metric selection *"the hardest failure,"* and
nothing here improves it. It stays a judged opinion with a measured error rate.

### The three structural gains

**1. The judge stops being the bottleneck.** Today R9 is one LLM critic carrying every semantic
question, and `RELIABILITY.md` records that it kills 13 of 13 diagnostic answers and that rewriting
its stance is not the lever. It is overloaded because it is the only mechanism that can see meaning.
With a typed ontology, most derivation edges are settled by algebra and the judge handles only
interpretation. **The deterministic core grows and the model-judged surface shrinks** — the same move
this repo already made when it kept `governed_numbers` and `output_validation` provable.

**2. Failures localize.** One bit per question becomes a verdict per claim, and *couldn't* separates
from *wouldn't*. Attribution needs less brute force to recover.

**3. Coverage rises without risk rising.** Partial serving is the first mechanism here that moves the
frontier instead of sliding along it. The ceiling is bounded and known: the 16 answers R9 currently
converts on the published run.

### What could still go wrong

- **The model must cooperate.** Enforcement catches non-compliance by refusing, so a model that binds
  badly loses coverage. Net effect is unknown until measured.
- **Prompted, not trained.** VeriGraph's gains came from a trained policy; expect less.
- **The ontology can be wrong.** A mis-declared additivity becomes a *confident* wrong check — worse
  than no check. The declarations need their own tests.
- **Authoring burden.** Fifteen metrics here; hundreds in any real deployment.

## The one thing to do before building

Reconstruct claims post hoc from stored runs and ask whether the R9 kills are multi-claim answers
whose claims mostly *were* grounded. This needs no agent change and runs on rows already paid for.

It cannot become the architecture — it guesses provenance by matching, the shape this document
argues against — but it sizes the effect before anything is built, and it is the kind of check this
repo does before it believes itself.
