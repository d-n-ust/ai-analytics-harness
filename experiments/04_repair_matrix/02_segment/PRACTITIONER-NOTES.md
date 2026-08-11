# Your metric names decide which users get counted, and the agent cannot read them

Written for data engineers, analytics engineers and data leaders deciding where to spend effort on
making a warehouse work with AI agents.

**The short answer: if two metrics differ only in which users they count, say so in words the
business actually uses. The metric name will not carry it, and neither will a description written
in your vocabulary instead of theirs.**

**The sample is small.** Eight questions, three repetitions, one model. Two of the eight questions
produce the whole result. Section 5 states the limits.

---

## 1. The defect

Most metric layers contain a pair like this:

```
value_moments         completed habits
real_value_moments    completed habits, excluding staff and test accounts
```

Same source table. Same aggregation. Same time grain. The only difference is **which rows are
counted**, and that difference lives in the word "real".

A person reads "real" and asks what it excludes. An agent reads "real" and picks one.

This is one measure and two populations shipped as two metrics. The choice that should be an
argument — *which population?* — has become a choice between two names.

---

## 2. What we tested

Three versions of the same layer, over the same data, answering the same eight questions:

| version | what it does |
|---|---|
| **implicit** | no description says who any metric counts |
| **documented** | each description says it: *"excludes internal/test accounts"* |
| **declared** | one metric, and the population becomes an argument: `value_moments(segment=real_users)` |

Every version returns the same numbers when asked directly. Only what the agent reads changes.

---

## 3. What we found

Two questions separated the versions. The other six were answered correctly by everything.

| the question | implicit | documented | declared |
|---|---|---|---|
| "how many habits did our **customers** complete last week?" | wrong | **wrong** | correct |
| "**excluding staff and test accounts**, how many in June?" | wrong | correct | correct |

**The difference between the two questions is the vocabulary, not the difficulty.**

The June question names the exclusion in the same words the description uses. The agent matches
them and applies the filter. The week question says "customers" — a word that appears in no
description — and the agent has nothing to match. It returned **3,785** where the correct figure is
**3,642**: the all-accounts number, served as the customer number, with no warning of any kind.

The declared version answered both, because its segment lists `customers` as a synonym.

**So the mechanism is lexical, not structural.** What repaired the week question was not that the
population became an argument. It was that somebody wrote down that "customers" means real users.

---

## 4. What to do about it

**Write the population into the description, in the words your business uses.** Not the words your
data model uses. If your executives say "customers" and your column says `is_internal`, the
description has to contain both. This is an afternoon of work and it fixed one of our two
questions outright.

**List the synonyms.** Whatever your semantic layer calls them — synonyms, aliases, labels. This is
what fixed the second question. It is cheaper than a modelling project and it was the whole
difference between our documented and declared versions.

**Then consider collapsing the twin metrics.** `value_moments(segment=real_users)` is better
modelling than `real_value_moments` for reasons that have nothing to do with this experiment: one
definition to maintain, one place to change the filter, and the population becomes visible in the
call rather than buried in a name. Our run cannot tell you it improves accuracy on its own, because
the version that collapsed the metrics also added the synonyms.

**The order matters.** Vocabulary first, structure second. The cheap step carried most of the
result.

---

## 5. What this result cannot support

**A rate.** Two questions decided everything. We cannot tell you what share of your questions this
affects.

**That declaring beats documenting.** The declared version won on exactly one question, and that
question's wording appears word for word in the declared version's synonym list. We wrote this
confound into the design deliberately and left it there rather than quietly removing it, because
removing it would have made the study look cleaner than the evidence is.

**That the aggregate version of this defect matters.** We also tested a metric with a threshold
buried inside its aggregation — `count(distinct case when moments >= 5 ...)`, where the rule
deciding who is counted is arithmetic nobody can read. All three versions answered all three of
those questions correctly. The defect is real; these questions did not detect it.

---

## Summary

1. Two metrics that differ only in which users they count are a defect, whatever your tool.
2. Write the population into the description, using the words the business uses, not the words your
   columns use.
3. Add synonyms. That is what separated our best version from our middle one.
4. Collapse the pair into one metric with a population argument — for maintainability. We cannot
   yet show it buys accuracy by itself.
5. A wrong population produces a plausible number, not an error. Nothing downstream will catch it.
