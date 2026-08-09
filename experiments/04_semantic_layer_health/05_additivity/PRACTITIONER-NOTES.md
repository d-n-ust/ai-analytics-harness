# Documenting a semi-additive measure does not stop an agent adding it up

Written for data engineers, analytics engineers and data leaders deciding where to spend effort on
making a warehouse work with AI agents.

**The short answer: for measures that cannot be added across periods, writing the rule down did not
help and declaring it in a field did not help. What helped was a runtime check that knows nothing
about the rule.**

**The sample is small.** Five questions, three repetitions, one model, and only one question
actually triggers the defect. Section 5 states the limits.

---

## 1. The defect

Your active users metric is a distinct count:

```sql
count(distinct user_id)
```

over a table where **one row is one user-day**.

A user active on Monday and Tuesday is **one** weekly active user and **two** daily rows. So the
seven daily numbers do not add up to the weekly number, and nothing about the metric says so.

We asked: *"break our weekly active users down by day for last week, and tell me the total for the
week."*

| | |
|---|---|
| correct answer | **886** |
| what the agent reported | **2,012** |
| overstatement | **2.27×** |

**No SQL was invented.** The agent made two entirely governed calls — a daily breakdown and then a
sum — and every individual number it received was correct. The error is in the addition, and the
addition is the thing the metric layer never talks about.

---

## 2. What we tested

Three versions of the same layer:

| version | what it does |
|---|---|
| **implicit** | nothing says whether periods may be added |
| **documented** | the descriptions say it: *"NOT additive over time — summing periods double-counts"* |
| **declared** | `additive_over_time: false`, a field on **every** metric, including the ones where summing is fine |

The declared version is the one that should win. Additivity is a property of the measure, true
everywhere, in a fixed slot the agent reads rather than a caveat it has to remember.

---

## 3. What we found

| version | answers on the trap, three attempts |
|---|---|
| implicit | refused once, then **2,012** twice |
| documented | **1,627**, **2,012**, **1,627** |
| declared | **2,012**, **2,012**, **2,012** |

Nought out of three everywhere.

**The declared version was the most consistently wrong.** We verified that the additivity warning
was actually present in the text the agent read — this is not a case of the field failing to render.
The agent read *"summing periods double-counts"* and then summed the periods.

The documented version produced a third wrong answer, 1,627, which is neither the correct figure nor
the naive sum. Being told the rule in prose made it inventive rather than correct.

---

## 4. What did work

We re-ran the identical test with one guardrail added: **every number in an answer must trace to a
single governed result.**

| | trap result |
|---|---|
| without the check | a confident wrong number |
| with the check | a refusal, every time, in every version |

A figure obtained by adding seven daily rows traces to no single governed result, so it is refused.

**The check has never heard of additivity.** It does not read the `additive_over_time` field and
would behave the same if that field did not exist. It asks one question — *where did this number
come from?* — and a number assembled by arithmetic outside the metric layer cannot answer it.

**Be precise about what this buys.** No version, at either setting, ever answered 886. The check
does not produce the right answer. It converts a wrong number that would have reached a slide into a
question that comes back to a person. That is the whole benefit, and it is a large one.

---

## 5. What to do

**Add a provenance requirement before you add an additivity field.** It is a runtime check rather
than a modelling project, it cost us nothing in correct answers, and it caught the one thing two
modelling interventions missed.

**Check that your legal roll-ups still work.** This is the failure mode of any such rule. We kept
two questions where adding periods is genuinely correct — completed habits by day, marketing spend
by month — and both continued to be answered correctly at every setting. A system that has learned
"never add" is worse than the one you started with.

**Do not stop documenting additivity.** It costs an afternoon, it is correct, and a human reading
your catalogue benefits from it. Our result is that it does not, on its own, stop this error.

**Know which of your measures this affects.** Distinct counts, ratios, rates, running balances,
inventory levels, anything semi-additive. Your layer probably already knows: ours could derive the
answer correctly for every metric from the aggregation alone. The fact was computed, correct, and
never put in front of the agent.

---

## 6. What this result cannot support

**A rate.** One question triggered the defect. We can say the fact being present changed nothing in
nine attempts across three treatments; we cannot say how often this happens to you.

**That declaring is useless in general.** It failed here, on one primitive. For a different
primitive — which population a metric counts — declaring the fact was the best version we tested.

**A second trap we expected to fire did not.** We asked the same question shape about a ratio, which
cannot be added in any direction. Every version answered it correctly without being told. So the
defect is narrower than "agents add things they should not" — it hit the distinct count and not the
ratio.

---

## Summary

1. Distinct counts, ratios and rates do not add across periods, and an agent will add them.
2. The wrong number is 2.27× the right one and is produced entirely from correct governed calls.
3. Writing the rule into the description did not stop it. Declaring it in a field did not stop it.
4. Requiring every number to trace to one governed result did stop it — by refusing, not by being
   right.
5. Test your legal roll-ups when you add that check.
