# What a warehouse needs before an AI agent can be trusted with it

Written for data engineers, analytics engineers and data leaders deciding where to spend effort on
making a warehouse work with AI agents.

**The short answer: data modelling fixes the questions that have answers, and stops helping quite
early. Three quite different warehouses scored identically on those. What separated them was the
questions that have no answer — and the fix there was not better modelling, it was writing down what
the data does not contain.**

**The sample is small.** 31 questions, one model, three repetitions each, and about one cell in five
disagrees with itself across identical repeats. Section 8 states the limits.

---

## 1. What we tested

Six versions of the same warehouse, over the same data, answering the same 31 questions. Every
version returns the same numbers when asked directly — only what the agent can read changes.

| version | what it is |
|---|---|
| raw tables | the application database as it comes: coded columns, abbreviations |
| raw + documentation | the same tables, every fact stated in a comment |
| clean model | a conformed star: sane names, resolved codes, one clean grain |
| clean model + documentation | the same star, commented |
| + semantic layer | a governed metric layer on dbt MetricFlow |
| **+ a runtime rule** | the layer, plus a rule that every number must trace to one governed result |

**The questions come in two piles.** 23 have answers, ranging from one fact to resolve up to four at
once. **8 have no answer**: a period outside the data, a term nobody defined, an ambiguous group, and
two questions whose premise is false.

A benchmark with only the first pile measures half the job, and the half that is easier to pass.

---

## 2. The result

| version | questions with answers (of 60) | questions without (of 24) | confident wrong answers |
|---|---|---|---|
| raw tables | 39 | 9 | 35 |
| raw + documentation | 55 | 7 | 17 |
| clean model | **57** | 11 | 11 |
| clean model + documentation | 56 | 11 | 12 |
| + semantic layer | **57** | 11 | 12 |
| **+ a runtime rule** | **57** | **20** | **3** |

Read the two middle columns against each other.

**Three very different warehouses tie at 57 of 60.** A clean star with no comments at all, that star
plus a full governed metric layer, and the layer plus a runtime rule — all the same. Once the model
is clean, this test cannot tell them apart on questions that have answers.

**On questions with no answer, five of the six sit between 7 and 11 out of 24.** Documentation does
not help; the best-documented version is the *worst* of the six here. A clean model does not help. A
semantic layer does not help. One version reaches 20, and section 5 is about what did it.

---

## 3. Easy questions cannot tell a good warehouse from a bad one

Correct answers out of 15, by how many things the question forces the agent to resolve:

| version | 1 fact | 2 facts | 3 facts | 4 facts |
|---|---|---|---|---|
| raw tables | **15** | 10 | 6 | 8 |
| raw + documentation | **15** | 15 | 13 | 12 |
| clean model | **15** | 15 | 15 | 12 |
| + semantic layer | **15** | 15 | 14 | 13 |

**Every version is perfect on the one-fact questions**, including the raw application database with
no documentation whatsoever. All of the difference appears from the second fact onward.

**The practical version:** if you are evaluating whether your warehouse is ready for an agent, the
test has to ask questions that need three or four things resolved at once — which rows count as the
thing, which people to include, people rather than rows, and a join that must not multiply. A test
built from single-fact questions will report that everything is fine. Ours did, for months.

---

## 4. Put the decode in the table

The highest-value modelling change we made, and it is an old rule.

The star stored country as `DE`. Three questions asked about *Germany*, and three versions answered
**0** — they filtered `country = 'Germany'` against a column of ISO codes.

We first documented it: *"DE is Germany, FR France…"* in a table comment. That helped the versions
that read comments and did nothing for the one that does not. Then we did what Kimball says: **store
the code and its decode as separate columns.**

```sql
country       'DE'
country_name  'Germany'
```

The clean model went from 62 to 66. **A comment can be ignored; a column cannot.**

The same applies to flags. `is_internal = true` is a boolean somebody has to interpret;
`user_type = 'staff'` states what a person is. Both now sit in the model.

---

## 5. The thing that worked was not what we built it to be

The version that reached 20 of 24 got almost all of that gain from **two questions about a period
the data does not cover** — August 2026, when the data stops on 12 July. It had been answering them
anyway, three times out of three. Now it declines, three times out of three.

The fix was not clever. **Our semantic layer never recorded which dates it holds data for.** dbt
MetricFlow has no field for it. But every model names its time column, so the range is just that
column's earliest and latest value — a fact the warehouse already held and had nowhere to write down.

We compute it now, per model, which matters: our habits table runs to 24 July while subscriptions
stop on 12 July. A single number for the whole warehouse would be wrong for one of them.

**The part worth reading twice.** We also switched on a rule that *blocks* any query reaching outside
the data. **It never fired — zero times out of six.** The agent asked the coverage question itself,
was told the data ends in July, and stopped. It had not been ignoring its limits; the lookup that
would have told it was switched off, because a layer that cannot answer "do you hold this period"
must not be handed that question. It had no way to check, and no way to discover that.

**The practical version:** record the date range each fact table covers, per table, and make it
readable by whatever queries your warehouse. This is metadata, not modelling, and in our test it was
worth more than the semantic layer. Then check whether your agent can actually reach it — the most
useful answer to a question is often "we don't have that", and it can only give it if something can
tell it so.

---

## 6. A semantic layer that is not required is not used

We counted how often the agent reached its answer through the governed layer at all, rather than
reading the schema and writing its own SQL:

| version | went through the layer |
|---|---|
| semantic layer, no rule | 59 of 93 — **63%** |
| **layer + the runtime rule** | 93 of 93 — **100%** |

Every one of the 34 bypasses had the identical shape: read the raw schema, write SQL against the
star, ignore the layer. Not a mix of routes — one route, taken on more than a third of questions.

**The practical version:** if you have built a semantic layer, measure how often the agent actually
calls it. Nothing in an accuracy report shows you this, and a layer that is bypassed a third of the
time is not governing anything. The rule that fixed it is one sentence: every number in an answer
must trace to a single governed result.

That rule is also what took confident wrong answers from 11 to 3. It costs a little: the version with
it declines a few questions the version without it answers correctly.

---

## 7. Two things that surprised us, both worth knowing

**Documenting a filter costs about as much as it pays.** Eleven of our questions ask to exclude staff
and test accounts; twelve do not. On the hardest questions, documenting that a column marks staff was
worth **+22 to +44 points** where the question needed it and **−50 points** where it did not — the
same −50 in three separate runs. Once you write down that a column marks a population, the agent
starts excluding that population from questions that never asked.

Rewording did not fix it. What fixed it was removing the ability to apply it casually: inside the
semantic layer we took the flag off the filterable list and offered the population only as a named
thing. Inside the layer the over-application stopped; outside it, where the same column still sits on
the table, it continued unchanged.

**The sophisticated versions are worse at spotting a false premise.** Asked *"signups fell in June —
what drove the decline?"* when signups rose from 403 to 553:

| version | rejected the false premise |
|---|---|
| the four versions with no semantic layer | **24 of 24** |
| the two versions with one | 4 of 12 |

The semantic layer version produced a fully reasoned causal account, with citations, of a decline
that never happened — three times out of three. We do not know why. A plausible guess is that an
agent required to find a governed metric spends its attention on finding one, while an agent writing
SQL looks at the numbers first and notices they went up. Two questions cannot settle it, and it is
the finding here we would most want to test properly.

---

## 8. What this cannot support

**A rate.** 31 questions, one model, about one cell in five unstable across identical repeats. Treat
any single-question result as noise; only the totals and the patterns that repeat across runs.

**Your model tier.** One model, `gpt-5-mini`. A separate sweep found a frontier model needing far
less documentation on easier questions, so these numbers are not portable upward.

**More than one filter.** Every over-application we measured is one staff flag. Whether a documented
*grain* or *join* rule behaves the same way is untested.

**That the blocking rule helps.** It never fired. Its value is unmeasured; what we measured is the
value of the layer *stating* its coverage.

**One failure we could not fix by modelling at all.** On the hardest questions the agent drops the
filter belonging to the thing it is counting while keeping the one arriving from a joined table. We
grouped the catalogue by table, labelled which table each metric counts, and removed competing
options. It persisted.

---

## Summary

1. Test with questions that need three or four facts resolved at once. Single-fact questions score
   100% on every warehouse we tried, including the undocumented one.
2. Test with questions that have **no answer**. Half of an analyst's job is knowing when not to
   answer, and no amount of data modelling taught ours to do it.
3. Record what each table covers — its date range, per table. In this test that metadata was worth
   more than the semantic layer, and it is far cheaper.
4. Then check the agent can reach it. Ours was not ignoring its limits; it had no way to look them up.
5. Put the decode in the table. Every code needs its label beside it; every flag needs a decoded
   value. Worth more than anything else we modelled.
6. Expect the agent to apply whatever you document. Rewording does not stop it; removing the
   affordance does.
7. Measure how often your agent actually goes through the semantic layer. Ours skipped it on 37% of
   questions until a rule required otherwise.
8. Requiring every number to trace to a governed result took confident wrong answers from 11 to 3.
   It is the single most effective control we tested, and it costs a little accuracy.
9. Do not trust the *reason* an agent gives for declining, even when declining was right.
