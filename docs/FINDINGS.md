# Findings ledger — what we ran, what it showed, what is still open

One place to reason from. Every number here is traceable to a commit or a stored run; where a
number is not established, it says so. Ordered by what it would take to publish, not by date.

Companion to `RELIABILITY.md` (the guardrail experiment), `ARCHITECTURE.md` (the three axes),
`REPAIR-MATRIX.md` (the warehouse experiment) and `TRUST-MODEL.md` (why gold-needing and gold-free
metrics must not be averaged).

---

## 1. The headline metrics, and what each is for

Four numbers, reported side by side and never blended (`harness/evals/selective.py`).

| metric | the question it answers | needs gold? |
|---|---|---|
| **coverage** | of the questions that HAVE an answer, how many did it attempt | yes |
| **balanced accuracy** | did it do the right thing on BOTH answerable and unanswerable | yes |
| **silent error rate** | how often was it confidently wrong in a way nobody would notice | yes |
| **grounded-answer rate** | of the answers it served, how many can be CHECKED end to end | **no** |

The first three ask whether the agent was RIGHT. The fourth asks whether a reader could tell.
They do not move together, and that is the point — see §3.

**Established names** (researched 2026-08-02, four parallel literature sweeps):

- coverage and selective risk are El-Yaniv & Wiener, JMLR 2010. We should cite, not re-derive.
- "silent error rate" is formalised as **AUGRC** — *"the average risk of undetected failures"* —
  Traub et al., NeurIPS 2024, which also publishes a critique of the incumbent AURC.
- our per-claim traceability is **Grounding Rate** (VeriGraph, arXiv 2606.16603, 87.61% reported).
  Our answer-level all-or-nothing roll-up has no published name; the closest precedent is
  OpenAI's *"% of responses with 1+ major incorrect claims"* in the GPT-5 system card.
- "unused evidence" (our `orphans`) is **unattributed chunks** (Galileo) / **unused**
  (ReasoningFlow). The literature treats it as diagnostic, never as a quality penalty — which is
  independently where we landed (§4).

**Rejected after consideration:** Effective Reliability `Φ_c` (Whitehead et al., ECCV 2022). It
prices a wrong answer against an abstention, which sounds like exactly what we want, but it scores
a correct refusal as 0 — and 93 of our 171 questions SHOULD be refused, so it awards nothing for
the agent's main job. Balanced accuracy already covers both piles, needs no hand-set parameter,
and has the same natural floor (an always-refuse and an always-answer agent both score 50%).

---

## 2. The evidence graph: what it is, and what it is not

An answer is a numbered list of claims. Each carries EITHER `sources` (citations addressing one
value in one executed tool call, as `handle:field`) OR `premises` (indices of earlier claims).
Carrying both is itself a defect. So the graph is bipartite by role: measurements cite evidence,
conclusions cite claims.

Seven defect codes per claim (`engine/src/evidence/claims.py`): `unresolved`, `unsourced`, `value_mismatch`,
`mislabelled`, `bad_premise`, `mixed_support`, `composed`. Six structural descriptors per answer:
`derived`, `max_depth`, `max_fan_in`, `correlational`, `orphans`, `sources`.

**The structural advantage, stated plainly because nobody else has it.** Every attribution metric
in the literature — AIS, AutoAIS, ALCE, RAGAS, TruLens — is judge-dependent, because citations
point at *text* and the question is entailment. Ours point at *query results*, so resolution is a
dictionary lookup: deterministic, re-executable, no NLI model, no judge drift.

**The limit that must be published with it.** The graph captures the EVIDENCE and loses the
ARGUMENT. Over 726 stored answers carrying premise links:

```
depth 0 (flat list of measurements)   511 = 70.4%
depth 1                               203
depth 2                                12
```

Seven in ten answers contain no conclusion at all. The model puts its numbers in the graph and
its reasoning in the prose beside it.

**And there is a lever, which is confounded.** With `rendered` on — the harness writes the
measurement sentences from the cited values, so the model can only write inferences — answers
with any conclusion go from 13–21% to **74.5%**, and on diagnostic questions from 43–45% to
**91.7%**. But that arm also carries `role` framing, so two changes moved together and neither is
attributable. **This is the single most valuable unrun experiment we have.**

---

## 3. Citation repair — measured, replicated, and bounded

`R9/claims` against `R9/claims+repair`, rung 7, gpt-5-mini, 171 attempts per arm.

```
                          coverage   bal.acc   silent   grounded   out tok/row
declares nothing (R9)       93.6%     96.2%     0.6%      n/a          228
claims                      91.0%     93.7%     1.8%     88.0%         339
claims + repair             87.2%     93.6%     0.0%     93.1%         342
```

**Asking for an account does not measurably change the answer.** Every difference against R9 is
within noise — coverage 68/78 vs 73/78 (Fisher p = 0.28), answerable-correct 69/78 vs 74/78
(p = 0.25), unanswerable-refused 70/93 vs 72/93 (p = 0.86). It costs **50% more output tokens**.
Recorded as a null with stated power: at 78 answerable questions per arm this could only ever have
caught a large effect.

**Repair moves the fourth number and only the fourth**, and it replicates across two independent
sweeps the same day: 88.2 → 94.6 and 88.0 → 93.1. First result in this project measured twice.

**`grounded` is `n/a` for R9, not low.** That arm produces no graph, so the failure is not that
its work fails an audit — it is that no audit is possible. This is the cleanest one-line argument
for the whole third axis.

**It repairs rather than deletes.** A citation naming nothing has two cheap fixes and only one is
intended; both end with `unresolved == 0`, so the stored after-state reported the same success for
either. Recording the before-state (`41e480c`) separates them. Pooled over every instrumented run:

```
11 answers handed back · 27 broken claims · 0 left unresolved
  came back with FEWER claims:  0        same size: 8        larger: 3
```

**The signature is the COUNT, not the text.** A first pass matched opening characters and reported
7 deletions, all wrong — those answers went 3 claims to 11, 3 to 5, 2 to 3. The model had
*reworded* while fixing. Nobody deletes their way to more claims.

**Not established:** the exact repair rate (27 claims), and whether any of this matters on a
stronger model — repair has never fired on gpt-5.6-terra, but that rests on 15 answers with a
graph, where an 8% rate predicts ~1. We have almost no evidence either way.

---

## 4. Things we tested and rejected

Kept because a rejected idea is worth as much as a kept one, and because both of these looked
compelling before the tier control.

**Orphan repair.** Handing an answer back when it gathered a measurement and concluded without it.
Rejected twice over. The signal is Simpson's paradox — aggregate 8.5% vs 27.3% wrong (p=0.0012),
and controlled for tier it vanishes entirely, because orphans occur only in the hard tiers and
never in filtered/lookup/metric. And the intervention has a perverse incentive: the cheapest way to
satisfy an orphan repair is to DELETE the measurement, so a repair whose easiest compliance is
hiding evidence is a training signal for opacity. Kept as a displayed fact, never a gate.

**Broken citations as a correctness predictor.** Same trap, found the same way. Aggregate 17.0% vs
1.7% on answers the judge passed; within tier it predicts nothing (diagnostic 3% vs 0%, knowledge
1% vs 0% — *better* with a broken citation). The case for repair was never that it predicts a wrong
answer; `engine/src/agent/protocol.py` already says it "cannot stop a wrong number, only an unaccountable
one", and the measurement agrees with the docstring.

**Showing orphans to the judge.** Refuse-only, so a difficulty-correlated signal can only cost
coverage on the tiers where the agent is nearly always right.

**The reachability test.** ReasoningFlow reports that 79.6% of reasoning errors never connect to
the final answer, which would explain both nulls above and suggests scoring only claims that are
ancestors of the conclusion. **Not runnable here:** 9 answers across every stored run have both a
broken citation and an argument for it to be off the path of. Blocked by §2 — you cannot measure
reachability in a graph with no conclusions.

---

## 5. The semantic layer is what made the failures diagnosable

The pattern is easy to miss because most fixes LAND in `engine/src/agent/` — that is where the check lives —
while the DIAGNOSIS repeatedly points at the layer.

**Four failures diagnosed one at a time, and where each actually resolved:**

| case | wrong | root cause | where the fix landed |
|---|---|---|---|
| `adv_dau_mau` | 35% | a cross-grain ratio read as "a comparison of two active_users results" | grain became part of the comparison key — `engine/src/semantic/semantic.py` gained `additivity()` derived from `agg` + `time_column` (`eddc7b0`) |
| `u_pricing_cause` | 15% | the tree said NO about a term it had never modelled | four-state causality in `engine/src/semantic/tree.py` — PROVEN / CORRELATIONAL / NOT_ENCODED / UNKNOWN (`4a6925f`) |
| `adv_last_week_oob` | 12% | refusal asserted "composed from different metrics" when nothing was queried | `engine/src/agent/guardrails/after.py` only (`13a4804`) |
| `t2_paid_search_spend_q2` | 38% | the channel filter is omitted and the total served as the segment | **UNFIXED** — the deterministic detector does not exist because the member vocabulary is unsafe for prose scanning, which is a LAYER property |

**The biggest single unfixed defect is a layer naming defect.** `mislabelled` fires on **28% of
answers**, almost all of it `value_moments` against `weekly_value_moments` — two governed names a
quarter of a point apart. It is excluded from the grounded-answer gate for exactly this reason
(`cfcc4cc`): requiring it would drop the number from 94.6% to 70.3% and report our naming problem
as the agent's failure. The ambiguity lint (`engine/src/semantic/ambiguity.py`, `14f2b0c`) flags the pair with
no run at all — the defect is visible from the declarations alone.

**On 2026-08-02 the layer caught three authoring errors of mine, in a row.** Each time I wrote a
question against data the layer deliberately sets aside, and each time the model was right and I
was wrong:

- APAC growth "last quarter" — APAC launched **2026-05-01** (`region.APAC.available_from`), so
  April is pre-launch test data. gpt-5.6-terra refused 15/15 naming exactly that; gpt-5-mini
  scored 10/15 by computing on rows it should never have touched.
- a channel question whose answer was `partnerships` — marked **`test: true`** and excluded from
  the `real_acquisition` segment. 15 of 18 models converged on a different channel.
- a revenue-trend question — `mrr`, `arpu` and `paying_users` are **point-in-time** and take no
  period at all, so the question is inexpressible.

**The conclusion, stated carefully.** It is not that most fixes are semantic-layer fixes; by commit
count they are not. It is that **the layer is what makes a failure nameable and a refusal
defensible.** Where the layer declares something — a launch window, a test channel, a grain, a
point-in-time measure — the agent refuses correctly and can say why. Where the layer is silent or
ambiguous, the agent guesses and no check can catch it, because there is nothing to check against.
The 28% mislabel rate is the same fact from the other side.

---

## 6. Model behaviour — two failure shapes, not a ranking

Eight new hard cases (2026-08-02), 30 attempts each, two models × three protocol arms.

```
case                                    gpt-5-mini   gpt-5.6-terra
u_july_partial_month                       0/15         15/15
t5_offsetting_mid_may                     14/15          2/15
t5_apac_growth_breadth                    11/15          9/15
t2_only_region_improving_frequency         9/15          4/15
t2_only_platform_improving_frequency       9/15         10/15
t2_biggest_absolute_user_growth            0/15         14/15
amb_healthiest_region                      2/15         15/15
amb_best_channel                           2/15         15/15
```

**They fail in opposite directions.** The small model is eager: it answered the partial-month trap
15/15 and explained a "drop" that is 12 days measured against 30 — in 5 of those it had already
written the July cut-off date itself. The large model is cautious: on the mid-May question it
pulled the DEFAULT week from `decompose_change`, got July's figures, wrote *"For the requested week
of 11 May 2026…"* and refused. Right reasoning, wrong period, described as the right one — and the
claim audit cannot see it, because the citation resolves to a real result and only the PROSE
asserts those values are May's.

**The sharpest separation is on questions with no right answer.** Both ambiguous cases: terra
clarifies or refuses 15/15, mini guesses a reading and serves it 13/15.

**Not a ranking.** One dataset, one configuration, and terra ran at minimal reasoning with itself
as judge at low reasoning — in the full sweep it declined 28 of 78 answerable questions, 15 of them
killed by our own judge. That is a handicap we imposed, not a property we measured.

---

## 7. Written ambiguity is findable before the agent runs; unwritten ambiguity is not

Experiment 05, one dbt-shaped warehouse with models and a metrics layer over them, 36 questions,
3 repetitions, 108 graded answers per arm per model. The agent holds both `query_metric` and raw
SQL, so it uses a governed metric where one exists and writes SQL where none does.

**The static scan predicts where the agent fails.** 11 findings before the repair, 0 after. Where
the metrics layer governs the concept, wrong-metric selection falls **24% → 0.00** (`gpt-5-mini`)
and **11% → 0.00** (`gpt-5.6-terra`), 93 answers each. Overall correctness 62% → 91% and 80% → 94%.

**Severity is a useful prior, not a verdict.** The worst cluster and the quietest were both ranked
HIGH (active-user aliases at 67% wrong grounding; value moments at 8%), with the LOW name collision
between them at 28%.

**Scale does not substitute for governed definitions.** The larger model made zero construction
errors on the sprawled warehouse and still grounded on a decoy metric one time in nine, and it was
*worse* than the small model on the active-user cluster.

**The boundary is what nobody wrote down.** Two undocumented staff flags covering different accounts
and a `status` column stale for ~8% of ended terms produced no findings, because no definition
disagrees with another — there is nothing to compare. On the five questions the layer does not
govern, wrong grounding was 69% before and 33% after: the repair helped and did not finish.

**A residue nothing predicted: coverage gaps invite improvisation.** Asked for a count of
subscription contracts, the agent never wrote SQL. It substituted the nearest governed metric every
time (`subscribers` before, `paying_users` after) across six runs and two models. No definition was
wrong; the layer governs no contract count. Cleaning existing definitions cannot remove this class.

**The detector was wrong three times, and each was found by a trace rather than by review.** An
acronym defeats name matching (fixed in preflight 0.2.0); a table beside its own `_v2` was invisible
though the name is the whole signal (0.3.0); and the same count over one process at two grains was
unreachable, because the dangerous pair scores *lower* on name similarity than a pair that must
never be flagged, so the rule had to be structural and ignore names entirely (0.4.0).

## 8. Irreducible ambiguity: no prompt, no name and no layout fixes it; a gate does

Experiment 06, **preliminary** — one question on one fixture, so these are mechanisms and
directions, not rates. A dbt project over the same generated warehouse, with two governed
definitions that both answer *"how many active users did we have last week?"*: 886 excluding
internal and test accounts (owned by Product), 919 including them (owned by Platform). Each has a
downstream consumer that breaks if it is deleted, so unlike every finding in §7 this one **cannot be
repaired offline** — which is the whole reason the experiment exists. The pair disagrees on 11 of 12
slices, between 0.00% and 5.17%, and by 3.72% over the week. preflight 0.4.0 names the same pair,
HIGH, independently of the hand labels: 1 of 1.

**Everything advisory failed. 217 attempts, 16 clarifications, 201 silent errors.** Tried and null:
no clarify tool; a prose clarify tool; a typed one carrying a coded reason and named candidates; the
rule stated in the prompt; renaming so neither metric matches the question; reordering the
catalogue; a compact catalogue putting the two descriptions on adjacent lines instead of five apart;
and `transparency`, which puts the compiled SQL on every result. The transparency null is the
strongest: the result the agent read contained `WHERE activity__is_internal = false` verbatim — the
discriminator in the output it had just received, not in a list it skimmed — and it served the
number without comment, 0 of 20 across two models.

**The name selects the metric; the description is not consulted.** Four presentations of the same
two definitions, identical in measure, filter, value, owner and consumer, differing only in labels
and order. Three served 886; the fourth, which moved the word "active" onto the other definition,
served **919** — a count including staff and test logins, from a metric whose own description says it
is about load rather than customers. 16 of 16, two models.

**It knows and does not show.** Asked to *compare* the two definitions rather than to answer, the
same model on the same layer clarifies, names both candidates and states the discriminator exactly.
The knowledge is available; the answering path does not use it. This reproduces *Knowing but Not
Showing* (arXiv 2605.25284) within-subject on a governed layer.

**Scale does not buy it, and good naming makes it worse.** Only `gpt-5.6-sol` ever clarified
unprompted, and only where the question's wording matched no metric name: **10/10** on that layer,
**1/10** where a name partly matched, **0/10** where one matched exactly. On the same no-match layer
`gpt-5.6-terra` scored 0/10 and `gpt-5-mini` 0/10. An interaction, not a main effect — so the
behaviour depends on which model is running and which words the user typed. Naming a metric exactly
what users call the concept, which every governance guide prescribes, is what suppresses the
question.

**The enforced gate works: 15 of 15, silent error 1.00 → 0.00.** `ambiguity_check` at
`Position.BEFORE` looks every governed call up in an index built by `preflight index` beside the
layer, and refuses a call whose metric is contested. The block **carries the decision brief** rather
than pointing at it — both names, both numbers, and the differing predicate — because the naming
result above says an agent that does not read descriptions when answering will not go and look one up. The
reason code corrects itself as a side effect: both voluntary clarifications filed
`underspecified_request`, every gated one files `competing_definitions`. This is §7's advisory /
enforced split again, and the R3-over-R6 result from the reliability ladder.

**The gate fires on sensitivity, not membership**, and that distinction is what makes it shippable.
It executes each competitor with the same arguments and stays silent when they agree — `platform =
unknown` returns the same number under both readings and is allowed through, while the same metric
over the whole week is blocked at 3.72%. Membership alone would have fired on **40.3%** of the
frozen suite's metric-declaring answers (1,566 answers, 631 in the contested cluster), most of them
diagnostics. The divergence threshold is **zero** and the zero is argued: danger runs inverse to
magnitude, so "does not matter" means identical rather than close.

**The gate's cost, now measured: it interrupts 10 of 12 questions that had already said which
reading they wanted.** The suite grew to 16 questions over four piles — clean metrics, contested
metrics asked with the scope stated, unanswerable, and contested. Coverage on the answerable piles
falls from 0.96 to 0.58 under the gate. The gate reads the SELECTION and never the question, by
design, so a question that disambiguates itself in words is indistinguishable from one that does not.

**An escape hatch the agent never used.** Given `resolved_scope` — retry the blocked call declaring
the discriminator the block named, and the gate stands down — the agent used it **0 of 12** times.
Blocked, told what separates the definitions, holding a question that had already answered that, it
clarified every time. Any mechanism whose last step is the model choosing to use it is worth what
the model's choices are worth, which §7 and the transparency null above both price at approximately
nothing.

**Attaching the rival number is advisory and behaves like one; checking that it was used is what
closes the gap.** Appending the competing definition's figure to the governed result costs no
coverage and interrupts nobody, and the agent names both figures **6 of 12** times. Handing back the
one-reading answer once, with both figures, takes it to **11 of 12** at coverage 1.00. The content
of the two arms is identical; the only difference is whether anything checks. Across five arms on 48
runs each, that one is best by eight questions:

| arm | mechanism | contested ok | stated-scope questions interrupted | silent wrong | coverage | total |
|---|---|---|---|---|---|---|
| A | nothing | 0/12 | 0/12 | 16/48 | 0.96 | 28/48 |
| B | gate blocks the call | 12/12 | 10/12 | 3/48 | 0.58 | 33/48 |
| C | gate + declared scope | 12/12 | 12/12 | 2/48 | 0.50 | 31/48 |
| D | rival figure attached | 6/12 | 0/12 | 9/48 | 1.00 | 36/48 |
| E | attached and checked | 11/12 | 0/12 | 3/48 | 1.00 | **44/48** |

**B and E are not ranked by this table.** E answers more and interrupts nobody; B never serves a
contested number at all. Which is right depends on the price of an answer carrying one reading
silently against the price of a round trip, and that price is still the placeholder `WRONG_COST`.

**The divergence does not survive a calculation intact, so a derived question can rest on a
contested metric and still have one correct answer.** The two definitions differ by 3.72% at the
input; that becomes 3.59% for a per-user rate, 3.82% for a subtraction, and **0.00%** for a
week-over-week change, because the internal accounts are a stable population. Any mechanism that
fires on "an input is contested" fires on the last case. The current check verifies that the rival
INPUT was named rather than the rival ANSWER, which both over-fires (demanding a divisor the reader
has no use for) and under-fires (an answer naming the rival count in passing, while giving only one
rate, passes). The fix is to have the answer carry its arithmetic so the harness can substitute the
rival operand and recompute.

**The market's runtime answer to ambiguity is the one measured here as ineffective.** Snowflake
Cortex Analyst, Power BI Copilot and Databricks Genie all detect and clarify by prompt instruction;
Cortex Analyst's documented example for that instruction is literally "active users". The
enumerate-execute-compare rule this experiment arrived at appears in research (AmbiSQL, arXiv
2508.15276, which resolves automatically when interpretations converge and asks when they diverge)
but not in a shipping product. Enforcing that the served answer discloses the divergence was not
found anywhere, and neither was any treatment of two owned definitions that must both survive — the
published advice is to certify one, which is exactly what this case rules out.

**The action-only 3×3 matrix flatters the system, and the defect is in a diagonal cell.** "The
question had one answer and the agent answered" holds both the best available outcome and one of the
worst. Split three ways — right, wrong number, no figure — the same runs that read 8/12 and 10/12
read 6/12 and 9/12. The grid needs one off-diagonal cell marked correct for the same reason: a
contested question answered with every reading and the discriminator has not made a silent choice.

→ [`harness/experiments/06_third_state/findings.md`](../harness/experiments/06_third_state/findings.md)

## 9. Errata and self-inflicted findings

**Three artifacts caught in my own analysis on one day**, all the same shape, all nearly reported
as findings:

1. "0 orphans in the rendered arm" — the field did not exist in rows written before that day.
   Absent, not zero.
2. "66 published answers would now be refused, 24 previously correct" — did not reproduce. A
   hand-written approximation of the provenance rule said **326**; the real `account_for` says
   **5** before a fix and **14** after, of which 1 and 3 were graded correct. Wrong by 65×.
3. "7 deletions in the repair loop" — a 25-character prefix match scoring a reword as a deletion.

**The rule that follows: never re-implement a check in order to audit it. Call the real one.**

**Live corrections.** Dropping the whole-number rounding rung (`e9a8024`) moves three answers
graded correct — `t5_which_lever`, `t4_retention_trend`, `t5_not_breadth` — to unaccounted. A
declared `0` had matched any rate below 50%.

---

## 10. Open, ranked by what it would take

| # | open question | cost | why it matters |
|---|---|---|---|
| 1 | **the over-clarification cost of the ambiguity gate** | a pile of answerable questions on the 06 fixture | the gate is 15/15 on questions it should stop, and nothing yet says what it costs on questions it should not. Membership would have cost 40.3%; sensitivity is unmeasured, and it is the number that decides whether §8 ships |
| 2 | **separate `rendered` from `role` framing** | 342 attempts | the only known lever on the 70% flat-list problem, currently confounded |
| 3 | the judge's prose accuracy | needs more diagnostic questions, not a better panel | 24 decisions across every run ever stored; unmeasurable, and it kills 15 of terra's 28 over-refusals |
| 4 | `t2_paid_search_spend_q2` | design work | 38% wrong, diagnosed, no deterministic detector exists |
| 5 | does any of this matter on a strong model | ~500 attempts at a fair reasoning budget | repair has never fired there, but that is 0/15 |
| 6 | split identity from arithmetic in `num_match` | small change, wide blast radius | rule (a) asks "is this a governed result", rule (b) "is this a comparison of two"; only (b) accumulates float error, and they share one predicate. Cost a correct answer 5/5 in one cell |
| 7 | rename `value_moments` / `weekly_value_moments` | layer change + regrade | the 28% mislabel rate, and the largest single defect we have not touched |

---

## 11. What is publishable today

**Yes, with the numbers we have:** the evidence-graph mechanism and the deterministic-verification
advantage; repair moves traceability 88% → 94% and nothing else; the `n/a` argument (an
uncited agent produces nothing to audit, not weak audit material); the two-failure-shapes model
result; the decline-rate argument; and the three-times-wrong story from §5, which teaches the
governance point without preaching it.

From §8, and the split matters because the two halves have very different evidence behind them.
**Publishable:** the advisory nulls, every one with its n — a typed clarify tool, the rule in the
prompt, four namings, two catalogue layouts and the compiled SQL all moved nothing across 217
attempts; that the served number follows the label rather than the definition, 16 of 16 on a
controlled swap; and the knowing-versus-showing gap, which reproduces published work on our own
fixture rather than restating it.

**Not yet:** anything claiming the graph captures reasoning (§2); a model ranking (§6); the exact
repair rate (§3); the judge's reliability (§9.2); orphans as any kind of signal (§4); and the
ambiguity gate as a RATE (§8) — 15 of 15 on one question is a demonstration that the mechanism
works, and until the over-clarification cost is measured it says nothing about what it would cost to
run.

**The honest headline available now:** *"we kept trying to fix the AI, and the fixes that held were
the ones that made the data say more about itself."*
