# One row is one *what* — and why our test of it failed twice

Written for data engineers and analytics engineers.

**The short answer: we could not make this defect bite, and how it failed to bite is the useful
part. A model that already knows what a subscription is does not need to be told.**

**This is a null.** Two runs, no version separated from another. Section 4 states what that does and
does not mean.

---

## 1. The defect

A subscriptions table holds **one row per subscription term**. Someone who cancels and later
resubscribes has two rows.

```
457   rows in the table
413   people
 43   people hold more than one term
```

Ask "how many customers have ever paid us" and count rows, and you overstate by 10.7%. That is
outside any sane tolerance and small enough to look like a real number on a slide.

## 2. What happened

**Every version got it right, including the one told nothing.** Nine attempts, nine times
`COUNT(DISTINCT user_id)` as the first query.

The reason is in the question. We asked *"how many **users** have ever had a subscription"* — and
"count users" translates directly into `count(distinct user_id)` without anyone needing to know what
a row stands for.

We rewrote it to ask for an average per subscriber, where the denominator is invisible in the
wording. That separated the versions — but for the wrong reason: five of nine wrong answers divided
by every signed-up account rather than by subscribers. **That is a disagreement about what
"subscriber" means, not about what a row is.**

## 3. What this is worth knowing

**A question only tests the grain if the right aggregation cannot be read off the noun.** "How many
users" tells the reader to count users. Most naturally-phrased business questions do the same, which
may be why this class of defect is less dangerous in practice than it looks on paper.

**The model already knows what a subscription is.** Churn-and-resubscribe is a familiar shape, and
it recovered the grain from the column names without help.

**It does not know what a user-day is.** In a companion test the same model was asked for weekly
active users, given a table where one row is one user-day, and answered **2,012** where the truth is
**886** — a 2.27× overstatement, from two entirely correct queries.

**The difference is the useful bit.** A subscription term is a business object with a name; a
user-day is a modelling decision somebody made and wrote nowhere. **The grain worth documenting is
the grain your business does not have a word for.**

## 4. What this cannot support

**That grain does not matter.** It matters — the companion result is a 2.27× error. What we failed
to show is that *this* grain, on *this* table, trips *this* model.

**A rate.** Three questions, one model.

**Anything about your warehouse.** If your fact tables have grains your business has no word for —
per user-day, per snapshot, per allocation, per bridge row — that is where to look, and it is not
where we looked.

---

## Summary

1. One row per subscription term, and a person can have several. Counting rows overstates people by
   about 11%.
2. Our model handled it unprompted every time. The question told it to count people.
3. Test a grain only with a question whose correct aggregation you cannot guess from the noun.
4. Document the grains your business has no word for. Those are the ones that bite.
