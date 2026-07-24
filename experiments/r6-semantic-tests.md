# R6+ — Semantic Tests: design & roadmap

Working notes for the **next rungs** of the reliability ladder. Each mechanism below is
its own rung: it adds exactly one capability, and it gets measured for its own
incremental boost, the same way R1–R5 each added one thing. Some may prove duds (the way
R2's cost warning added nothing) — that is a legitimate result, not a failure. Nothing
here is built yet; this is the plan.

> The old framing treated all of this as a single "R6". It isn't. It's a whole second
> half of the ladder (§8), built and measured one rung at a time.

---

## 1. Why R6 exists

R0–R5 drive confident-wrong on impossible questions from ~35% down to ~8%. The
residual ~8% is one class only: **a valid metric answering the wrong question**.

Every guardrail so far checks one of two things:

- **Existence** (the gate, R4): is the metric defined, is the period covered.
- **Access** (the fence, R5): no raw SQL, only governed metrics.

Neither ever checks **meaning**. The floor is entirely meaning errors: the number
is real, defined, and in coverage, but it answers a slightly different question.
R6 onward is the meaning layer — and it takes several rungs, not one (§8).

### The exact floor cases (still fabricate at the fence, R5)

Measured on run `20260721-221514` (gpt-5.4-mini, 50 questions × 2 reps):

| id | question | right answer | model returns | error type |
|---|---|---|---|---|
| `vw_total_users` | "How many users do we have in total?" | 2,500 (`count(dim_users)`) | 2,100 (`active_users`) | active-vs-total (subset) — **fails 2/2** |
| `vw_total_subscriptions` | "How many subscriptions have we sold in total?" | 457 (all rows) | 371 (`active_subscriptions`) | active-vs-total (subset) — fails 1/2 |
| `adv_dau_mau` | "Where's our DAU/MAU stickiness sitting lately?" | refuse (no such metric) | 0.547 (relabels `days_per_user`) | invented ratio — fails 1/2 |

Already handled at R5 (for contrast): `t1_total_habits`, `vw_arr`, `vw_paying_users`
(control), and the false-premise questions all refuse or answer correctly at the fence.

Two of the three failures are the **same** error: report the "active/current" subset
when the question asks for the "all-time total". That is a reconciliation invariant
(`active ⊆ total`), the most textbook check of the set. **`vw_total_users` is the clean
first target**: it fails reliably, and the fix is derivable, not hardcoded.

---

## 2. Core principles

These are the load-bearing ideas; everything else follows.

1. **Verification is safe to delegate; generation is not.** A verifier can only
   *tighten*: its outputs are accept/refuse. The worst it can do is miss an error or
   over-refuse a correct answer. It can never manufacture a served wrong number.
   Answering has the opposite failure mode (fabrication). So the model can be trusted
   to *check* an answer even where it can't be trusted to *produce* one.

2. **Give the critic more power than the producer.** Corollary of (1). The fenced
   analyst gets governed metrics only. A verifier — a deterministic rule or a judge
   agent — can be handed the dangerous tool (raw SQL, the whole warehouse) precisely
   because it can only veto. The channel to the user is the analyst's governed answer
   plus the verifier's veto; the verifier's raw-SQL findings never become a number.

3. **Push checks onto the metric layer, never onto the questions.** A per-question
   check (`if question == total-users: assert active ≤ total`) is hardcoding and
   re-opens the "graded my own homework" hole. Metric-level checks are `O(metrics)`,
   declared once, and cover every question that touches those metrics — including ones
   nobody wrote. This is the dbt discipline: test the model, not the query.

4. **Floor + lever.** Deterministic, derived checks are the guaranteed floor (they run
   always). Model-authored checks and the judge agent are the lever on top (general,
   probabilistic). Reliability rests on the floor; coverage comes from the lever.

5. **The whole layer is refuse-only, so its cost is over-refusal, not fabrication** —
   the currency we already spend.

---

## 3. The check taxonomy

Ordered; each depends on the one before.

1. **Additivity — *can* this be summed at all?** Precondition. Derived from the
   `agg`: `sum(…)` → additive; `count(distinct …)` → semi-additive (not over time);
   `avg(…)` / ratio → non-additive. Gates the next two: you can't reconcile by summing
   a ratio, or sum a distinct count across periods.

2. **Reconciliation — do the parts sum to the whole?** *Vertical.* Decompose the
   metric and check the pieces add up to what was reported. `total_users = internal +
   non_internal`. If the reported number equals *one branch* (active), it's a part
   masquerading as the whole. Uses the metric tree we already have.

3. **Cross-check — does an independent path agree?** *Horizontal.* Compute the *same*
   quantity a second, unrelated way and require agreement. `count(dim_users)` vs
   distinct user_ids seen in the activity fact. Works even on non-additive metrics
   (you recompute rather than sum). Two witnesses disagree → one is wrong.

4. **Decomposition — what is it made of?** The general form of (2)/(3): expose a
   metric's structure so its shape can be challenged. A metric whose decomposition is
   *activity* (value_moments = active_users × days_per_user × moments_per_day) is
   structurally the wrong shape for an *entity count* ("how many habits").

5. **Ambiguity detection — one term, several metrics.** When a question's entity maps
   to more than one metric at different grains (`users` → `active_users`, `total_users`,
   `power_users`), that under-specification is itself the flag. No intent-parsing
   needed: refuse the silent pick and force disambiguation ("say which"). A `not
   unique` test on the metric match.

---

## 4. Where checks come from (without hardcoding)

Three sources, least hardcoding first.

- **Derived from the definitions.** Our metrics are SQL with explicit filters and
  aggregations, so much falls out for free:
  - *Additivity* from the `agg`.
  - *Subset* from the `WHERE`: `active_users` is `total_users` **plus** `NOT is_internal`
    + a period filter, so `active_users ⊆ total_users`, derived by reading the compiled
    query. No metadata to hand-write.
  - *Grain* from the base table + time column (all-time entity count vs period flow).
- **Declared as governance.** Business invariants that can't be derived, written once
  on the metric layer like a dbt `schema.yml`: `MRR = ARPU × paying_users`,
  `sum(regional value_moments) = global`. Manual, but universal, not per-question.
- **Model-generated on the fly.** The model authors the verification plan for its own
  answer (see §5.5). General, adapts per metric, no annotation — but probabilistic, so
  it sits on top of the derived floor.

---

## 5. Mechanisms to build

### 5.1 Metric-SQL transparency  *(we missed this; basic; cheap)*
Expose the compiled SQL / filters of a governed metric to the analyst (and the judge).
Today the model calls `query_metric(active_users)`, gets 2,100, and never sees it
compiled to `… WHERE NOT is_internal AND active_date BETWEEN …`. Show the filter and the
substitution becomes visible: a metric with a `WHERE` the question didn't ask for is a
subset, not a total. New tool: `describe_metric(name)` → definition, filters, grain,
decomposition.

### 5.2 Deterministic filter/subset + additivity rules  *(the floor; no LLM cost)*
Read the compiled query. If the chosen metric applies a filter the question didn't ask
for → it's a subset; if the question asks for a "total/all", refuse and name the
unfiltered counterpart. Additivity read off the `agg`; block illegal summing. These are
hard rules, always on, no model needed.

### 5.3 Reconciliation / decomposition checks
Decompose the reported metric via the tree; verify parts sum to the reported whole, or
that the reported number isn't a single branch.

### 5.4 Cross-check checks
Recompute the quantity a second way (independent metric or raw count) and require
agreement within tolerance.

### 5.5 Model-generated verification harness  *(Workflows-style)*
Before a count/metric answer is served, the model emits a short **verification plan**
over governed primitives (`is_additive`, `decompose`, `reconcile`, `cross_check`,
`assert_relation`) — a harness generated for the task, à la Claude Code Workflows. The
system executes it deterministically; a red result forces refuse-or-correct.
- Leans on the **generation-vs-verification asymmetry**: writing the test is easier than
  getting the answer right, and the test is checkable.
- Risks a lazy/trivially-passing harness. Mitigations: make it **adversarial** ("write
  the test that refutes this"), **run it deterministically**, and **back it with the
  derived floor**.
- **Fence constraint:** the plan must be expressed over *governed objects* (or a narrow
  `assert(metric_a, relation, metric_b)` primitive), or it re-opens raw SQL. This also
  forces the missing metric to exist first (completeness).

### 5.6 Adversarial judge agent  *(the top of the ladder; raw SQL; refuse-only)*
A second agent whose sole job is to challenge the metric choice as hard as possible.
**It may use raw SQL** — safe because it only outputs a verdict (accept/refuse), never a
served number (principle §2.1–2.2). It inspects the chosen metric's SQL, runs raw
investigations (`count(dim_users) = 2,500` vs the reported 2,100), and vetoes
substitutions. Optionally a panel of N judges for high-stakes.
- Division of labour: **deterministic rules** catch the mechanical substitutions
  (filter→subset, wrong additivity); **the judge** catches what needs a look at raw data
  or semantic reasoning.

### 5.7 Ambiguity detection
When the term maps to several metrics, refuse the silent pick and force disambiguation.

---

## 6. How it kills `total_users` (end to end)

1. Analyst answers 2,100 via `active_users`.
2. **Deterministic check (5.2):** reads the compiled SQL, sees `WHERE NOT is_internal`,
   a filter the question never asked for, flags "filtered subset, question said *total*."
   *Enough on its own here.*
3. **Judge (5.6), if run:** raw SQL `count(dim_users) = 2,500`; `2,100 ≠ 2,500`; refuse.

Neither step is keyed to this question. Both read the metric's own definition and the raw
data, so they generalise to `total_subscriptions` and any future active-vs-total case.

---

## 7. Validation approach (cheap, focused)

Per the money constraint: pick one known-failing question, implement one mechanism, run
**two reps**, read the result. No broad sweeps until a mechanism is proven.

- **First target:** `vw_total_users` (fails 2/2, cleanest fix).
- **Next:** `vw_total_subscriptions` (same mechanism, free generalisation check),
  then `adv_dau_mau` (needs cross-check/ratio, not subset).

---

## 8. The semantic ladder (R6+): each mechanism is a rung

Ordered simplest/cheapest → most powerful. Each is built and measured on its own; the
experiment reports the **incremental boost per rung** (and the over-refusal it costs),
exactly as R1–R5 do. Not all need to ship — a rung that adds little gets cut, and that
too is a finding.

| rung | adds (one thing) | who controls | catches | LLM cost |
|---|---|---|---|---|
| **R6** | metric transparency — the analyst can see a metric's compiled SQL / filters (`describe_metric`) | model | tests whether *seeing* the `WHERE` is enough for the model to avoid the subset | ~free |
| **R7** | derived semantic gate — system reads the compiled SQL and refuses a filtered-subset answer to a "total/all" question; blocks illegal aggregation of non/semi-additive metrics; flags ambiguous terms | system | active-vs-total substitutions, wrong aggregation, one-term-many-metrics | ~free (no LLM) |
| **R8** | reconciliation — decompose via the tree, check parts sum to the whole (reported ≠ a branch) | system | subset-as-whole by structure; wrong-entity shapes | low |
| **R9** | cross-check — recompute the quantity an independent way, require agreement | system | non-additive and novel-quantity errors reconciliation can't reach | low |
| **R10** | self-authored test harness — the analyst emits a verification plan over governed primitives; the system runs it; red → refuse | model (refuse-only) | anything the model thinks to test; general coverage | +1 reasoning pass |
| **R11** | adversarial judge agent — a second agent challenges the metric choice, may use raw SQL, outputs only a verdict | separate agent (refuse-only) | semantic and raw-data errors the rules miss | ~2× |

Shape of the ladder:

- **The model/system axis repeats.** R6 (transparency) and R10 (self-authored harness)
  are model-controlled; R7–R9 are system-enforced and derived; R11 is a separate
  refuse-only agent. Expect the R1–R5 pattern again: the model-facing rungs help but
  wobble, the enforced ones hold.
- **Derived rungs are the floor; agent rungs are the lever.** R7–R9 run always and are
  cheap; R10–R11 add general coverage at LLM cost and can only tighten.
- **Redundancy is expected and useful.** R7's derived gate may already catch the
  active-vs-total class, leaving R8/R9 to show little on *those* cases but more on others.
  Measuring each in isolation is how we learn which checks actually buy performance.

### Build order (implement & test one at a time)

1. **R6 + R7** (transparency + derived gate). No / near-no LLM cost, most likely to pay
   off. Likely catches `total_users` outright. *If just showing the analyst the filter
   fixes it, that is a near-free result and a story on its own.*
2. **R8 / R9** (reconciliation, cross-check). Low cost; extend to `adv_dau_mau` and the
   non-additive cases.
3. **R10** (self-authored harness). General coverage.
4. **R11** (raw-SQL judge). The powerful, general top; build once the cheaper rungs are
   measured.

Each step: implement, run the target floor question **twice**, read the result, decide
whether the rung earns its place before moving on.

---

## 9. Harness integration sketch

- New reliability rung `rrung = 6`, with a `_RRUNG_VERIFY` prompt fragment in
  `grounding.py` (alongside `_RRUNG_TERMINAL/PRICE/CHECKS/ENFORCE/FENCE`).
- Extend metric metadata in `semantic_layer.yml` where needed (declared invariants); much
  is derivable from the existing `agg` / `default_filters`.
- New tools in `tools.py`: `describe_metric`, and a verification primitive
  (`assert_relation` / `reconcile` / `cross_check`) usable by the analyst harness and the
  judge.
- Add the derived checks to the gate path (post-answer verify stage); wire the judge as a
  second agent in `agent.py`, gated on `rrung >= 6`.
- Grade unchanged: a caught substitution becomes a refuse (`idk`) instead of `wrong`.

---

## 10. Open decisions

- **Harness authoring:** free-form plan (general, more over-refusal) vs a fixed menu of
  governed checks (tighter). Lean: start free, since it's refuse-only, and measure noise.
- **Enforcement split:** how much weight on the deterministic floor vs the judge lever.
- **Over-refusal budget:** R6 will decline some answerable questions; measure and report
  it, as with every other rung.
- **Does the judge undercut the fence story?** No, if framed right: the *analyst* stays
  fenced; the *critic* gets raw SQL and can only veto. Needs a clear beat in the article.

---

## 11. Article payoff

R6 flips the thesis. R0–R5 constrain *what the analyst can do*; R6 makes it *prove its
answer passes tests the system ran*, before the number is allowed out.

- "An AI analyst that ships its work with a green test suite" / "as testable as a dbt
  model."
- "I took raw SQL away from the analyst, then handed it to the analyst's critic. A critic
  with raw SQL can check anything and can only ever say 'that's wrong.'"
- Expectation: the floor drops from ~8% to low single digits, and the residue becomes a
  smaller, more honest thing — true intent ambiguity, not sloppy substitution.
