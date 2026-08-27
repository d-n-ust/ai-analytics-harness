# Step 1 and step 2 — reading the harness before changing it

The brief (`three-state-experiment-brief.md`) asks for a stop-and-report after step 1 ("confirm how
`clarify` is currently handled end to end and where those turns land in the current scoring") and
after step 2 ("size Pile C against the noise band"). This is both reports. No code has been changed.

Every number below is computed from the repository as it stands at `c6ce983`, from the 5,985
archived rows in `results/published/2026-07/runs/` and from the layer YAML. Nothing is typed from
memory.

---

## 1. Where the brief's assumptions differ from the repository

| brief says | repository |
|---|---|
| `evals/selective.py` | `harness/evals/selective.py` (PR #10 modularised the tree) |
| `results/published/2026-07/cells.csv` | correct, and it already carries an `outcome_clarify` column |
| "no question in the suite has clarification as its correct outcome" | half true. `expect.type: clarify` exists in `schema.json` and in `grade.py` and is used by **zero** cases. `expect.type: ambiguous` exists and is used by **three** cases, where a refusal *or* a clarification is graded correct |
| "the `clarify` terminal tool already exists in the agent's action space" | correct, and it is offered **unconditionally** at every rung and every guardrail cell, including R0 |
| run-to-run spread: BA 86.5–90.0%, coverage 79.5–85.9% | the published spread is wider: BA 84.5–91.9%, coverage 75.0–87.2%. It is also **not a clean replication** — see §5 |

The three `ambiguous` cases are `adv_whales`, `amb_healthiest_region`, `amb_best_channel`. They are
not Pile C in the brief's sense. Each names a term the layer does **not** govern ("whales",
"healthiest market", "best channel") that has two plausible governed *readings*. The brief's Pile C
is the opposite shape: the concept **is** governed, twice. Refusing is correct on an `ambiguous`
case and wrong on a Pile C case, so the two cannot share a label.

---

## 2. Step 1 — `clarify`, end to end

### 2.1 The path

| stage | file | what happens |
|---|---|---|
| action space | `engine/src/agent/guardrails/action_space.py:102` | `offered.append(schema("clarify"))`, outside every conditional. Present at R0–R9, present at every rung, present in every Shapley cell |
| tool schema | `engine/src/agent/tools.py:75` | one field: `question` (free text). No coded reason, no candidates |
| prompt | `engine/src/agent/prompts.py:38,40` | R0: "if the question is too ambiguous to attempt, end with `clarify`". R1+: "`clarify` when the question is too ambiguous to answer either way" |
| loop | `engine/src/agent/loop.py:296` | `outcome="clarify"`, `reason="clarify"`, `abstained=True`. Kept distinct from `refuse` deliberately: "a refusal is terminal, and a clarification is resumable" |
| grader | `harness/evals/grade.py:201` | `correct = accepts_clarify or missing_context`; `bucket = "idk"` |
| metrics | `harness/evals/selective.py` | **nothing reads `outcome == "clarify"`** |
| report | `publish_metrics.py:110` | counted as `outcome_clarify`, a descriptive column that feeds no rate |

At R0 the `refuse` tool is absent, so `clarify` is the **only** decline channel the agent has. The
nine clarifications at R0 are not an ambiguity signal; they are refusals wearing the only available
exit.

### 2.2 Where the turns land

`selective()` splits on `expected_refuse` and then on `outcome == "answer"`. A clarification is
never an answer, so:

| pile | what `selective()` does with a clarification | effect |
|---|---|---|
| A (`expected_refuse` false) | falls out of `answered`, so it lands in `over_refused = answerable − answered` | costs coverage, and counts as a miss in Pile A accuracy |
| B (`expected_refuse` true) | `refused = len(b) − served`, and `served` counts only `fabricated`/`confident_wrong`/`off_governance` | **counted as a correct refusal**, and lifts balanced accuracy |

Verified by running `selective()` on a single synthetic row of each shape.

So the current metrics reward clarifying on Pile B and punish it on Pile A, and neither effect is
visible in any published column.

### 2.3 How much of this is in the published numbers

296 clarifications in 5,985 archived rows (4.9%), across four published runs.

| | n |
|---|---|
| clarifications, total | 296 |
| … on Pile B | 210 |
| … on Pile A | 86 |
| Pile B clarifications on a `refuse`-type case: **graded wrong by `grade.py`, counted as a correct refusal by `selective.py`** | 188 |
| Pile A clarifications on a case with `requires`: **graded correct by `grade.py`, counted as an over-refusal by `selective.py`** | 76 |
| clarifications where the grader and the published metrics disagree | **264 of 296 (89%)** |

The 76 are almost all one question, `t4_retention_trend`, asked at rungs with no knowledge base.
The grader was widened for exactly that case; the metrics were not.

There is a second, smaller inconsistency already in the CSV. `answerable_over_refused` (from
`selective`) counts clarifications; `over_refused_answerable` (from `publish_metrics`) counts only
`outcome == "refuse"`. The difference between those two columns is the Pile A clarification count,
which means over-clarification is already recoverable from the published files without a new run.

### 2.4 What this means for the zero point

The zero point the brief asks for in §7.5 is partly already measurable. It does not need Pile C to
exist to say: **the current best configuration clarifies 2.3%–12.3% of the time, none of it is
scored as clarification, and 89% of it is scored two contradictory ways.**

---

## 3. Step 1 finding that changes §2.4 of the brief: the cost ordering is wrong

The brief predicts "refuse is cheapest, answer is middling, clarify is most expensive", and calls
the inversion against consequence "the strongest sentence in the article".

Measured on 5,973 archived non-error rows:

| outcome | n | median total tokens | mean total tokens | median wall-clock |
|---|---|---|---|---|
| answer | 3,267 | 9,919 | 13,301 | 5.9 s |
| refuse | 2,410 | 11,839 | 15,499 | 6.2 s |
| clarify | 296 | 12,735 | 15,590 | 6.4 s |

Pooling across configurations is confounded (low rungs answer more and have shorter prompts), so the
same comparison was run **within** each of the 29 configurations that produced at least five of each
outcome:

| cheapest → dearest, by median total tokens | configurations |
|---|---|
| answer < clarify < refuse | 11 |
| answer < refuse < clarify | 10 |
| clarify < answer < refuse | 5 |
| refuse < answer < clarify | 3 |
| **the brief's predicted order (refuse < answer < clarify)** | **0** |

Answering is the cheapest action in 21 of 29 configurations. Refusing is cheapest in 3.

The inversion the brief wants is real, and it is stronger than the version predicted. The correct
sentence is not "clarify is the most expensive action". It is: **answering is the cheapest action
the agent can take, and the confident wrong number is a member of that class.** Declining, in either
form, costs about 30% more tokens than answering, because the agent runs more checks before it
declines.

One configuration inverts even that. At R9 the judge adds a model call to answers only, so an answer
takes 12.5 s against a refusal's 7.3 s. The guardrail that makes answering safer is the one thing
that makes answering slow.

Wall-clock separation between the three outcomes is otherwise about 0.5 s, which is inside the
noise. The latency half of §2.4 will not carry a finding on first-turn data. It would need the
second round trip, which the harness does not simulate.

---

## 4. Step 2 — the fixture cannot supply Pile C as specified

### 4.1 `k`, computed

The layer declares, per metric, four facets of what is measured (`entity`, `agg`, `base`, `unit`)
and three of scope (`segment`, `default_filters`, `time_column`). `semantic/ambiguity.py` already
uses that split. Clustering the 17 governed metrics by the four meaning facets gives `k` with no
name matching and no model:

| k | cluster |
|---|---|
| **2** | `value_moments`, `real_value_moments` |
| 1 | the other fifteen metrics, each alone |

`bench ambiguity` agrees from the other direction: 17 confusable name pairs, **2 rated high**, and
both are the same concept (the second is the tree node `weekly_value_moments`, a third public name
resolving to `real_value_moments`).

**The fixture supplies exactly one contested concept.** Not four clusters, not a family. One.

Relaxing the rule to entity+base+unit adds `active_users ~ power_users` and `mrr ~ arpu`, but those
differ in aggregation, so they measure different things and a question cannot be satisfied by
either. They are not k ≥ 2.

### 4.2 The one cluster is the layer's most-used metric, which breaks the enforced gate

Across 3,267 archived answers, 1,566 declared a `source_metric`:

| | n | share of declaring answers |
|---|---|---|
| declared a metric in the k ≥ 2 cluster | 631 | **40.3%** |
| … on Pile A | 556 | |
| … on Pile B | 75 | |
| distinct Pile A questions that touched the cluster | **12 of 26** | 46% |

The twelve include every diagnostic question (`t5_*`), `t4_business_health`, and the four "how many
value moments came from X" lookups. The metric tree's root is `weekly_value_moments`, so decomposing
the North Star touches the cluster by construction.

An enforced k-gate defined as membership lookup on the selected metric would fire on roughly two
answers in five and convert most of the diagnostic tier into clarifications. That is the brief's own
first falsification condition — "over-clarification on Pile A exceeds the silent-error reduction on
Pile C" — and on this fixture it is not a risk. It is arithmetic.

### 4.3 The four Pile A "value moments" cases are arguably Pile C already

`t1_ios_value_moments_june`, `t2_web_value_moments_june`, `t2_americas_value_moments_june` and
`t4_apac_value_moments_q2` all ask "how many value moments came from X in period P". Each declares
`metric: value_moments` and a `gold_sql` that counts every row, including internal and test
accounts. `real_value_moments` answers the same English question and excludes them.

The consequence is already in the published numbers:

| qid | metric declared | n | graded correct | graded confidently wrong |
|---|---|---|---|---|
| `t2_americas_value_moments_june` | `value_moments` | 40 | 26 | 14 |
| `t2_americas_value_moments_june` | **`real_value_moments`** | **8** | **0** | **8** |

Eight attempts served 22,872 where the gold says 24,042. Both numbers are governed. Both are
defensible. The suite calls one of them a confident error because the case author picked an arm and
did not record that a choice was being made. That is the article's opening scene, and it is already
measured.

It is also a comparability problem. Moving those four cases from Pile A to Pile C changes coverage
and balanced accuracy for every cell ever published. The brief's instruction to "extend rather than
replace, so the July numbers remain comparable" and the correct labelling of those four cases cannot
both be honoured in one suite.

### 4.4 Divergence is per-slice, not per-pair

`harness/scratchpad/ambiguity/04_divergence.md` already prices the flagship pair against this
warehouse:

| | value_moments | real_value_moments | Δ% |
|---|---|---|---|
| all rows | 67,132 | 64,257 | 4.28% |
| platform = unknown | 1,628 | 1,618 | **0.61%** |
| channel = paid_search | 13,898 | 13,077 | **5.91%** |

Two consequences for the brief.

First, §2.2's divergence weight is computable, and the existing tolerance already interacts with it:
a 4.87% divergence on the Americas slice exceeds the 2% grading tolerance, which is why the eight
`real_value_moments` answers were caught. A 0.61% divergence would not have been.

Second, the "divergence threshold" lever in §4 is **not** a static index lookup. The pair diverges by
ten times as much on one slice as on another, so a threshold gate has to execute both candidates at
the requested slice. That is a different mechanism from the membership lookup, and it should be named
as one: it costs one extra governed query per gated call, and in exchange it produces both numbers,
which is exactly the decision brief §1.4 asks for.

---

## 5. Step 2 — the noise band does not exist yet

The brief's discipline list requires "run-to-run spread for at least one configuration repeated ≥5
times". `cells.csv` appears to contain that: five R9 / gpt-5-mini / 171-row cells. They are not
replicates.

| run | main reasoning | verifier model | verifier reasoning | surface fingerprint | clarify |
|---|---|---|---|---|---|
| 20260727-140714 | minimal | gpt-5-mini | low | 5e2d95ee5997 | 5 |
| 20260726-200930 | minimal | gpt-5-mini | low | **d34f1184aa97** | 10 |
| 20260726-215928 | **low** | gpt-5-mini | low | 5e2d95ee5997 | **21** |
| 20260726-220152 | minimal | **gpt-5.6-terra** | low | 5e2d95ee5997 | 4 |
| 20260726-222055 | minimal | gpt-5-mini | **minimal** | 5e2d95ee5997 | 8 |

Three of the five differ in a treatment variable. The two that agree on treatment differ in tool
surface. The run with the highest clarification count is the run with more reasoning effort, which is
a finding rather than noise.

So the published band (coverage 75.0–87.2%, BA 84.5–91.9%) is an **upper** bound on noise that
includes real effects. Treating it as noise makes the experiment under-powered on paper and
over-cautious in practice; treating it as clean would be wrong in the other direction.

**Recommendation: run five true replicates of one configuration before sizing anything.** At
$0.0023/row that is 855 rows for about $2 and a few minutes at concurrency 8. It is the cheapest
item in the entire plan and everything downstream is priced against it.

### 5.1 Clarification is the least reproducible outcome in the harness

Within one run (20260727-140714, ten configurations × 57 questions × 3 reps), the three reps of a
(config, question) cell disagreed on the outcome 21.6% of the time. Restricting to cells where any
clarification occurred:

| clarifications among the 3 reps | cells |
|---|---|
| 1 of 3 | 35 |
| 2 of 3 | 12 |
| 3 of 3 | 5 |

Clarification is close to a coin flip on the questions where it happens at all. It is not a stable
property of a question. Only 19 of 57 questions ever produced one, and three questions account for
29 of the 74 in that run.

### 5.2 Sizing

Design effect from the five "R9 repeats", treating all five as replicates (an upper bound, per §5):

| | |
|---|---|
| mean clarify rate | 0.0561 |
| observed variance of the five rates | 0.001583 |
| binomial variance at n = 171 | 0.000310 |
| **design effect φ** | **5.11** |

Attempts required per arm, 80% power, α = 0.05 two-sided:

| clarify rate, from → to | φ = 1 | φ = 2 | φ = 5.11 |
|---|---|---|---|
| 5% → 15% | 140 | 280 | 716 |
| 5% → 25% | 49 | 98 | 250 |
| 5% → 50% | 14 | 28 | 73 |
| 5% → 80% | 5 | 11 | 28 |
| 20% → 50% | 38 | 77 | 197 |

Read the other way: given a Pile C of Q questions × R reps, the smallest jump from a 5% base that
clears the band.

| Q | R | attempts | φ = 1 | φ = 2 | φ = 5.11 |
|---|---|---|---|---|---|
| 8 | 3 | 24 | +32 pts | +50 pts | +80 pts |
| 12 | 3 | 36 | +25 pts | +39 pts | +67 pts |
| 12 | 5 | 60 | +17 pts | +28 pts | +50 pts |
| 20 | 5 | 100 | +12 pts | +20 pts | +37 pts |
| 30 | 5 | 150 | +10 pts | +15 pts | +28 pts |

**The conclusion the brief asked for.** The *enforced* k-gate needs no power at all: it moves the
clarification rate to ~100% by construction, and measuring it confirms that code runs. The arm that
needs statistics is the **advisory** one, where the model chooses, and a plausible advisory effect
(5% → 25%) needs 49 attempts per arm on the optimistic noise assumption and 250 on the pessimistic
one. A twelve-question Pile C at three reps cannot see it. At five reps it can see the optimistic
case only.

Over-clarification on Pile A is worse served. The reliability suite holds 26 Pile A questions, so at
three reps that is 78 attempts, enough to detect a rise from 5% to about 22% at φ = 1 and nothing
useful at φ = 5. The enforced gate's over-clarification will be large enough to see (§4.2 predicts
roughly 46% of Pile A questions affected); a subtle advisory effect will not be.

Cost is not the binding constraint anywhere. At $0.0023/row on `gpt-5-mini`:

| design | rows | cost |
|---|---|---|
| July lattice (24 coherent cells × 57 q × 3) | 4,104 | $9 |
| + 1 independent lever (48 cells) | 8,208 | $18 |
| + 2 independent levers (96 cells × 69 q × 3) | 19,872 | $45 |
| + 2 levers, 69 q × 5 reps | 33,120 | $75 |

Reps are affordable. Reps also only fight binomial noise, not the run-to-run component, so buying
power with reps has a ceiling that §5's replication run will locate.

---

## 6. The methodological tension in "k is computed, not authored"

The brief makes two claims that cannot both hold as stated.

1. §1.1: "`k` is a property of the question against the data model … It is computed, not authored.
   This is the central methodological claim."
2. §1.3: "Do not attempt NL-question-to-grounding matching; that is retrieval and it will wobble.
   Check the *selection*, not the question."

Mapping a question to its candidate groundings is precisely the step §1.3 forbids. What is actually
computable is the **cluster** (a property of the layer). What is authored is the **attachment** of a
question to a concept.

There is a clean resolution, and it strengthens the design rather than weakening it:

> Build each Pile C question **from** a cluster rather than labelling it against one. Take the
> cluster, phrase a question at the shared concept, and k ≥ 2 holds by construction. Then compute
> the *value* of k at runtime by executing every candidate in the cluster at the requested slice and
> counting how many produce materially different results.

This gives a k that is genuinely computed, needs no model, produces the divergence weight for §2.2
and the two numbers for the decision brief in §1.4, all from the same operation. The static cluster
index becomes what it should be: the index that says which candidates to execute.

It also relocates the circularity risk, which is worth stating plainly in the article. The brief
worries that preflight both labels and gates. The sharper risk is that the question **generator** and
the gate share one cluster index, so the questions are guaranteed to be gateable. Hand verification
addresses whether each candidate genuinely answers the question. It does not address whether the pile
is representative of ambiguity an agent meets in the wild. That limitation should be stated rather
than tested away.

---

## 7. Levers — what the ladder can and cannot inherit

| brief's lever | position | state of play |
|---|---|---|
| typed `clarify` outcome | action space | **the analogue does not reproduce.** `clarify` is already offered at R0–R9. R1's refuse tool was the largest single move because R0 had no decline channel at all; there is no equivalent "before" here. What *can* be measured is the schema upgrade: today `clarify` carries one free-text `question` and no code, where `refuse` carries a twelve-value enum. Adding a coded reason and named candidates is a real action-space change. Measuring "no clarify at all" requires a new cell below R0, which is legitimate as a new cell but does not extend the published ladder |
| k-lookup | action space | small and well precedented. `_CHECK_TOOLS` is a four-name tuple in `action_space.py:23`; a fifth follows the same path. It sits inside the `check_tools` guardrail, which the Shapley lattice holds ON as a constant, so it needs its own flag to be attributable |
| k-gate | before | fits `Position.BEFORE` beside `coverage_check` and `resolve`. §4.2 is the problem, not the mechanism |
| divergence threshold | before | not a static lookup. See §4.4 |
| judge ambiguity stop | after | the conflict the brief wants to watch is real and cheap to isolate: `trajectory_verify` × k-gate is a 2 × 2 |

The lattice cost is exact. `incoherent()` admits 24 of the 64 cells over the six varied guardrails.
Each independently-switchable lever doubles that: 48 cells with one, 96 with two. Adding all five
proposed levers is 768 cells and is not a plan. A reduced design that varies
{`governed_numbers`, `trajectory_verify`} × {typed clarify, k-gate} is 4 × 4 and answers the
question the brief actually cares about.

One standing conflict: `docs/FINDINGS.md` §9 lists "rename `value_moments` / `weekly_value_moments`"
as open work item #6, "the largest single defect we have not touched". Doing that rename removes the
only k ≥ 2 cluster in the fixture. The two pieces of work are mutually exclusive on one layer.

---

## 8. What has to be decided before step 3

**Decision 1 — which fixture carries Pile C.**

| option | contested concepts | reuses | cost |
|---|---|---|---|
| **A.** main layer as-is | 1 | everything: R0–R9, `selective`, Shapley, the messy warehouse | cannot support the pile |
| **B.** main layer + 3–5 authored irreducible forks | 4–6 | everything, but `surface_fingerprint` changes and July baselines need re-running to stay comparable | one layer change, one re-run of the reference cells |
| **C.** experiment 05's `one_warehouse` before-arm | 4 high clusters already built and scanned | preflight, the before/after arms | its own runner; no ladder, no `selective`, no Shapley |

The recommendation is **B**. Option C's clusters are mostly the *reducible* kind — six aliases for
active users, `mrr` beside `monthly_recurring_revenue` — which is the ambiguity experiment 05 already
measured and whose answer is "delete the duplicates". Pile C needs the *irreducible* kind, where both
definitions have a legitimate consumer and no rename can collapse them. The fixture holds exactly one
of those today. Three to five more must be authored deliberately, each with a named downstream
consumer, which also supplies the decision brief's "which consumers use each".

**Decision 2 — the four mislabelled Pile A cases.** Relabelling them is correct and breaks
comparability with every published cell. Leaving them breaks the experiment's own premise. The
suggested split: freeze the 57-question reliability suite exactly as it is, add Pile C as new cases,
and report the relabelling of those four as a separate, explicitly-flagged analysis. That way the
July numbers stay quotable and the finding still gets published.

---

## 9. Ready to run before any of that is decided

1. **Five true replicates of R9** to establish the actual noise band. ~$2, minutes. Everything is
   priced against it.
2. **Regrade the four archived runs under the current grader.** The archived rows were graded before
   `ambiguous` existed, so all 296 clarifications carry `correct: False`, including the 22 on
   `adv_whales` that the current grader would pass. `bench regrade` exists.
3. **Reconcile `grade.py` and `selective.py` on clarify** — the 264-row disagreement in §2.3 —
   before adding a third pile on top of it.

---

## 10. What was not checked

- The second round trip. The harness has no user simulator, so clarification abandonment (§2.3 of the
  brief) is unmeasurable today, and the first-turn cost of a clarification is a truncated cost.
- Whether preflight run against the main `semantic_layer.yml` reproduces the one cluster the
  in-repo `ambiguity.py` finds. The agreement number the brief asks for in §1.2 has not been
  computed; `adapt_semantic` exists in preflight 0.4.0 and the check is cheap.
- Anything on a second model, beyond what `cells.csv` already reports. `gpt-5.6-terra` produced
  **0 clarifications across its two published cells (342 attempts)** and `gpt-5.6-sol` produced 3 in
  171, against `gpt-5-mini`'s 4.9%. Whichever way the ladder goes, a model that never reaches for the
  tool is a finding, and it means the model sweep cannot be an afterthought.
