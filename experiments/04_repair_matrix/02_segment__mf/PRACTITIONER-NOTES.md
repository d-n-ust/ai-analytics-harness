# The same defect, on dbt MetricFlow — and the fix your stack already supports

Written for analytics engineers running dbt MetricFlow, Cube, LookML or any other metric layer, and
for anyone who has been told the answer is "build a semantic layer".

**The short answer: the defect reproduces on a production semantic layer, and the cheap fix works
there. You do not need a construct your tool may not have.**

**The sample is small.** Four questions, three repetitions, one model. Two of the four are controls.
Section 5 states the limits.

---

## 1. Why this test was run separately

We first found this defect on our own metric layer. The obvious objection is that we had measured
our own file format.

So we rebuilt the same test on **dbt MetricFlow**: its YAML, its query engine, its idioms. Same
data, same questions, same agent.

---

## 2. The defect reproduces exactly

Two metrics over the same table, at the same grain, with the same aggregation:

```yaml
- name: value_moments          # every account
- name: real_value_moments     # excludes staff and test accounts
```

With no description saying which is which, the agent asked *"how many habits did our customers
complete last week?"* answered **3,785**. The correct figure is **3,642**.

It did not hesitate, did not ask, and did not flag anything. Three repetitions, the same wrong
number every time.

| version | correct |
|---|---|
| no description says who each metric counts | 6/12 |
| **descriptions say it** | **12/12** |
| one metric, population as a where-constraint | 12/12 |

---

## 3. The important part: MetricFlow cannot do the "proper" fix

In our own layer the repair is a **named segment**:

```
query_metric(metric="value_moments", segment="real_users")
```

`real_users` is declared once, carries a description, and the metric offers it as a choice. Cube
does the same thing under the same name.

**MetricFlow has no such construct.** A population is an expression over a dimension:

```
mf query --metrics value_moments --where "{{ Dimension('user__is_internal') }} = false"
```

There is no `real_users` anywhere. Only `is_internal = false`, and something has to tell the agent
that this is what "customers" means.

| tool | how a population is expressed | can a machine read its name? |
|---|---|---|
| Cube | `segments:` — named, described, reusable | yes |
| ours | governed segment — the same idea | yes |
| MetricFlow | a where-constraint over a dimension | no — only the predicate survives |
| DAX | inside a measure expression | no |

**If the formal construct were the mechanism, MetricFlow users could not repair this defect.** They
can. Writing the population into the descriptions took the score from 6/12 to 12/12, which is
everything the declared version achieved.

---

## 4. What to do

**Write who each metric counts into its description.** One sentence per metric. This is the whole
intervention that worked, and it works in every tool listed above.

**Use the words the business uses.** Our two failing questions differed only in wording. "Excluding
staff and test accounts" matched the description and was answered correctly. "Our customers" matched
nothing, and produced the wrong number. If your leadership says "customers", the word "customers"
has to appear somewhere the agent reads.

**Describe your dimensions as selectors, not just as columns.** In MetricFlow we had to write
*"filter on this to choose the population"* into the `is_internal` dimension's description, because
nothing structural marks a dimension as the thing that picks a population. Your agent has no way to
know which of forty dimensions is the one that matters.

**Do not wait for a modelling project.** The expensive repair and the cheap repair scored the same
here.

---

## 5. What this result cannot support

**A rate.** Four questions, of which two are controls that every version answers. One question does
the real work.

**That descriptions are always enough.** They were enough for this defect, at this size, on this
model. Other primitives behave differently — a semi-additive measure was not repaired by a
description or by a declared field, and needed a runtime check.

**That MetricFlow is worse.** It reached the right numbers in every arm that was told the fact. What
it cannot do is give the population a name a machine can read back, which matters for governance and
reuse rather than for this test.

---

## Summary

1. Two metrics differing only in which users they count is a real defect on a production semantic
   layer, not an artefact of a home-grown format.
2. The wrong population produces a plausible number with no warning. Nothing downstream catches it.
3. A description fixed it completely — 6/12 to 12/12.
4. Use the business's vocabulary in that description. Matching words is what actually happened.
5. A named segment is better modelling, but it was not what bought the accuracy here, and your tool
   may not offer one.
