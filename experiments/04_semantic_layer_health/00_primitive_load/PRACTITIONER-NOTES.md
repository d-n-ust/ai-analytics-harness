# Model the meaning into the tables, and be careful what you write down

Written for data engineers, analytics engineers and data leaders deciding where to spend effort on
making a warehouse work with AI agents.

**The short answer: put the meaning in the model. A clean model with no documentation beat a messy
model with good documentation, and it beat a semantic layer. And documentation of a filter helps on
the questions that need it and hurts about as much on the questions that do not.**

**The sample is small.** 23 questions, one model, and 16% of cells disagree with themselves across
identical repeats. Section 6 states the limits.

---

## 1. What we tested

Six versions of the same warehouse, over the same data, answering the same 23 questions. Every
version returns the same numbers when asked directly — only what the agent reads changes.

| version | what it is |
|---|---|
| raw tables | the application database as it comes: coded columns, abbreviations |
| raw + documentation | the same tables, every fact stated in a comment |
| **clean model** | a conformed star: sane names, resolved codes, one clean grain |
| clean model + documentation | the same star, commented |
| + semantic layer | a governed metric layer on dbt MetricFlow |
| + a runtime check | the layer, plus a rule that every number must trace to one governed result |

The questions run from **easy** — one fact to resolve — to **hard**, where a single question needs
four resolved at once: which rows are the thing, which people count, people rather than rows, and a
join that must not multiply.

---

## 2. The result

| version | score |
|---|---|
| **clean model, no documentation** | **66 / 69** |
| clean model + documentation | 65 / 69 |
| + a runtime check | 64 / 69 |
| + semantic layer | 62 / 69 |
| raw tables + documentation | 60 / 69 |
| raw tables | 52 / 69 |

**The clean model with no comments at all beat everything, including the documented version of
itself and the semantic layer on top.** It scored 66 in both runs after the change described next,
and the ordering held in both.

---

## 3. What made the difference, and it is one old rule

The star originally stored country as `DE`. Three questions asked about *Germany*, and three
versions answered **0** — they filtered `country = 'Germany'` against a column of ISO codes.

We first tried documenting it: *"DE is Germany, FR France…"* in a table comment. That helped the
versions that read comments and did nothing for the one that does not.

Then we did what Kimball says: **store the code and its decode as separate columns.**

```sql
country       'DE'
country_name  'Germany'
```

The clean model went from 62 to 66. **A comment can be ignored; a column cannot.**

The same rule applies to flags. `is_internal = true` is a boolean the reader has to interpret;
`user_type = 'staff'` states what a person is. Both now sit in the model.

**The practical version:** every code in a dimension should have its label beside it, and every flag
should have a decoded value. If you do one thing from this note, do that.

---

## 4. Documentation cuts both ways, and the size is the surprise

Eleven of our questions ask to exclude staff and test accounts. Twelve do not. Splitting on that, on
the hardest questions:

| | documentation is worth |
|---|---|
| the question **needs** the documented fact | **+22 to +44 points** |
| the question does **not** | **−50 points** |

The negative half came out at exactly −50 in three separate runs.

**Why.** Once you document that a column marks staff and test accounts, the agent starts excluding
them — on questions that never asked. It reads a description of a population as an instruction to
apply it.

We tried to fix this by rewording. The first comment said *"An account is staff or test when…"*,
which reads as a rule; we rewrote it to describe the values instead. **It made no difference.**
Naming a filterable population in documentation at all was enough.

What did work was removing the ability to apply it casually: in the semantic layer we deleted the
flag from the list of things you can filter by, and offered the population only as something you
name. **Inside the layer the over-application stopped. Outside it — where the same column still sits
on the table — it continued exactly as before.**

**The practical version:** documenting a filter is not free. If your agent can reach a column that
marks a population, expect it to use that column whether or not the question asked. The remedy is to
remove the affordance, not to reword the comment — and a remedy inside a semantic layer only helps
if the agent stays inside the layer.

---

## 5. Two findings about semantic layers

**A layer that cannot express the question is worse than no layer.** Our first one bound each metric
to a single table with no join model, so no metric about habits could be filtered by any attribute
of a person. Every segment question was unreachable. The agent abandoned it and wrote SQL — and when
it *did* use the layer it was right 31% of the time against 70% when it ignored it, because one
metric had a filter hidden in its name.

Rebuilt on dbt MetricFlow with declared entities, every question became answerable through the layer
and the arm went from roughly 15 to 22 out of 23.

**A layer alone does not get used. A provenance rule does.** Given a governed layer, the agent
skipped the catalogue on 38 to 47 of 69 answers and wrote SQL instead. Add one rule — *every number
must trace to a single governed result* — and it read the catalogue on **every** answer, three runs
running.

**But it does not remove error; it changes which error.** With the check, every remaining failure was
a filter the question asked for and the agent left out. Without it, the failures were filters nobody
asked for, added in SQL. Two versions, two points apart, failing in opposite directions.

**The practical version:** if you have built a semantic layer, measure how often the agent actually
calls it. Nothing in a normal accuracy report shows you this, and a layer that is bypassed is not
governing anything.

---

## 6. What this cannot support

**A rate.** 23 questions, one model, 16% of cells unstable. The findings that repeat across runs are
the clean-model score and the −50; everything else moved between runs.

**Your model tier.** One model, `gpt-5-mini`. A separate sweep found a frontier model needing far
less documentation on easier questions, so the numbers here are not portable upward.

**More than one filter.** Every over-application we measured is one staff flag. Whether a documented
*grain* rule or a documented *join* rule behaves the same way is untested.

**One failure we could not fix by modelling at all.** On the hardest questions the agent drops the
filter belonging to the thing it is counting while keeping the one that arrives from a joined table.
We grouped the catalogue by table, labelled which table the metric counts, and removed competing
options. It persisted. That looks like a property of the agent when a question has several parts,
not something a better model fixes.

---

## Summary

1. Put the decode in the table. Every code needs its label beside it; every flag needs a decoded
   value. This was worth more than anything else we tried.
2. A clean model with no documentation beat a messy model with good documentation.
3. Documenting a population helps on questions that need it and costs about the same on questions
   that do not. Expect the agent to apply what you document.
4. Rewording documentation does not stop over-application. Removing the ability to apply it does.
5. If you have a semantic layer, check whether the agent uses it. Requiring every number to trace to
   a governed result is what made ours get used.
6. That requirement trades over-application for under-application. It does not remove error.
