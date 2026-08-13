# The trust model — what a claim's support is worth

Companion to `EVIDENCE-GRAPH-DESIGN.md`, which says what the graph *is*. This says what it
**measures**, why those measurements do not merge with the ones already published, and what would
have to be true before any of it is called confidence.

## Two families, and why they must not be merged

Every metric this harness publishes today shares one property:

```
coverage · silent error rate · balanced accuracy   →   ALL require gold
```

They are computable only because we wrote the questions *and* the answers. They are lab
instruments. On a client's question there is no gold, ever, so none of them can be computed where
it would matter most.

Every claim metric has the opposite property. `bound`, `mislabelled`, `unresolved`, evidence
concentration — none needs gold. Each is a lookup against the certified model and the trace, at
answer time, on a question nobody has an answer key for.

|                        | the published three | the claim metrics |
|---|---|---|
| needs gold             | yes                 | no                |
| available in production| never               | always            |
| answers                | *was it right?*     | *is it supportable?* |

So they are not two views of one thing, and averaging them into a single score produces a number
that means neither. **They stay separate.**

### The bridge is calibration, not definition

A claim metric is worth exactly what it PREDICTS about the gold metrics. That is an empirical
question, and both sides are already stored on every row.

It also has a precise shape. A trust threshold — *"serve only when the weakest claim is exact"* —
is another **operating point on the same coverage/risk frontier** the guardrail ladder traces. R7
is a point on it. R9 is a point on it. A trust rule is a point on it. Same axes, directly
comparable, so this work lands on the chart we already publish rather than beside it.

## What can be wrong with an assertion

Not "what would be nice to measure" — what are the ways an assertion in an analytical answer can
fail? There are seven, and each is a lookup against one layer of the certified stack.

| # | the failure | checked against |
|---|---|---|
| 1 | the number does not exist — invented | **semantic layer** — is it a governed result? |
| 2 | it exists but is not what it is called | **semantic layer** — does the claim's metric match the result's? |
| 3 | the operation on it is not legal | **ontology** — additivity, unit, ratio legality |
| 4 | the relation asserted is not in the model | **metric tree** — identity edge / influence edge + confidence / no edge |
| 5 | the scope does not match the question | **coverage + filters** |
| 6 | the support is thin | **trace** — how many independent calls |
| 7 | the conclusion does not follow from its premises | **the claim graph itself** |

None of these needs a judge, because the stack already declares what each one needs. A metric
carries `unit`, `agg`, `additive_over_time`, `dimensions`. The tree carries
`type: identity, op: multiply` and `type: influence, confidence: low, evidence: "…"`. The checks
read what governance already states rather than forming an opinion about it.

## The trust ladder

Each claim is assigned the **strongest warrant that licenses it**:

```
L3  CERTIFIED               the value IS a governed result, correctly named, at the scope asked.
                            The layer computed it; nothing was done to it.

L2  DERIVED-EXACT           produced from governed values by an operation the ontology licenses:
                            an identity share from the tree, a same-metric comparison, a total
                            over a metric declared additive. Arithmetic the model did not do.

L1  DERIVED-CORRELATIONAL   rests on an influence edge the tree declares, carrying its stated
                            confidence and evidence. Evidence, never proof.

L0  UNWARRANTED             no resolvable support, or an operation nothing licenses — composing
                            two different metrics, summing a non-additive measure, asserting
                            cause across a correlational edge.
```

Which reads out as three bands:

```
trusted        L3 + L2      act on it
questionable   L1           act on it knowing what it rests on
ungrounded     L0           do not act on it
```

The level is **computed, not judged**. That is the property that makes it a guarantee rather than
an opinion, and it is the standard the rest of the harness already holds itself to: a hedge is
correlational because the tree says `confidence: low`, not because the model chose a soft word.

## Propagation: node, branch, answer

- **node** — its own level, as above.
- **branch** — the **minimum** level along the path to it. The weakest link governs, which is why
  one correlational premise makes the whole conclusion correlational. This is the min semiring;
  the boolean one (grounded / not) reads the same graph for a different question.
- **answer** — evaluated over **terminal claims only**, so a leaf counts once as support and not
  again as a finding. That is what stops a wall of easy lookups outweighing the one claim that
  carries the argument.

### Why the answer level is not one number

An answer with six certified claims and one unwarranted one is not "86% trustworthy." It is
*mostly solid, with one thing in it nobody should act on*. Averaging destroys exactly the
information the reader needs, and it ranks a list of lookups above an argument.

The answer-level output is a **band distribution with the weakest commitment as the headline**:

```
ANSWER TRUST     weakest commitment: correlational
  trusted 5  ·  questionable 1  ·  ungrounded 1
```

If a single number is needed for a surface that cannot show three, it is **evidence coverage** —
the share of TERMINAL claims at L2 or above. It counts commitments rather than averaging quality.
It must not be published as a confidence or a probability until the calibration below succeeds;
an uncalibrated 0.85 looks like a probability and is not one, which is the failure this practice
exists to name in other people's work.

## Calibration — the only thing that makes any of it real

The question: **does a worse claim profile predict a worse answer?**

Measured on run `20260730-133027` (rung 7 · R11 · gpt-5-mini @ minimal · 171 rows), over the 67
answered rows that declared claims:

| claim profile | n | correct | wrong-number rows |
|---|---|---|---|
| all bound, correctly labelled | 47 | 100% | 0 |
| all bound, mislabelled | 12 | 92% | 0 |
| **has an unresolved citation** | **8** | **62%** | **2** |

Monotonic, in the predicted direction. Incorrect rate is **38% with an unresolved citation against
1.7% without** — Fisher exact, one-sided, **p = 0.0044**.

### The caveat that matters more than the p-value

**The whole run contains four incorrect answered rows.** A result resting on four errors is a
direction to investigate, not a finding to publish, however small the p-value. The guardrails have
done their job so thoroughly that the error variance calibration needs has been removed at the top
of the ladder.

So the calibration experiment must run **down** the ladder, not at the top: R1–R5, where wrong
answers are plentiful, and where the question becomes answerable at a useful n. That is the
experiment, and it is cheap — the claim audit is a pure lookup, so it costs one sweep and no
judging.

## What is computable today

| level | status | needs |
|---|---|---|
| L3 vs L0 — bound, mislabelled, unresolved | **shipped** (R11) | — |
| evidence concentration | **shipped** | — |
| **L2 vs L1** | **shipped** | — |
| operation legality (failure 3) | partial — `additive_over_time` only | unit + ratio rules |
| scope match (failure 5) | no | scope declared on the claim |

The middle row was the point of this document, and it has since landed. **The trusted /
questionable split could not be computed until a claim could name its warrant**, and a warrant
only exists once a claim can cite another claim rather than a value. `premises` gives it that:
a claim citing `["c1","c2"]` is a conclusion, its strength is the **minimum** over its premises,
and `correlational` vs `exact` is read off the metric tree's edge types rather than chosen by
the model. Backwards-only, so the graph cannot cite in a circle.

What it measures, over today's runs (743 audited rows, 1,712 claims): **7.4% of claims are
derived** under the rule framing and **13.6%** under the role framing — that is, most of what an
analytical answer asserts is still a lookup rather than an argument. `max_depth` is 1 on every
run so far: no conclusion yet rests on another conclusion.

## What still stands between this and a trust level

The audit produces the inputs. It does not yet produce the ladder — nothing computes L3/L2/L1/L0,
the band distribution, or the answer-level headline described above. That work, and the package
it belongs in, are set out in `docs/ARCHITECTURE.md`: the claim audit is an **instrument**, not a
guardrail, and a trust profile computed inside `engine/src/agent/guardrails/` would be a verdict wearing a
measurement's clothes.
