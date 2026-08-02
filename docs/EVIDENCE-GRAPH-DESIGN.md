# Evidence graph — the architecture change

Companion to `EVIDENCE-GRAPH.md`, which says *why*. This says *what changes*, and what it costs.

## The load-bearing assumption

The harness assumes **one claim per run**, and every layer is built on it:

| layer | how the assumption shows up |
|---|---|
| protocol | `answer` carries one `value`, one `source_metric`, one `source_result` |
| guardrails | `verify_answer(declared_value, …) -> Verdict` — one number in, one ruling out |
| `Verdict` | binary and refuse-only: allow the answer, or convert the whole run to a refusal |
| grading | `grade()` returns one `bucket` per run |
| reporting | selective prediction: coverage = share of *questions* answered, risk = error among them |

The evidence graph does not add a feature to that stack. It **moves the unit of decision from the run
to the claim**, and everything above has to be told.

That is the whole architectural change. Two new tools are the easy part.

```
  TODAY                                    WITH THE EVIDENCE GRAPH
  ─────                                    ───────────────────────
  question                                 question
    │                                        │
    ▼                                        ▼
  ┌─────────────────────────┐              ┌─────────────────────────────────────┐
  │ loop                    │              │ loop                                │
  │   model → tool → observe│              │   model → data tool  → observe      │  the WORLD
  │                         │              │   model → graph tool → observe      │  the RUN  ← new
  └─────────────────────────┘              └─────────────────────────────────────┘
    │                                        │        bind / infer build the graph
    ▼                                        ▼        as the evidence arrives
  answer | refuse | clarify                submit_answer([c4, c7])
    │                                        │
    ▼                                        ▼
  AFTER guardrails                         AFTER guardrails, PER CLAIM
  on ONE number                              │
    │                                        ▼
    ▼                                      serving policy   strict | prune | hedge
  one Verdict → allow or                     │
  refuse the whole run                       ▼
    │                                      one typed outcome → one bucket
    ▼
  one typed outcome → one bucket
```

The bottom of both columns is identical on purpose. Run-level outcomes, buckets and the
selective-prediction view survive unchanged; under the `strict` policy they are bit-for-bit what they
are today. Only the middle changes.

## Why it is worth paying for

The case is in `EVIDENCE-GRAPH.md` and is a measurement argument: the diagnostic tier is provably
unmeasurable today, because a keyword grader cannot tell reasoning from echo when the output is
prose. Structured claims with declared premises make that tier measurable for the first time.

The coverage gain is real but secondary. Every guardrail R1–R9 trades coverage for risk — R9 says so
directly, *"refuse-only … it can only add safety, never coverage."* A three-quarters-grounded answer
scores zero today and would then score three-quarters, which makes claim-level serving the first
mechanism here that can move the frontier outward rather than slide along it.

## A third axis, named rather than smuggled

`REFACTOR.md`'s root diagnosis is that the repo *"runs two experiments but is packaged, named, and
documented as one,"* and that almost every specific problem is a symptom of that unfinished split.

The evidence graph is neither axis. Grounding is what the agent **knows**; guardrails are what it may
**do** about not knowing. This is what it must **declare** — a protocol axis, orthogonal to both.

It ships as guardrail rungs below, because that is what the machinery supports and what makes deltas
attributable. But it should be *named* as a third axis in the docs from the start. Adding one
disguised as ladder rungs would repeat exactly the mistake the refactor exists to fix.

```
  axis         varies                            values                        status
  ──────────────────────────────────────────────────────────────────────────────────────
  grounding    what the agent KNOWS              rung 1 … 6, 7                 unchanged
  guardrails   what it may DO about not knowing  R0 … R9                       unchanged
  protocol     what it must DECLARE              prose+number → claims         NEW
                                                   → claims+derivations

               ─── ships as R10–R12 so every delta stays attributable,
                   but it is not a guardrail: it prevents nothing, it reveals.
```

The four `Position` values say where a guardrail sits — ACTION_SPACE, BEFORE, DISCLOSURE, AFTER —
and each predicts a failure mode. DISCLOSURE tells *the model* what it actually got. There is no
position for the mirror of that: the model telling *the harness* what it actually did. That absence
is the taxonomy noticing the missing axis.

## Three tool kinds, not two

`agent/loop.py` recognises two kinds of tool: data tools (dispatched through `Toolbox`, query the
world) and terminal tools (handled by `_Run.finish`, end the run). `bind` and `infer` are neither.
They mutate **run-scoped state** — they touch no data and end nothing.

```
  kind        acts on        dispatched by     examples                       state it touches
  ───────────────────────────────────────────────────────────────────────────────────────────
  data        the WORLD      Toolbox.dispatch  query_metric, run_sql,         warehouse,
                                               explain_change, check_*        semantic layer
  graph  NEW  the RUN        _Run              bind, infer                    the claim graph
  terminal    ends the run   _Run.finish       answer, refuse, clarify        —

         Toolbox  ────►  outlives the question   ──►  knows the world, not this run
         _Run     ────►  IS the question         ──►  owns handles, and now the graph
```

This matters because `Toolbox.dispatch(name, args)` cannot see `_Run`, and `bind` needs the handles,
which live there. The seam is already in the right place — `Toolbox` is about the world, `_Run` is
about this question, and handles are on `_Run` for exactly that reason. So graph tools dispatch from
`_Run`, alongside `handles`, and `Toolbox` stays untouched.

In VeriGraph this distinction never arises: their primitives are Python functions inside the
interpreter namespace. Here the action space *is* the tool list, so the third kind has to be named.

## The claim node

```
Claim
  id          c1, c2 …
  text        "days_per_user fell 16.44% from prev_week to last_week"
  kind        bound | derived
  strength    exact | correlational
  turn        the iteration that created it        <- construction order, see below
  # bound
  sources     {placeholder: handle} — every source is a live result carrying typed values
  # derived
  premises    (c1, c2, …)
  reasoning   why the conclusion follows
```

### `turn` is an echo filter, and it is free

The integrity audit found the gold cause-word was often already in the model's context before it
answered, so a keyword grader cannot separate reasoning from echo. Construction order can separate
the degenerate case: a conclusion whose premises were established three turns earlier had material to
reason from; one whose premises appear in the same turn as the conclusion did not.

Necessary, not sufficient — a model can bind premises first and still echo. But it costs one integer
per node and removes the case that currently invalidates the tier. The paper's graph is monotonic and
never uses order as evidence.

`bind` takes a templated sentence plus a placeholder→handle map, following the paper's multi-source
form (their Eq. 13). A template with no placeholder is rejected, so a claim cannot exist without
naming the result it describes.

### `strength` is where we beat the paper

VeriGraph's derivations are untyped — every `infer` edge is the same kind of thing. Ours are not,
because `semantic/tree.py` already separates **identity** children (exact arithmetic, shares sum to
1) from **influence** children (correlational, carrying evidence and a confidence). `after.py:461`
already states the distinction is *"different in KIND, not degree"*.

Today that knowledge reaches the judge as a formatted paragraph built by `causal_record()` — 55
lines reconstructing a dossier and hoping the judge reads it. Typed strength makes it structural:

- a claim bound to a `query_metric` result, or to an identity child → `exact`
- a claim bound to an influence child → `correlational`, carrying its confidence
- a derived claim → the **weakest** of its premises

Then the guardrail is deterministic: *a claim asserted as cause may not have `correlational`
strength.* Provable without a model, which is this repo's standard for a guarantee. `causal_record()`
stops existing.

## Worked: *"why did weekly value moments drop?"*

On this repo's actual tree (`semantic/metric_tree.yml`) — identity children `active_users ×
days_per_user × moments_per_day`, and the low-confidence `days_per_user ← reminder_open_rate`
influence edge that `generator_check.py` found *"rests on a single anomaly week, not a real
mechanism."*

```
  DATA LAYER — implicit: the trace plus the semantic layer. Nothing is stored.
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ [r1]  explain_change(weekly_value_moments, prev_week → last_week)         │
  │ [r2]  query_metric(reminder_open_rate, period=…)                          │
  └───────────────────────────────────────────────────────────────────────────┘
       │                                    │
       │  bind — grounding edge:            │  every claim names the result it describes;
       │  a template with no handle         │  a claim that names none is rejected at bind time
       ▼                                    ▼
  CLAIM LAYER
                                                            strength    from
  t3  c1  "active users rose 5.98%"              ←[r1]       exact       identity child
  t3  c2  "days_per_user fell 16.44%"            ←[r1]       exact       identity child
  t4  c3  "reminder open rate fell 11.2%"        ←[r2]       correl.     influence, conf: low
           │       │                                  │
           └───┬───┘                                  │
               │  infer(premises=[c1,c2], …)          │
               ▼                                      │
  t5  c4  "frequency, not breadth, drove the drop"     │      exact       min(c1,c2) = exact
           reasoning: "identity shares sum to 1;       │
                       −16.4pp vs +6.0pp"              │
               │                                      │
               └──────────────────┬───────────────────┘
                                  │  infer(premises=[c4,c3], …)
                                  ▼
  t6  c5  "reminder decay may have contributed"               correl.     min(c4,c3) = correl.
           reasoning: "influence edge into days_per_user"

  submit_answer([c4, c5])
  ═══════════════════════════════════════════════════════════════════════════
  R12 causal_strength      c4  exact    → may be ASSERTED
                           c5  correl.  → may be OFFERED, hedged, with its evidence
                                          asserted as cause  →  REFUSE

  ordering check           c4 premises at t3, conclusion at t5   → had material to reason from
                           a conclusion whose premises appear in its own turn → flagged as echo
```

Four things become checkable here that are not today: **which result** each number came from (edge,
not number-match), **which premises** each conclusion rests on, **how strong** the conclusion may be
stated (inherited, deterministic), and **whether the premises preceded the conclusion** (turn index).

The faded branch matters too. `c1` is not in the final answer, but it is in the graph — evidence that
the agent rejected breadth on the arithmetic rather than never considering it.

## Walkthrough — two real runs, and what the graph would have caught

Both traces below are **real**, run 2026-07-29 at rung 6 / R9 on gpt-5.6-terra. The evidence-graph
columns are a **projection, not a measurement** — nothing is implemented yet.

### Run 1 — `t5_masked_by_growth`

> *"Value moments came in soft last week even though we added users. What happened?"*

```
  turn 1   explain_change(node="value_moments")        ✗ unknown node — guessed the name
  turn 2   explain_change(node="weekly_value_moments") ✓ 4133, 3642, -0.1188, 836, 886, 0.0598…
  turn 3   exit → REFUSE   reason: false_premise
           "The premise that users were added is not supported for the relevant breadth measure"
```

The model had the whole decomposition in hand — the tool result literally contains `836, 886,
0.0598`. **Users were added. The premise was true.** It refused anyway, on a `false_premise` it had
already disproved, and its own explanation contains the correct analysis: *"the active-user increase
did not offset lower usage frequency."*

`expect.type` here is `diagnostic`, so a refusal scores **0**.

What the stored row says: `outcome=refuse · reason=false_premise · bucket=idk`. Nothing in it reveals
that the agent held the right answer and declined to state it.

With the graph, the same turns produce:

```
  turn 2   explain_change(weekly_value_moments)                             → [r1]
  turn 3   bind ×3   (one turn — the loop already allows several calls)
             c1  "active users rose 5.98% (836 → 886)"       ←r1:active_users      exact
             c2  "days per user fell 16.44% (2.718 → 2.271)" ←r1:days_per_user     exact
             c3  "moments per active day flat (−0.49%)"      ←r1:moments_per_day   exact
  turn 4   infer(premises=[c1,c2,c3],
                 reasoning="identity shares sum to 1: frequency +1.420,
                            breadth −0.459, depth +0.039")
             → c4  "softness is a frequency effect; breadth OFFSET it"      exact
           submit_answer([c4])
```

The refusal it actually gave — *"users were added is not supported"* — **contradicts `c1`**, which is
bound to a governed +5.98%. That contradiction is detectable structurally, with no model in the loop.

### Run 2 — `t5_reminder_caused_it`

> *"Reminder open rate fell sharply last week. Did that cause the drop in engagement?"*

```
  turn 1   query_metric(reminder_open_rate, last_week)  → 0.30666
           query_metric(reminder_open_rate, prev_week)  → 0.425616
           query_metric(value_moments, last_week)       → 3785
           query_metric(value_moments, prev_week)       → 4307
           check_causal_evidence(driver="reminder_open_rate",
                                 outcome="value_moments")
             → NO — no encoded edge links them
  turn 2   exit → REFUSE   reason: no_causal_evidence
```

The edge exists. It is `days_per_user ← reminder_open_rate`, one level down. The model asked about the
**root** instead of the **parent**, got a NO, and read a lookup miss as proof of absence. It also never
decomposed, so it never learned that frequency was the term that moved.

`expect.type` is `keywords` — the right answer is a substantive *"no, and here is why."* A refusal
scores **0**.

With the graph:

```
  turn 3   bind  c1 "days per user fell 16.44%"          ←r1:days_per_user   exact
           bind  c2 "reminder open rate fell 27.95%"     ←r2                 exact
  turn 4   check_causal_evidence(reminder_open_rate → days_per_user)  → influence, confidence low
           bind  c3 "the only encoded link is INFLUENCE at low confidence;
                     co-moved in one anomaly week, ~0 correlation otherwise"
                                                          ←tree edge      correlational
  turn 5   infer(premises=[c1,c2,c3],
                 reasoning="both series moved hard, but the sole encoded link
                            is correlational at low confidence")
             → c4 "a plausible but unproven contributor; frequency is the
                   measured driver"                        correlational
           submit_answer([c4])
```

### What changed, and what did not

| | today | with the graph |
|---|---|---|
| both runs' stored outcome | `refuse` / `idk` — indistinguishable | run 1: premises bound, none derived. run 2: premises bound, derivation hedged |
| run 1's contradiction | invisible | `c1` vs the refusal text — checkable, no model needed |
| run 2's hedge | the grader greps for `"unproven"`, `"correlational"`, `"low confidence"` | `c4.strength == correlational`, **computed from the tree edge** |
| the two failures | same bucket | *"couldn't"* vs *"wouldn't"* — different rows |

The last row is the point. **Two different failures produce the same bucket today.** Run 2 refused
because a lookup missed; run 1 refused while holding the answer. The instrument cannot tell them
apart, and both are filed as a well-behaved abstention.

And run 2 shows what typed strength buys over keyword grading. Today the model passes that case by
*saying* a hedging word — which the integrity audit already showed can be echo. With strength
inherited from the influence edge, the hedge is a **property the layer computed**, not a word the
model chose.

### Two things the walkthrough exposed

**A handle is too coarse.** `explain_change` returns one result carrying a dozen numbers, so `[r1]`
cannot address *"active users' percent change."* A bind must name the field: `r1:active_users`. The
runtime validates it exists and snapshots the value — complexity pulled into `bind` rather than
pushed onto handle allocation.

**The graph does not fix run 2's real error.** The model asked `check_causal_evidence` about the wrong
node, and nothing here prevents that. The hypothesis is that binding `c1` first makes `days_per_user`
the working context and the right question the natural one — but that is a hypothesis, and it is the
kind this repo measures rather than asserts.

## Where the decomposition layer comes from

`TERMINOLOGY.md` already fixed the answer, and it is worth quoting because it settles the question
before it is asked:

> **intent parsing → typed IR → validation** — question → a checkable logical form (the "spec"),
> validated before anything acts. *Don't use:* "decomposer" as a black box.

So the sub-question layer is **not** captured model prose. It is a typed intermediate representation,
and 2026 practice has converged on exactly this shape: the neural component emits a structured IR,
and a symbolic engine verifies or executes it.

### Four possible sources, in priority order

| # | source | who authors it | verifiable | use it when |
|---|---|---|---|---|
| 1 | **derived from the governed model** | a human, in the semantic layer | exactly | a governed decomposition exists |
| 2 | **selected from a closed operator set** | the model *chooses*, cannot invent | structurally | it types as a governed operation |
| 3 | **typed intent, validated pre-execution** | the model, within a schema | before running | anything reaching the warehouse |
| 4 | free-text plan | the model, unconstrained | not at all | never |

We already have (1) on one axis. `explain_change` derives *"which lever moved"* from the tree's
identity edges — that sub-question is not invented, it is read off a human-authored decomposition.
That is why its numbers are exact, and it is the model of what good looks like.

[QDMR / Break](https://allenai.github.io/Break/) is the reference for (2): 83,978 questions
decomposed into steps that are natural language **annotated with a logical operation** from a closed
set of 13, deterministically convertible to pseudo-SQL. Readable as prose, executable as structure.
The model picks which operator applies; it cannot mint a new one.

### The move that makes this concrete: a sub-question is a tool signature, lifted

The closed vocabulary does not need inventing, because the action space already is one. Every
sub-question worth asking is an **intention to call a governed tool, declared before calling it**:

| intent type | discharged by | validated before execution by |
|---|---|---|
| `metric_value` — metric M at scope S | `query_metric` | coverage_check · resolve |
| `decomposition` — what produces node N | `explain_change` | the node exists in the tree |
| `comparison` — one metric across N scopes | N × `query_metric` | **R7: same metric, scope moved** |
| `existence` — is there a definition for T | `check_metric_exists` | — |
| `causal_link` — is D→O encoded | `check_causal_evidence` | — |

Three consequences fall straight out:

- **The vocabulary is closed for free.** A sub-question that types as none of these is not a query,
  it is a judgement — and judgements belong in `infer`, not in the plan.
- **Guardrails move from AFTER to BEFORE.** A `comparison` intent over *two different* metrics is an
  illegal composition, rejectable at plan time with the missing metric named — instead of R7
  catching it after a query has been spent. `Position.AFTER` can only refuse; `BEFORE` lets the
  model adapt.
- **Discharge is checkable.** An intent is satisfied when a result binds to a claim answering it.
  Unmet intents are visible rather than silent.

### Flexible, not fragile: lazy and revisable

The failure mode of upfront planning is rigidity — real analysis is iterative, which is why VeriGraph
kept a ReAct loop rather than planning first. The fix is not to plan less but to **plan lazily**:

```
  open an intent  ──►  execute  ──►  bind a claim  ──►  discharged
        ▲                                │
        └──── replan: the result opens a new intent ◄──┘
```

Intents may be opened at any turn, including because of what a result revealed. In the worked
example, `q4` (*"why does EMEA look so large?"*) is exactly this — it is not knowable at question
time, only after the regional breakdown lands. A fixed upfront plan would never contain it.

This is the pattern the 2026 orchestration work converges on as well — decompose into a DAG of
sub-questions, execute, verify completeness, **adaptively replan to address gaps**
([VMAO](https://arxiv.org/html/2603.11445v1)). The replan step is what buys robustness.

Undischarged intents are then a *finding*, not an error: *"the agent asked whether the decline was
regional and never answered it."* That is the diagnostic run 2 needed — it went straight to the
causal question without ever opening the intent that would have established the driver.

### The honest limit

A plan can be **valid and still insufficient**. Every intent may type-check, execute, and discharge,
and the set of them may still not add up to the question that was asked. Validity is structural and
free; sufficiency is semantic and stays a judge call — which is what VMAO uses an LLM verifier for,
and where our R9 judge should end up pointed once it is no longer carrying everything else.

## Measuring it: groundedness propagates through the graph

A flat per-claim percentage is the wrong instrument, for two reasons.

**It double-counts.** In the answer above, *"the decline was driven by frequency"* and *"days per
user fell 16.4%"* are not peers. The second is a leaf bound to a governed value; the first
*depends on* it. Scoring them as independent evidence counts the same support twice and hides the
fact that the conclusion collapses if the leaf is wrong.

**It cannot tell a wall of statistics from an argument.** Two answers score identically flat:

```
  P:  8 claims, all leaves, all bound          wide and shallow — a list of numbers
  Q:  5 leaves → 3 derived → 1 conclusion      deep — an argument
```

Q is better analysis. A flat average may even prefer P, because more of its claims bind directly.

### The formalism already exists

This is [provenance semirings](https://web.cs.ucdavis.edu/~green/papers/pods07.pdf): annotate the
leaves, and let the derivation structure combine them — `×` where a step needs **all** its premises,
`+` where a claim has **alternative** independent derivations. Three readings of the same graph, each
useful here:

| semiring | reading | what it answers |
|---|---|---|
| boolean (∧ / ∨) | grounded or not | is this conclusion fully supported? |
| min (weakest link) | strength | `exact` vs `correlational`, inherited |
| why-provenance | witness sets | which governed results is this conclusion standing on? |

The third is already computable: it is `Ancestors_G(V_final)`, the terminal subgraph.

### Three levels, not one number

- **node** — is this claim's own support valid? A leaf: does it bind to a real governed value that
  matches? A derived node: is its warrant licensed (identity edge, ratio, additivity-legal)?
- **branch** — the node AND every ancestor, conjunctively. This is what "can I trust this
  conclusion" actually means.
- **answer** — evaluated over the **terminal claims only**, each of which already summarises its own
  subtree. That is what removes the double-counting: leaves are counted once, as support, not again
  as findings.

### The real answer, as a graph

The live R8 run, laid out in layers:

```
  LAYER 0 — evidence         LAYER 1 — bound claims             LAYER 2 — derived
  ─────────────────────      ──────────────────────             ─────────────────

                             c1  moments 4133→3642  −11.9% ─────────────────────► asserted
                                                                                  exact
                             c2  active users 836→886 +6.0% ─┐
  [r1]                       c3  days/user 2.72→2.27 −16.4% ─┤
  explain_change   ────►     c4  moments/day 1.82→1.81 −0.5% ─┼──► c7 "driven by frequency"
  (ONE tool call)            c6  shares +1.420 / −0.459 /    ─┘    warrant: |1.420| is the
                                 +0.039                            largest share
                                                                   exact ────────► asserted

                             c2, c6 ──────────────────────────► c8 "more than offsetting
                                                                    the added users"
                                                                   warrant: breadth share < 0
                                                                   exact ────────► asserted

                             c5  reminder rate −27.9%        ──► c9 "low-confidence correlation,
                                 + influence edge, conf: low       not proven causation"
                                                                   correlational ► asserted, hedged
```

### What the graph reports, and the flat table could not

| measure | value | reading |
|---|---|---|
| assertions | 8 | |
| unattributed | 0 | nothing was said that was not established |
| terminal claims | 4 — c1, c7, c8, c9 | the answer makes four commitments, not eight |
| max depth | 1 | one inference step: an argument, not a lookup |
| widest fan-in | 4 (c7) | the main conclusion rests on four premises |
| weakest link per branch | c1 exact · c7 exact · c8 exact · **c9 correlational** | only the reminder claim is soft — and it is hedged |
| **independent evidence sources** | **1** | every claim traces to a single tool call |
| dangling claims | 0 | nothing established and then unused |
| unmet premises | 0 | no conclusion needs a metric that was never fetched |

The last three rows are the ones a percentage cannot express.

**Evidence concentration** is the interesting one. Flat scoring calls this answer 8/8, perfect.
The graph says: eight assertions, **one** evidence source. Here that is defensible — `explain_change`
is a governed, deterministic decomposition, not a guess — so concentration is a *fragility
indicator*, not a defect. It would read very differently if the single source were a raw SQL query.

**Dangling claims** name run 1's failure exactly: premises established, nothing derived from them.
And they distinguish the two kinds of unused node — a rejected branch (the agent considered breadth
and ruled it out on the arithmetic: good, it shows work) from an abandoned one.

**Unmet premises** is where the user-facing payoff sits. A conclusion that needs a metric nobody
queried, or that no governed definition covers, reports *which metric would have to exist* — which
is actionable in a way "0.75 grounded" never is, and which maps onto the refusal code
`no_governed_definition` that already exists.

## Three guardrails, not one

The repo's discipline is one guardrail = one mechanism, measured on its own. An "evidence graph"
guardrail would bundle four, so it splits:

| rung | guardrail | position | mechanism |
|---|---|---|---|
| R10 | `claim_binding` | ACTION_SPACE | adds `bind`; `answer` submits claim ids instead of prose+value |
| R11 | `derivation` | ACTION_SPACE | adds `infer`; derived claims carry premises and inherited strength |
| R12 | `causal_strength` | AFTER | refuses a claim asserted as cause that rests only on correlational premises |

Three measured deltas instead of one bundle, and the question becomes *which part of the evidence
graph pays* — a better result than *evidence graphs help*.

`incoherent()` gains one rule: `claim_binding` without `governed_numbers` is incoherent, because
there is no governed result for a claim to bind to.

Nothing below R10 changes, so every published number stays recomputable.

## What happens to `Verdict`

`verify_answer` currently takes one number and returns one ruling. Per claim it returns one ruling
each, and the run-level outcome becomes a **stated policy** over them:

```
  TODAY                              PER CLAIM
  ─────                              ─────────
                                     c1 ─► binding faithful?      ok
  declared_value                     c2 ─► binding faithful?      ok
       │                             c4 ─► derivation valid?      ok
       ▼                             c5 ─► derivation valid?      FAIL — asserted, correlational
  verify_answer(…)
       │                             {c4, c5} ─► scope: does this SET answer the question?
       ▼                                          ← asked ONCE, not once per number.
  one Verdict                                       this is the R9 cliff's fix
  allow │ refuse                          │
       │                                  ▼
       ▼                             ┌─────────────────────────────────────────┐
  the WHOLE RUN                      │ strict  refuse the run       (= today)  │
  is refused                         │ prune   serve c4, drop c5, disclose     │
                                     │ hedge   serve c5 marked unverified      │
                                     └─────────────────────────────────────────┘
                                                   │
                                                   ▼
                                          one typed outcome
```

- **strict** — any failed claim refuses the run. Exactly today's semantics, so R0–R9 rows are
  reproduced bit for bit and the migration is provable.
- **prune** — drop failed claims, serve the rest, disclose what was dropped.
- **hedge** — serve everything, mark unverified claims.

`strict` is the default and the control. `prune` is the treatment that can move the frontier. Making
the policy an explicit, named knob rather than an implicit behaviour is what lets the two be
compared.

## The verifier splits into three narrower judges

`judge.verify_trajectory` takes eleven arguments today — a wide surface behind one question. Per
claim it separates into three questions that are each much narrower:

1. **binding faithfulness** — does this sentence describe this governed result? Near-deterministic:
   the value, unit and scope are all typed.
2. **derivation validity** — does this conclusion follow from these premises? The paper's `Verify`.
3. **scope** — does the terminal claim set answer the question? Asked **once, over the claim set**,
   not once per number.

(3) is the fix for the R9 cliff. The judge stops being handed one metric and a narrative question.

## What does not change

- **The data layer stays implicit.** No stored computation graph. The trace plus the semantic layer
  already give exact lineage — better than the paper's static AST walk, which cannot follow pandas
  mutation. They reached the same conclusion for weaker reasons (Appendix A.2).
- **`Answer` keeps its singular fields.** `value` / `source_metric` / `source_result` become derived
  from the terminal claim when there is exactly one. Every existing grader, report and stored row
  keeps working.
- **Run-level metrics stay the headline.** Claim-level coverage and risk are a second view, not a
  replacement. Publishing a claim-weighted frontier as if it were the old one would silently change
  what the article's numbers mean.
- **Memory stays "none" across runs** — but the anatomy table should stop saying "none" without
  qualification. The graph is within-run structured state, re-rendered into each turn's observation.
  A bound claim also survives `_TRACE_LIMIT` truncation, which raw stdout does not.

## Costs and open risks

- **Turn budget.** `max_iters=8`; VeriGraph ran 29 turns for its report case. A `bind` cannot
  reference a result from its own turn, so binding lags by one. The loop already permits several
  tool calls per turn, so a batch of binds costs one turn — but the cap may still need raising for
  R10+ cells, and raising it is itself a treatment that must be reported.
- **No fine-tuning.** VeriGraph's gains come from a trained policy; prompted structure ("Prompt-Veri")
  improved grounding but trailed it. We are in the prompted regime, so expect a smaller effect. The
  design must not assume compliance — hence enforcement at bind time rather than instruction.
- **Fingerprint churn** is contained: `Grounding.fingerprint()` changes only for cells with the new
  guardrails on, the same way `answer_schema` already varies with `governed_numbers`.

## Sequencing — measure before building

The cheapest decisive step needs **no agent change at all**.

Reconstruct claims post hoc from stored runs: decompose each answer into atomic claims and try to
tie each to a step, the way the paper's Grounding Rate does. This runs over all existing rows,
today, and answers the question the architecture is premised on — *are the R9 kills multi-claim
answers where most claims were grounded?*

If yes, R10–R12 is justified and the expected effect size is already known. If no, the cliff is
something else and the architecture would have been built on a guess.

Post-hoc reconstruction cannot change agent behaviour — it guesses provenance by matching, which is
the shape `after.py` already argues against. It is an instrument, not an architecture. But it is the
right first move.
