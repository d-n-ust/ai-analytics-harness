# Do not rewrite your metric catalogue as JSON

Written for data engineers, analytics engineers and the people deciding where to spend effort on
making a warehouse work with AI agents.

**The short answer: how you format the list of metrics you give an agent does not appear to matter.
Spend the effort on what the list says instead.**

**The sample is small.** Five questions, three repetitions, one model. This result is a null, and a
null at this size means "we could not detect a difference", not "there is no difference". Section 4
states the limits.

---

## 1. What we tested

An AI analyst starts by reading a list of the metrics it can use. We gave it the same fifteen
metrics written three ways, and changed nothing else:

**As prose**, which is what most tools produce:

```
- value_moments: Number of value moments (completed habits) in the period.
    also called: completed habits, habit completions, activity
    group_by: region, platform, channel, country
    period: supported
```

**As JSON**, with field names matching the arguments the agent uses when it calls a tool:

```json
{ "name": "value_moments",
  "description": "Number of value moments (completed habits) in the period.",
  "also called": ["completed habits", "habit completions", "activity"],
  "group_by": ["region", "platform", "channel", "country"],
  "period": "supported" }
```

**As a markdown table**, one row per metric.

The facts are identical in all three. Only the arrangement differs.

---

## 2. What we found

No difference we could measure. All three formats scored within one point of each other, on a test
where run-to-run variation was wider than that gap.

The one measurable difference is cost:

| format | tokens | relative |
|---|---|---|
| markdown table | 1,028 | 1.00 |
| prose | 1,204 | 1.17 |
| JSON | 2,209 | **2.15** |

**JSON costs about twice as much as a table to convey the same information.** If you send a metric
catalogue on every request, that is a real bill for no measured benefit.

---

## 3. What did matter, and it was not the format

Making the three formats genuinely identical was harder than expected, and the difficulties are more
useful than the result.

**Small wording differences changed the answers.** Our first version had four accidental differences
between the three formats. In one, only the JSON version mentioned a `segment` option, at the top of
the list. That version then applied a segment nobody had asked for and answered **227** where the
correct answer was **283**. The formats scored 5, 4 and 1 out of 5, and none of it was about format.

**Two real defects in the catalogue surfaced during the work.** Both are worth checking for in your
own setup:

- The catalogue advertised fewer filters than the query engine actually accepted, so the agent never
  learned about a filter it was allowed to use.
- A refactor removed the list of valid time buckets (`day`, `week`, `month`) from the catalogue while
  the query tool continued to accept them.

**The check that catches this class of problem:** assert that the catalogue documents exactly the
argument space your query tool accepts. If the tool takes a `time_grain` argument, the catalogue must
list its valid values. If a metric accepts a filter, the catalogue must say so. These drift apart
silently, and the agent has no way to notice.

---

## 4. What this result cannot support

**Whether format matters for a weaker model.** Published work shows that sensitivity to prompt format
varies enormously between models and decreases as models improve. We tested one model. A smaller or
older model may well be more format-sensitive.

**Whether it matters for longer catalogues.** Ours is about 1,200 to 2,200 tokens. Effects related to
context length and position are documented at much larger sizes, and none of them apply here.

**Whether it matters for harder questions.** Ours were counts and lookups.

---

## Summary

1. Do not spend effort rewriting a metric catalogue from prose into JSON.
2. If you do use JSON, know that it costs roughly twice the tokens of a table for the same content.
3. Do spend the effort making sure the catalogue states everything the query tool accepts, and check
   it automatically. That is where we found real defects.
