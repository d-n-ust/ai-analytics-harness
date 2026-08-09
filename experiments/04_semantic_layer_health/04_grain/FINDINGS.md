# Study 04 — the first grain item, and why it is being replaced

Run `20260809-163522-04_grain`: one question, five arms, three repetitions, `gpt-5-mini` at
`reasoning=minimal`, R1.

**The item is dead. Every arm answered correctly on every repetition, including the arm that was
told nothing.** The traces say why, and the reason is worth more than the run cost.

---

## 1. The result

| arm | correct | unstable cells |
|---|---|---|
| A_implicit | 3/3 | 0 |
| B_documented | 3/3 | 0 |
| C_modelled | 3/3 | 0 |
| D_declared | 3/3 | 0 |
| E_enforced | 3/3 | 0 |

All five fingerprints differ, so every treatment reached the model. The vocabulary audit came back
at two tokens. The instrument worked; the question did not.

---

## 2. What the traces show

**Nine of nine SQL attempts wrote `COUNT(DISTINCT user_id)` as the first query.** Not one arm ever
issued `count(*)` against the subscriptions table. The trap was never approached, let alone avoided.

`A_implicit`, which is told what the table holds and never what one row is:

```sql
SELECT COUNT(DISTINCT user_id) AS users_with_paid FROM fct_subscriptions;   -- 413
```

Three repetitions, the same query, produced immediately after `get_schema`.

**The question named the entity, and the aggregation followed from the noun.** *"How many **users**
have ever had a paid subscription"* tells the agent it is counting users. `count(distinct user_id)`
is then the obvious expression of "count users", and no knowledge of what a row stands for is
required to write it.

`B_documented` confirms this from the other side. Its rep 2 explanation quotes the treatment back:

> Counted distinct user_id in fct_subscriptions (**one row per subscription term**) to get number of
> unique users who have ever had a paid subscription.

It read the grain sentence. It then wrote the same SQL the arm without the sentence wrote. The
sentence was available, understood, and unnecessary.

**This was predicted in `study.yml` and is the reason the run was audited by hand:**

> An arm can reach 413 without understanding the grain, by writing `count(distinct user_id)` out of
> habit because the question says "how many users". That is a correct answer produced by a heuristic
> that would break the moment the question said "how many subscriptions".

The prediction was exact. A summary table alone would have shown five arms at 3/3 and invited the
conclusion that grain does not matter.

---

## 3. What the item got right, and should keep

**Pinning the population worked.** Two runs computed the real-users figure as well and then reported
the all-accounts one:

```
A_implicit rep1   413 (all)   393 (excluding internal)   -> answered 413
C_modelled rep0   413 (all)   393 (excluding internal)   -> answered 413
```

The phrase *"including our own internal and test accounts"* did its job: the segment primitive was
held constant and never contaminated the measurement. Keep it in the replacement.

**The arms are correctly constructed.** A and B differ in one sentence per view; A and C differ in
the table name alone; both were verified against `duckdb_columns()` before the run. `C_modelled`'s
agent read `fct_subscription_terms` and described it as "paid subscriptions table" — the name did
not mislead it, and it also did not need it.

---

## 4. The replacement, and why these two

The defect is that the question's noun dictates the aggregation. The repair is a question whose
correct aggregation is **not** derivable from the noun, plus a pair-mate that punishes the habit
this run exposed.

| candidate | correct | the easy wrong answer | gap |
|---|---|---|---|
| "what have we billed per subscriber, across our whole history?" | **$34.92** — `sum(billed)/count(distinct user_id)` | **$31.56** — `avg(billed_amount)`, which is per term | 10.7% |
| "how many subscriptions have we sold in total?" | **457** — `count(*)` | **413** — `count(distinct user_id)` | 10.7% |

**The first is the grain question.** "Per subscriber" does not say what the denominator is. An agent
that does not know rows are terms writes `avg(billed_amount)` — a correct average of the wrong
thing. The grain is the only fact that separates the two, and it is invisible in the wording.

**The second exists because of what this run found.** Every arm reached for `count(distinct
user_id)`. Here that habit is wrong, and the row count is the answer. An arm that scores on both
questions understands the grain; an arm that scores on one has a habit.

Both stay clear of the treatment's vocabulary: neither says "term", "row", "distinct" or "per
term".

---

## 5. One defect found by accident

`D_declared` rep 1 called the new metric with a segment and hit a real error:

```
query_metric(metric="ever_subscribed_users", segment="real_acquisition")
  -> Binder Error: Referenced column "channel" not found in FROM clause!
     Candidate bindings: "plan", "is_active"
```

`real_acquisition` filters on `channel`. The metric's base is `fct_subscriptions`, which has no such
column. **The layer offers a segment on a metric whose base cannot support it**, and the failure is
a database error surfaced to the agent rather than a check.

The agent recovered — it re-listed the metrics and answered correctly — so this cost nothing here.
It is a coverage defect in the layer and belongs in the matrix's coverage row, not this one.

---

## 6. What this run establishes

**Nothing about grain.** No arm was separated, so no cell of `../primitives_matrix.md` row 4 can be
filled from it.

**Something about method.** One question, five arms, three repetitions and a hand-read of fifteen
traces cost a fraction of a full study and killed an item that would otherwise have gone into a
25-question bank. Four of the five earlier studies in this experiment discovered their item problems
*after* a paid run and a write-up. `../FINDINGS.md` §6b has the count.

The rule this supports: **an item is not a grain item because it is about a table with an
interesting grain. It is a grain item only if the correct aggregation cannot be inferred from the
question's noun.**

---

## Provenance

| claim | source |
|---|---|
| per-arm results and fingerprints | `20260809-163522-04_grain/run.json` |
| nine of nine `COUNT(DISTINCT user_id)` | the `steps` field of every rung-2 row in that run |
| `B_documented` quoting the grain sentence | the same run, rep 2, `explanation` |
| the segment binder error | the same run, `D_declared`, rep 1, `steps` |
| replacement candidate values | `fct_subscriptions` over the current generated data |
