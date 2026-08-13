# The three axes — grounding, guardrails, protocol

Status: **steps 1–3 landed 2026-07-31, and the declarations are now off the ladder entirely;
steps 4–5 outstanding.** Extends the 2026-07 refactor plan (formerly `REFACTOR.md`, removed
2026-08; everything from it that still matters is restated where it is used).

The refactor plan diagnosed the repo as running **two experiments packaged as one** — the grounding
ladder and the reliability ladder — and said to name them as first-class peers. That diagnosis
was right and is now incomplete. There is a **third** axis, it has been arriving one commit at a
time since `declared_purpose`, and it is currently filed under the second one.

This document names it, says why it is not a guardrail, and says where it goes.

---

## The three axes

| axis | the question it varies | primitive | lives in |
|---|---|---|---|
| **grounding** | what the agent **knows** | `rung` 1–7 | `engine/src/agent/rungs.py`, `engine/src/agent/grounding.py` |
| **guardrails** | what the agent **may do** | `GuardrailSet` R0–R9 | `engine/src/agent/guardrails/` |
| **protocol** | what the agent must **declare** | `Protocol` | `engine/src/agent/protocol.py`, `engine/src/evidence/` |

Each is independent in the sense that matters for an experiment: hold two fixed, move the third,
and the run means something. That is what makes it an axis rather than a setting.

The third axis has a property the other two do not, and it is the reason it is worth the
restructuring:

```
grounding and guardrails are scored by metrics that need GOLD.
protocol is scored by metrics that need NONE.
```

Coverage, silent-error rate and balanced accuracy exist only because we wrote the questions *and*
the answers. They are lab instruments and always will be. Every protocol metric — is each
assertion bound, is any citation unresolved, is the conclusion derived, how weak is the weakest
link — is a lookup against the certified model and the trace. It computes on a client's question,
at answer time, with no answer key. `docs/TRUST-MODEL.md` argues at length why the two families
must never be averaged; this document is the structural consequence of that argument. **Two
families of metric that cannot be merged should not be produced by one package.**

---

## Why protocol is not a guardrail

`engine/src/agent/guardrails/__init__.py` classifies guardrails by `Position`, and the docstring is explicit
that the classification is by **failure mode**, because failure mode is what predicts behaviour:

```
ACTION_SPACE  the request cannot be expressed at all
BEFORE        expressible, but it does not run
DISCLOSURE    prevents nothing; carries information
AFTER         the number exists; the question is whether it is served
```

`claims` is filed under DISCLOSURE, alongside `transparency` and `declared_purpose`. That is the
closest available box and it is still wrong, because DISCLOSURE describes something that carries
information *and does nothing with it*. Claims are read: by a correction loop that hands the
answer back, by an audit that scores it, and — in the design `TRUST-MODEL.md` sets out — by a
trust profile served to a human. A category whose defining property is inertness cannot hold the
one member that is load-bearing.

### One flag doing four jobs

The concrete evidence that the seam is real: `GuardrailSet.claim_binding` is a single boolean
switching on four things of three different kinds.

| what it switches on | where | kind |
|---|---|---|
| `claims` added to the answer schema | `agent/guardrails/action_space.py:190` | **treatment** — the model sees it |
| the prompt paragraph asking for them | `agent/prompts.py:209` | **treatment** — the model sees it |
| reject-and-retry on an unresolved citation | `agent/loop.py:156` | **enforcement** — changes the run |
| the audit stored on the row | `agent/loop.py:244` | **measurement** — changes nothing |

Three live consequences:

**1. R11 cannot be ablated, so its effect cannot be attributed.** *(Fixed in step 2.)* Turning `claim_binding` off
removes the schema field, the prompt, the correction loop and the audit together. The correction
loop demonstrably changes runs — across today's 743 audited rows, **41 needed at least one
correction** (38 needed one, 3 needed two), and a correction on the closing turn buys an extra
iteration. So R11's effect on coverage and accuracy is a compound of a treatment and an
enforcement, and the ladder reports it as one rung. This is exactly the failure `incoherent()`
exists to prevent for every other cell.

**2. A treatment variable lives in an environment variable.** *(Fixed in step 3.)* `CLAIM_FRAMING=rule|role`
(`agent/prompts.py:142`) changes the model-visible prompt and is stamped on every row
(`evals/runner.py:97`), but is not part of any config primitive, does not appear in
`GuardrailSet.label()`, and cannot be named in `--cells`. It is a real, measured treatment — role
framing roughly doubles the share of claims that are conclusions rather than lookups:

| framing | rows | claims | bound | derived | correlational |
|---|---|---|---|---|---|
| rule | 209 | 450 | 89.6% | 6.9% | 56 |
| role | 208 | 558 | 90.1% | **13.6%** | 61 |

A variable that moves a headline number by 2× and cannot be written into a cell spec is the
single-primitive problem the refactor plan's Workstream B existed to solve, reintroduced.

**3. The dependency points the wrong way.** *(Fixed in step 1.)* `agent/guardrails/claims.py` is a pure function over
a trace — no model, no tolerance, no policy. Anything that wants to read an evidence graph (the
trace renderer, the report, a future client-facing surface) must import the guardrail package to
get it. The audit is an instrument, and instruments do not belong inside the thing they measure.

### The position that is actually missing

Handing a malformed answer back is not any of the four positions. It is not ACTION_SPACE (the
call was expressible), not BEFORE (it already ran), not DISCLOSURE (it is not inert), and the
`Position` docstring rules out AFTER in as many words: *"Can only refuse, never rescue."* The
correction loop rescues — the answer is neither served nor refused; the fault is named and the
run continues.

So the classification needs a fifth member, and naming it is most of the design:

```
REPAIR        the answer is not served and not refused — it is handed back with the fault
              named, and the run continues. The first position that can rescue. Fails by
              looping, so it is bounded (MAX_CORRECTIONS = 2) rather than trusted.
```

This is not bookkeeping. `Position` predicts how a guardrail fails; a repair guardrail fails by
consuming the budget, which no other position can do, and which is why `loop.py` had to grow a
GRACE turn to keep a correction from costing the run its answer.

---

## Target structure

Following the refactor plan's rule — organize by layer of the stack, so the directory tree *is* the
reference architecture:

```
evidence/                what an answer committed to, and whether it holds
  claims.py              ✅ claim identity + the binding audit  (moved from agent/guardrails/)
  values.py              ✅ num_match — is this figure that governed value
  strength.py            ⬜ warrant levels; min-semiring propagation over premises
  trust.py               ⬜ the answer-level trust profile      (docs/TRUST-MODEL.md)
agent/
  protocol.py            ✅ what an answer must DECLARE — the third primitive
  guardrails/            ✅ unchanged, minus claims.py; consults evidence/ for num_match
```

`engine/src/evidence/` sits beside `engine/src/warehouse/` and `engine/src/semantic/`, not inside `engine/src/agent/`, and it has the same
shape as `engine/src/semantic/`: it reads a certified model plus a trace and returns facts. **It decides
nothing.** `audit()` already holds that property — it returns findings and never refuses — and
making it structural is what stops it drifting into a judge the first time a check is
inconvenient. It is also what makes it publishable: a component that renders no verdict can be
handed to a reader who does not trust us.

Dependency direction, stated so it can be tested:

```
evidence/          →  semantic/  +  a trace.        Never agent/.
agent/guardrails/  →  evidence/  (may consult)
agent/protocol.py  →  nothing (booleans + schema fragments)
evals/             →  evidence/  (for reporting)
```

### The third primitive

As shipped:

```python
@dataclass(frozen=True)
class Protocol:
    """What an answer must declare about itself. A peer of GuardrailSet, not a part of it."""
    purpose: bool = False   # `because` on every governed call
    claims: bool = False    # one declaration per assertion, each naming the value it rests on
    repair: bool = False    # a citation that names nothing is handed back, bounded
    framing: str = RULE     # how the account is asked for: a rule to follow, or part of the job
```

`repair` is the one member that ACTS. It lives here because what it enforces is the declaration
contract and not the data contract — it cannot stop a wrong number, only an unaccountable one.
`repair` without `claims` raises at construction: with no `claims` field offered there is never a
citation to hand back, so it could only ever fire zero times.

Where each piece of `claim_binding` went:

| was | is | axis |
|---|---|---|
| the `claims` schema field + prompt (R11) | ✅ `Protocol.claims` | protocol |
| `premises` (derived claims) | part of the same field | protocol |
| `CLAIM_FRAMING` env var | ✅ `Protocol.framing` | protocol |
| `because` on governed calls (R10) | ✅ `Protocol.purpose` | protocol |
| reject-and-retry on unresolved citations (R12) | ✅ `Protocol.repair`, at `Position.REPAIR` | protocol — it enforces the DECLARATION contract |
| the stored audit | ✅ always on, `engine/src/evidence/` | neither — it is the instrument |
| typed `value` / `source_metric` / `sources` (R7) | ⬜ still `GuardrailSet.governed_numbers` | protocol, misfiled — R7 is published |

The audit becoming unconditional is the point of the split: measurement is not a treatment. An
answer that declares nothing audits to `n=0`, which is a finding, not an absence.

`claims` and `premises` are still one flag, so the cell "claims without derived claims" remains
unexpressible. That is a real gap and it is smaller than it looks — `premises` is an optional
field, so the model can already decline it, and the ablation in step 4 measures the framing
difference that actually moves the derived rate (6.9% → 13.6%).

### The move that finished it: the ladder stops at R9

The three steps above put the declarations on their own axis while leaving them *numbered* as
rungs 10–12 of the guardrail ladder. That was still wrong, for a reason worth stating plainly:

**a guardrail ladder is ordered by increasing strictness about what touches data, and a
declaration is not stricter than a verifier — it is orthogonal to it.** Numbering them as rungs
asserted an ordering that does not exist, and it made the useful cells inexpressible. The one
question worth asking is whether declaring helps a *weaker* agent, and "rung 5 with claims" could
only be written as an eight-name explicit set.

That is not hypothetical. The rung-7 R9 baseline answers 70 questions and gets **4 wrong**. There
is no room up there to detect whether declaring changes accuracy. The experiment has to run
further down, where the agent is wrong often enough for a difference to show — and until this
move, that run could not be configured.

So `LADDER` stops at R9, and `purpose` / `claims` / `repair` / `framing` are `Protocol` fields
crossed with any rung and any guardrail level. Labels compose: `R9`, `R9/claims`,
`R5/claims+repair+role`.

**It cost nothing in recomputability, which is why it could be done now.** Nothing above R9 has
ever appeared in a published result or doc — checked, not assumed. And the model-visible surface
is provably unchanged: the retired rungs' fingerprints are reproduced exactly by their protocol
equivalents (`R10` → `R9/purpose` → `6a39830a26e9`, `R11` → `R9/purpose+claims` →
`a75d438d834a`, `R12` → `…+repair` → `8d01ebe7a413`). The restructure renamed cells; it did not
alter a treatment.

One consequence had to be fixed to make it real: the `claims` field used to be gated behind
`governed_numbers`, so it could not exist below R7. It now has its own gate — citations resolve
against result handles, which exist from rung 3 up, and never needed the R7 checks.

`Position.REPAIR` outlives the guardrail that introduced it. A repair is still a mechanism at a
position; it is simply not a rung. The registry test now asserts every position is used
*somewhere in `engine/src/agent/`* rather than by a `Guardrail`, so the no-dead-position guarantee survives
the axis it was written for.

### Design it twice — the alternative, and why not

The obvious cleaner move is to hoist **every** declaration onto the protocol axis, including
`governed_numbers`'s `value` / `source_metric` / `sources` and `declared_purpose`'s `because`.
Structurally that is more correct — those are declarations, and the checks that read them are
separate mechanisms that happen to be gated by the same flag.

`declared_purpose` was R10, and it moved — nothing above R9 was published, so it cost nothing.

`governed_numbers` is **R7, and it is published**, so it stays. Splitting it would renumber a
ladder whose numbers appear in results and on every stored row; the refactor plan's invariant 1
requires old runs to stay re-gradeable and its invariant 4 requires published numbers to stay
recomputable. So one declaration remains misfiled as a guardrail, and it is written down here
rather than pretended away. It moves with the Workstream A rename, which already carries a
migration.

---

## What this does not change

- **No behaviour change.** Every move is a relocation plus a flag split. The claim audit is the
  same pure function; the correction loop is the same bounded loop with a different label.
- **The guardrail ladder R0–R11 keeps its numbers and its semantics.** Only the repair loop was
  split out, as a new R12, and it has never been published. The pinned model surface confirms it:
  the golden diff across R0–R11 is empty.
- **The rung axis is untouched.**
- **The two metric families stay separate**, exactly as `docs/TRUST-MODEL.md` requires. Nothing
  here merges a gold-requiring metric with a gold-free one; the restructure makes the boundary a
  package boundary instead of a paragraph.

---

## Sequencing

1. ✅ **`claims.py` → `engine/src/evidence/`.** `num_match` moved with it — both ends of the stack ask the
   same question, so one definition, in the layer that owns it. The dependency direction is a
   test (`test_the_evidence_layer_never_reaches_back_into_the_agent`) that catches a real
   violation, not just an absent one.
2. ✅ **`Position.REPAIR` + `citation_repair` as R12.** R11 now asks and audits without
   correcting, so `R12-citation_repair` is the leave-one-out cell that was previously
   unexpressible. The golden surface diff was **purely additive** — R0–R11 byte-identical — so no
   published cell's treatment moved.
3. ✅ **`Protocol`**, threaded beside `GuardrailSet` through `build_grounding`. `CLAIM_FRAMING`
   is gone; `--framings rule,role` crosses every cell, and the arms label themselves `R12` and
   `R12/role` so the report separates what it would otherwise pool. No row-schema bump: no field
   was added or removed, and bumping would only raise a spurious skew warning on every stored run.
4. 🟡 **Run the ablation** the split makes possible: claims off / claims on without repair /
   claims on with repair, × rule and role framing. Six cells, and for the first time each number
   means one thing. **Two of the six are done** — `R9/claims` against `R9/claims+repair`, below.
   The framing pair is still open.
5. ⬜ **`strength.py` and `trust.py`** — the trust ladder, once the ablation says the declarations
   are worth propagating.

Steps 1–3 were behaviour-preserving and landed together. Step 4 is the first experiment on the
third axis, and it is cheap: the audit is a lookup, so it costs one sweep and no judging.

### What step 3 revealed

The framing was not an oversight — it was the first treatment that is **not a boolean**, and
`GuardrailSet` can only say on/off. Anything with more than two levels, or that varies *wording*
rather than *mechanism*, has nowhere to live and ends up in the environment. Two others are still
there: `VERIFIER_STANCE` (`engine/src/agent/guardrails/judge.py`) and the reasoning-effort settings. They are
read once per run and stamped on every row, which is most of the discipline — but they still
cannot be named in a cell or vary within a run, so a stance comparison is two runs at different
times on a shared API. `Protocol` is the pattern for fixing that; the judge's stance is the
obvious next tenant, and it belongs to the guardrail axis rather than this one.

### What step 4 measured — repair is real, and it repairs (2026-08-02)

`R9/claims` against `R9/claims+repair`, rung 7, gpt-5-mini at minimal reasoning, 3 reps —
171 attempts per arm, **0 errors**. The two arms differ in exactly one thing: whether a claim
citing something that does not exist is handed back.

**An answer's citations resolve, or it does not go out.**

```
served answers carrying an unresolved citation
  R9/claims          6/76 = 7.9%
  R9/claims+repair   0/74 = 0.0%      Fisher two-sided p = 0.028
```

The obvious confound is that one arm simply made fewer mistakes. It did not: the repair arm
*produced* broken citations at the same rate it fired (4 answers) as the claims arm *served*
them (6). The difference is the correction, not the error rate.

**And it repairs rather than deletes — which is the claim that could not previously be made.**
A citation naming nothing has two cheap fixes, and only one is intended; both end with
`unresolved == 0`, so the stored after-state reported the same success for either. Recording the
before-state (`repairs` on the Answer) is what separates them. Pooled over every instrumented run,
including a targeted sweep of the six questions that trigger it most:

```
11 answers handed back · 27 broken claims · 0 left unresolved
  came back with FEWER claims than went in:  0
  same size:                                 8
  larger:                                    3
```

**The signature is the COUNT, not the text.** A first pass matched each handed-back claim's
opening characters against the final answer and reported 7 deletions — every one of them wrong.
Those answers went 3 claims to 11, 3 to 5, 2 to 3: the model had *rewritten* the sentence while
fixing its citation, and a prefix match scores a reword as a disappearance. Nobody deletes their
way to more claims. The text comparison is kept as a weaker secondary signal; the count is what
the claim rests on.

**It costs tokens and nothing else.** Split answerable / unanswerable, as this repo never pools
them:

```
ANSWERABLE   (n=78/arm)   answered 91.0% -> 89.7%   correct 93.6% -> 92.3%
UNANSWERABLE (n=93/arm)   answered  9.7% ->  7.5%   correct 74.2% -> 77.4%
output tokens per row            319 -> 351  (+10%)
```

Every one of those movements is one or two questions. Repair does not buy accuracy and does not
cost coverage — which is the predicted result, not a disappointing one: `engine/src/agent/protocol.py` states
that repair *"cannot stop a wrong number, only an unaccountable one"*, and the measurement agrees
with the docstring.

### The arm that was missing: declaring nothing (2026-08-02)

`R9` against `R9/claims` against `R9/claims+repair`, same model and settings, 171 attempts each,
0 errors. `R9` is the baseline that had never been run — the agent answers with no declaration
asked of it at all.

```
arm                   coverage   bal.acc   silent   grounded    out tok/row
R9                      93.6%     96.2%     0.6%       n/a           228
R9/claims               91.0%     93.7%     1.8%     88.0%           339
R9/claims+repair        87.2%     93.6%     0.0%     93.1%           342
```

**Asking for an account does not measurably change the answer.** Every difference against `R9`
is within noise — coverage 68/78 against 73/78 (Fisher p = 0.28), answerable-correct 69/78
against 74/78 (p = 0.25), unanswerable-refused 70/93 against 72/93 (p = 0.86). The apparent
6-point coverage slide is five questions. What it does cost is **50% more output tokens**.

Read that as a null with stated power, not as equivalence: at 78 answerable questions per arm
this run could only ever have caught a large effect. A real 5-point coverage cost would need
several hundred per arm to separate from chance.

**`grounded` is `n/a` for `R9`, not low.** That arm produces no evidence graph, so there is
nothing to check — the failure is not that its work does not survive an audit, it is that no
audit is possible. That distinction is the whole argument for the third axis.

**And the grounded-answer rate replicates.** Two independent runs, same day, same settings:

```
              R9/claims   R9/claims+repair
first sweep      88.2%          94.6%
this sweep       88.0%          93.1%
```

**What this does not establish.** The mechanism split rests on **27 broken claims** — the direction
is unambiguous, the exact rate is not precise. The framing arms are unrun. And it is one model,
which matters more here than usual:

```
repair firing rate, all stored runs
  gpt-5-mini      47/1886 = 2.5%
  gpt-5.6-terra    0/55   = 0.0%
  gpt-5.4-mini     0/20   = 0.0%
```

The loop has **never fired on a stronger model**. Run there, the two arms are the same run and the
comparison measures sampling noise at the higher price — which is the concrete form of the claim
this axis was split out to test: the question worth asking is whether declaring helps a *weaker*
agent, and on this evidence the enforcement half only has anything to do down there.

---

## Open decisions this exposes

### The thermometer has no `clarify` case

Zero of the 57 cases expect `clarify`. Every clarification the agent has ever produced was scored
wrong by construction — including ones that were plainly the right move, such as `adv_whales`,
where the agent checked `check_segment_defined("whales")` (undefined), checked `power_users`
(defined), and asked which the user meant.

Fixing this by looking at which clarifications happened to be reasonable is exactly the
circularity that invalidates a gold set. The rule has to be derivable from the **question text
alone**, blind to any run:

> A question is `clarify`-eligible when it names a term with **no governed definition** *and*
> there is **more than one plausible governed reading** of it. One reading, or none, is a refusal.

Applied blind and signed off before any case file changes. Until then, `clarify` is a known
scoring gap, not a result.

### The judge's prose decisions are unmeasurable at this question set

Re-labelled with three independent lenses (strict / pragmatic / skeptical), blind, unanimous-only,
splits escalated rather than out-voted — see `harness/evals/components/prose_panel.py`. Pooled across
**all 22 stored runs**:

```
28 prose decisions · 24 unanimous · 4 escalated
on the settled ones: the judge false-flagged 0 and missed 0
```

Zero errors in 24 decisions, which is reassuring and thin. The sample is the ceiling, not the
panel: of 1,384 rows in today's runs, 513 reached the judge, 381 of those the gold settles by
itself, 108 are unanswerable — leaving 24 prose decisions as **the entire labelling surface**.
Pooling every run ever stored raises it to 28.

The numeric half is fine and current: n=58, agreement 98.3%, catch rate 100%, one false flag.

The four escalated cases are in `harness/evals/labels/prose_panel_escalations.yml` awaiting a human.
Averaging a three-way split into a majority label is how a validation set encodes a coin flip as
ground truth.

**The structural fix is more diagnostic questions, not a better panel.** Seven diagnostic
questions cannot produce a labelling surface large enough to measure a judge that is right most
of the time.
