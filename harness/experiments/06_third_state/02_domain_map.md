# The domain map — what an answer stands on, and where each experiment sits

A map of agentic analytics as a layered stack, the failure classes at each layer, and which
instrument can detect each one. Written to place the five completed experiments, the sixth in
design, and the space none of them touch.

The unit of the domain is **one answer a decision rests on**. Everything below is a layer that
answer stands on, or a step it passes through on the way out.

---

## 1. The stack

Fifteen layers in four strata. For each: what lives there, what goes wrong, and what could
possibly notice.

### Stratum I · GROUND — what happened, and what got recorded

| | layer | what lives there | what goes wrong |
|---|---|---|---|
| **L1** | Reality & instrumentation | the business process; the events the product emits | states nobody logs, events that stop firing, an event whose meaning drifts, a flag nobody wrote down |
| **L2** | Raw data | source tables, columns, enums, keys, timestamps | inconsistent enums (`ios`/`iOS`/`1`), test accounts in production, a `status` column stale for 8% of rows, duplicate keys, timezone drift |
| **L3** | Modelled data | `dim_` / `fct_` views, star schema, conformed dimensions, snapshots | fan-out joins that double a number, wrong grain, a table beside its own `_v2`, a snapshot beside the live fact |

### Stratum II · MEANING — what the numbers are called and what they mean

| | layer | what lives there | what goes wrong |
|---|---|---|---|
| **L4** | Semantic layer | metrics, measures, dimensions, segments, default filters, coverage windows, units, ownership | no governed definition (k = 0); **competing definitions (k ≥ 2)**; scope traps; concept forks; name collisions; duplicates; no declared coverage; no owner |
| **L5** | Ontology & knowledge | what terms mean in this business; world facts absent from the data; synonyms; entity relations | an undefined term; a world fact that lives only in someone's head ("APAC launched 2026-05-01", "partnerships is an internal test channel"); a meaning that drifted and was never restated |
| **L6** | Causal & structural model | metric tree, identity edges, influence edges with their evidence | correlation asserted as cause; an identity spanning two populations; a missing driver; a tree that does not reconcile |

### Stratum III · ACT — turning a question into a number

| | layer | what lives there | what goes wrong |
|---|---|---|---|
| **L7** | The question | intent, segment, period, grain, baseline, output shape | underspecification — group 1 of the clarification taxonomy |
| **L8** | Grounding & selection | the mapping from the question onto L2–L6 | wrong-metric selection; the right number reached off the governed path; improvising SQL where the layer governs nothing; a claim labelled with a metric it did not come from |
| **L9** | Execution | compiled SQL, filters, the covered window | a period outside coverage; a filter value that is not a governed member; a phantom dimension; an unsupported join |
| **L10** | Composition | the served number and the sentence around it | a hand-composed number; a unit error; an implausible value; the right number for a different question; no conclusion drawn at all |
| **L11** | Declaration | citations, claims, stated purpose, the evidence graph | uncited; a citation that resolves to nothing; a stated figure that differs from the one cited |
| **L12** | Adjudication | the output guardrails and the judge | blocks a good answer; passes a bad one; refuse-only by design, so it cannot express a third verdict |

### Stratum IV · EXCHANGE — what reaches a person, and what they do

| | layer | what lives there | what goes wrong |
|---|---|---|---|
| **L13** | Outcome | the typed terminal action, its reason code and payload | a silent wrong number; over-refusal; over-clarification; a reason code nobody can act on; a clarification with no named candidates |
| **L14** | Resolution | the second turn, the disambiguation, the route to a backlog | abandonment; a clarification the user cannot answer either; a refusal that routes nowhere |
| **L15** | Decision & trust | the reader's confidence, the action taken, what happened next | trust miscalibration in either direction; a right number and a wrong decision; no feedback loop back to L4 |

---

## 2. Which instrument reaches which layer

Six instruments exist, and each needs a different input before it can run at all. What it needs
determines how far it can reach — this is the structural reason preflight sits where it sits and
cannot move.

| instrument | what it needs to run | reaches | runs in production |
|---|---|---|---|
| **Static scan** | the declarations, nothing else | L3, L4, and the arithmetic half of L6 | in CI, before deploy |
| **Data tests** | the data, but no question | L2, L3 | yes |
| **Runtime guardrails** | a question and a run | L7 – L12 | yes |
| **Trace-backed eval** | a run's own trace and the declarations | **L4**, and L8 – L13 | **yes** |
| **Gold-backed eval** | questions plus written correct answers | L2 – L15 | **no** |
| **Field observation** | a person | L1, and L13 – L15 | yes, slowly |

The evaluation row was missing from the first version of this map, and splitting it in two is what
makes the map say something. Both halves are instruments. They differ in one input, and that input
decides whether a customer can ever run them.

**Gold-backed** is what every published rate in this repo rests on: a human wrote down the right
answer. It reaches almost every layer and it is the only instrument on the list that cannot be
deployed. Anything a write-up claims about practice has to be honest that the reader has no gold
set.

**Trace-backed** decides nothing and needs no labels. It asks whether a citation resolves against
the run that produced it, whether a stated figure matches the one it cites, and whether two
candidate groundings return different numbers for this slice. `engine/src/evidence/` is already
built this way, and the module comment says why: it "decides nothing… that is what keeps it an
instrument rather than a second judge, and why its numbers need no gold answers."

Three things fall out, and all three are findings rather than bookkeeping.

**L5 is unreachable by any instrument except a gold set or a person.** Ontology and world knowledge
produce no static finding, because a scan compares two declarations and there is only one, or none.
This is experiment 05's honest boundary, stated there as "the boundary is what nobody wrote down",
and the map explains why it is a boundary rather than a gap in the tool.

**The widest instrument is the one you cannot deploy.** Gold-backed evaluation spans fourteen of
fifteen layers. Everything else is narrow. So the practical question for any finding is not "can we
measure it" but "can we measure it without gold", and that question has a different answer per
layer.

**Trace-backed evaluation is the only production-capable instrument that reaches L4.** That is the
whole reason `competing_definitions` is a tractable problem and, say, a missing driver at L6 is not.
Divergence between two governed candidates at one slice is a lookup plus one extra query. It needs
no model, no labels, and no person — so the thing the harness measures with gold, a customer can
measure without it. That bridge is the strongest practical claim available from experiment 06, and
it exists for exactly one of the fifty problems below.

---

## 3. Three laws that fall out of the map

**Law 1 — Detectability before a run requires two declarations that can disagree.**
Only stratum II holds two artifacts that both *declare* something, which is why it is the only
stratum a scan can lint with no data, no question, and no model. Stratum I needs the data. Stratum
III needs a question. Stratum IV needs a person. A tool cannot be moved up or down this stack by
being cleverer; it can only be moved by being given a different input.

**Law 2 — A defect is invisible when it changes which rows, not what is counted.**
Every check in stratum III operates on the *result*. A difference in scope produces a plausible
number of the right magnitude and the right unit, from a real metric, computed by real SQL. The
provenance check passes, the output validation passes, the judge sees a genuine trajectory. Nothing
downstream has a signature to test. Invisibility is therefore a property of the signature a defect
leaves, not of how bad it is — which is why the layer's own severity ratings are a prior and not a
verdict (experiment 05 found the worst and the quietest cluster both rated HIGH).

**Law 3 — The fix is almost always at a lower layer than the symptom.**
A wrong-metric selection at L8 is fixed at L4. Improvised SQL at L8 is fixed by adding a metric at
L4. A clarification at L13 is fixed at L4 or L5. This is the repair matrix stated as a rule, and it
is the reason a clarification is worth more than a refusal: it names the two candidates, so it
points at the row in L4 that has to change.

---

## 4. The six experiments as six operations on one map

Each experiment is a different move, which is why they compose rather than extend each other.

| experiment | the question it asks | the move |
|---|---|---|
| **01 · Grounding** | how much does structure buy? | **vertical, whole stack** — hold the question fixed, raise the floor from L2 to L6, one layer at a time |
| **02 · Reliability** | how much do guardrails cut confident-wrong answers? | **horizontal, stratum III** — hold the stack fixed, add one check at one position |
| **03 · Protocol** | how much of an answer can be checked? | **L11 only** — add declaration, change nothing else |
| **04 · Repair** | for one broken primitive, what is the cheapest place to fix it? | **vertical, per defect** — move one grounding between implicit, documented, modelled, declared, enforced |
| **05 · Preflight** | does fixing what a static scan finds remove runtime harm? | **L3 + L4, statically** — lint a layer before any run, then measure the agent before and after |
| **06 · Third state** | what should the agent do when the layer is ambiguous? | **L4 → L13** — a defect at L4 that no stratum-III check can see, given a new outcome at L13 |

Experiment 06 is the first one whose whole subject is a defect that Law 2 makes invisible. That is
its claim to existence, and it is why it needs a new outcome rather than a new check: there is
nothing at stratum III left to check with.

---

## 5. Granular problems, and where each one stands

Every problem worth naming, with what could catch it and whether we have measured it.

Status key: **measured** · **partial** — touched but not the subject of an experiment ·
**open** — named, never measured.

### Stratum I

| id | problem | detected by | fixed at | status |
|---|---|---|---|---|
| L1.1 | an event the product never emits | field observation | L1 | open |
| L1.2 | a flag whose meaning nobody wrote down | field observation | L5 then L2 | **open**, and named in exp 05 as the residue the repair could not remove |
| L1.3 | an event whose semantics drifted | field observation | L1 + L5 | open |
| L2.1 | inconsistent enum spellings | data tests | L3 | partial (rung 1 treatment) |
| L2.2 | internal or test accounts mixed into production | data tests, if the flag exists | L3 or L4 | partial |
| L2.3 | a status column stale for part of the population | data tests | L2 | **open**, exp 05 residue |
| L2.4 | duplicate or non-unique keys | data tests | L2 | open |
| L3.1 | a fan-out join that doubles a number | data tests; a grain declaration | L3 | partial (rung 2) |
| L3.2 | a table beside its own `_v2` | static scan (`VERSIONED_TWIN`) | L3 | **measured** (exp 05) |
| L3.3 | a snapshot beside the live fact at another grain | static scan (`FACT_TWIN`) | L3 | **measured** (exp 05) |

### Stratum II

| id | problem | detected by | fixed at | status |
|---|---|---|---|---|
| L4.1 | no governed definition for the concept (k = 0) | runtime lookup | L4 | **measured** (exp 02, Pile B) |
| L4.2 | **two governed definitions, both defensible (k ≥ 2)** | **static scan + divergence** | L4 governance | **exp 06** |
| L4.3 | a scope trap — metric B is metric A plus a hidden filter | static scan (`SCOPE_TRAP`) | L4 | **measured** (exp 05) |
| L4.4 | a concept fork — one concept, several metrics over different columns | static scan (`CONCEPT_FORK`) | L4 | **measured** (exp 05) |
| L4.5 | two names that read alike | static scan (`NAME_COLLISION`) | L4 | **measured** (exp 05) |
| L4.6 | an exact duplicate under two names | static scan (`DUPLICATE`) | L4 | **measured** (exp 05) |
| L4.7 | no declared coverage window | static scan | L4 | partial (R3 uses it; the absence is untested) |
| L4.8 | a metric with no owner, so no one can decide | static scan, in principle | governance | **open** — the layer holds no ownership field |
| L4.9 | the layer governs nothing for a real question, so the agent improvises | runtime, only if provenance is enforced | L4 | **measured** (exp 05, the third residue) |
| L5.1 | a term used in questions that the ontology never defines | nothing | L5 | partial (rung 5 present/absent) |
| L5.2 | a world fact needed for a correct answer, absent from every layer | nothing | L5 | partial (rung 5) |
| L5.3 | synonyms colliding across dimensions | static scan (member clashes) | L4 | partial |
| L6.1 | correlation reported as cause | runtime, via a causal-evidence lookup | L6 | **measured** (exp 02, `no_causal_evidence`) |
| L6.2 | an identity edge spanning two populations | static arithmetic | L6 | partial — the tree documents the fix; the defect is untested |
| L6.3 | a driver the tree does not contain | nothing | L6 | open |

### Stratum III

| id | problem | detected by | fixed at | status |
|---|---|---|---|---|
| L7.1 | intent underspecified — what is this for | the question | L7 | open |
| L7.2 | segment underspecified | the question | L7 or a declared default | open |
| L7.3 | period or time grain underspecified | the question or a default | L4 default | open |
| L7.4 | aggregation grain underspecified | the question | L4 | open |
| L7.5 | a comparison with no baseline | the question or a default | L4 default | open |
| L7.6 | output shape underspecified — value, trend, breakdown, cause | the question | L7 | partial (the diagnostic tier lives here) |
| L8.1 | wrong-metric selection | provenance at runtime | L4 | **measured** (exp 05: 24% → 0.00) |
| L8.2 | the right number reached off the governed path | provenance at runtime | L8 | **measured** (exp 02, `wrong_metric`) |
| L8.3 | a claim labelled with a metric it did not come from | the claim audit | L4 rename | **measured** (28% mislabel rate, exp 03) |
| L9.1 | a period outside the coverage window | before the query | L4 | **measured** (R3) |
| L9.2 | a filter value that is not a governed member | before the query | L4 | **measured** (R5) |
| L9.3 | a dimension the metric cannot be broken down by | before the query | L4 | **measured** (rt_phantom tier) |
| L10.1 | a hand-composed number | after the answer | L10 | **measured** (R7) |
| L10.2 | a value malformed for its unit | after the answer | L10 | **measured** (R8) |
| L10.3 | evidence gathered, no conclusion drawn | the claim audit | prompt / protocol | **measured** (73.7%, exp 03) |
| L11.1 | an answer with no citation | the evidence layer | protocol | **measured** (exp 03) |
| L11.2 | a citation that resolves to nothing | the evidence layer | repair | **measured** (88% → 94.7%) |
| L11.3 | a stated figure that differs from the cited one | the evidence layer | repair | **measured** |
| L12.1 | the judge blocks a correct answer | gold only | judge design | **measured** (`judge_blocked_good`) |
| L12.2 | the judge passes a wrong one | gold only | judge design | **measured** (`judge_passed_bad`) |
| L12.3 | the judge cannot express a third verdict | by design | judge design | **exp 06** — the conflict to watch |

### Stratum IV

| id | problem | detected by | fixed at | status |
|---|---|---|---|---|
| L13.1 | a silent wrong number at k = 0 | gold only | stratum III checks | **measured** (48.5% → 2.4%) |
| L13.2 | **a silent wrong number at k ≥ 2** | **divergence, no gold needed** | L4 or L13 | **exp 06** |
| L13.3 | over-refusal | gold | guardrail tuning | **measured** (coverage) |
| L13.4 | over-clarification | gold | gate scoping | **exp 06** |
| L13.5 | a refusal code nobody can act on | the code vocabulary | L13 | **measured** (`other` chosen 26 times over a fitting code) |
| L13.6 | a clarification with no named candidates | the payload schema | L13 | **exp 06** |
| L14.1 | the clarification is never resolved | simulation or the field | interface | **open** |
| L14.2 | the clarification is unanswerable by the user | the ambiguity/vagueness split | L4 default | **open** |
| L14.3 | a refusal or clarification that routes nowhere | process | governance | **open** |
| L15.1 | trust miscalibration — confidence that does not track accuracy | field study; or calibration as a proxy | the whole stack | **open** |
| L15.2 | right number, wrong decision | field study | outside the stack | out of scope |
| L15.3 | no feedback loop from a clarification back to L4 | process | governance | **open** |

---

## 6. The white space, ranked

Four regions no experiment touches. Ordered by what they would be worth against what they would
cost.

**1 · L14 — resolution.** The second turn. In scope for experiment 06 already, cheap to build (the
case carries the disambiguation, the runner continues the loop), and it is the only way the cost
table in the brief can be honest. Without it every clarification is priced at half an episode.
*Do it inside experiment 06.*

**2 · L15.1 — calibration as a proxy for trust.** The practice's whole promise is "analytics your
leadership trusts", and nothing in five experiments measures trust or anything near it. Full trust
calibration needs people. Calibration does not: ask the agent to state its own confidence, then
measure whether that confidence tracks its accuracy. That is a standard reliability-diagram
measurement, it runs entirely in the harness, and it is the closest quantity to the promise that
does not need a human subject.
*A small, high-value experiment 07.*

**3 · Stratum I — data truth.** Every experiment to date holds the warehouse fixed and generated, so
"the agent answered correctly from wrong data" has never been measured. It is the largest failure
class in real deployments and the one experiment 05 ran into as its boundary. It is closer than it
looks: the repair matrix already builds eight versions of one warehouse, and the generator already
injects one anomaly. Injecting *data* defects rather than *definition* defects is the same
machinery.
*The most valuable unexplored region, and the most work.*

**4 · L7 — the question.** Group 1 of the clarification taxonomy: underspecified intent, segment,
period, grain, baseline, output shape. Three cases in the suite touch it. It is a real class and it
is well covered by published benchmarks, which makes it the least differentiated thing on this list.
*Worth a tier of cases, not an experiment.*

---

## 7. How to use this map

- **Placing a new idea.** Name the layer the defect lives at and the layer the symptom appears at.
  If they are the same, it is a check. If the defect is lower, it is a repair. If no instrument
  reaches the defect's layer, it is a governance problem wearing an engineering costume.
- **Deciding where a fix goes.** Law 3: push it down until it reaches the lowest layer that can hold
  it. A default belongs in L4, not in a prompt. An ownership field belongs in L4, not in a runbook.
- **Judging whether a failure can be caught.** Law 2: ask what signature it leaves at the layer the
  check runs at. If the answer is "a plausible number", no stratum-III check will ever see it, and
  the only remaining moves are a static scan at L4 or a new outcome at L13. That pair is exactly
  experiment 06, and it is why the two halves of the preflight work — offline linter and runtime
  gate — are one artifact with two consumers.
