# What this means for your warehouse

Written for the people who own the tables: data engineers, analytics engineers, and the leaders who
decide what "AI-ready" is worth spending on. The internal write-up is in `FINDINGS.md`. This
document describes what to change in a warehouse and how to check it.

**The sample is small.** Five questions, three repetitions, one model. Treat the results as a
mechanism to look for in your own warehouse rather than as a benchmark. Section 6 states what these
results cannot support.

---

## 1. The failure is a wrong number, not an error message

We gave an AI analyst a table called `evt` with 193,407 rows and a column called `etype`. The
meaning of the integer was not recorded anywhere.

| etype | what it is | rows |
|---|---|---|
| 1 | app opens | 111,056 |
| 2 | **completed habits** | 67,132 |
| 3 | reminders shown | 15,219 |

We asked how many reminders were shown in one week. The correct answer is 645. Across three
attempts the analyst answered 6,311, then 3,785, then 10,641. Those three numbers are the other two
event kinds and the total of all three.

It did not refuse, and it did not express any doubt. It wrote correct SQL against the table it was
given and returned a number that was ten times too large.

This is the risk to plan for. A failed query is visible to everyone. A wrong number is not.

---

## 2. Four defects we placed in the data, and how to find them in your own warehouse

All four are common. None of them indicates poor engineering. They are what warehouses look like
when they are built for people who already know the domain.

### Which raw layer this describes

The tables above model an **application database extract**: one table per business object, surrogate
keys, foreign keys by convention, and enum values stored inline as integers or short strings. This
is what a Fivetran or Airbyte load from Postgres or MySQL produces.

It is deliberately **not** a normalised warehouse. There are no lookup tables for event type,
channel, country or subscription status. That is the normal case rather than an artificial
difficulty: in most applications the meaning of an enum lives in application code, as a Django
choice, a Rails enum or a TypeScript union. The loader carries the integer across; the meaning stays
in a repository the data team may not read. Nothing in the warehouse can resolve it, which is
exactly when someone has to write it down.

**If your source has proper lookup tables, you have a different and easier problem.** An agent can
resolve `event_type_id` by joining to `event_types`, so the structure documents itself. Your task is
making that join discoverable, not writing comments.

**One way our raw layer is harder than typical.** The column names are heavily abbreviated — `uid`,
`nm`, `cat`, `arch`, `st`, `chan`. A modern schema would give you `user_id`, `created_at`,
`archived_at`, `status`, `channel`. Our undocumented arm therefore combines two difficulties,
unlabelled codes and cryptic names, and only the first is universal. A warehouse with readable names
and inline enums sits between our undocumented and documented arms, and would score better than
10 of 15.

### One table holding several kinds of thing

`evt` contains three event types, separated by an integer. An analyst who knows the domain knows
that `etype = 2` means a completed habit. That fact was never written down, because everyone on the
team already knew it.

```sql
-- columns that probably encode a KIND, and carry no comment
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name ~ '(type|kind|status|state|category|code|flag)$'
  AND table_schema = 'your_schema';
```

For each result, run `SELECT <column>, count(*) FROM <table> GROUP BY 1`. If the values are integers
or short codes, and the column has no comment, then an agent has to guess their meaning.

### A status code where only one value counts

`subs.st` holds 1 for active, 2 for cancelled, 4 for past due. Counting every row gives 457 live
subscriptions where the correct answer is 371, an overstatement of 23%. The query that produces it
looks reasonable.

### A NULL that carries meaning

`hab.arch` is an archive date. NULL means the habit is still being tracked. This is not recorded, so
the question "how many habits are still being tracked" cannot be answered reliably.

```sql
-- nullable date and flag columns, where NULL may carry meaning
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE is_nullable = 'YES'
  AND (data_type LIKE '%date%' OR data_type LIKE '%bool%')
  AND table_schema = 'your_schema';
```

### A flag with three values

`u.internal` holds 1, 0, or NULL. 271 rows are NULL, and some of those accounts are internal. They
can be identified only by their email domain. `WHERE internal = 0` removes 271 real users from the
result. `WHERE internal IS NOT TRUE` includes the internal accounts.

```sql
-- a flag that is not a boolean
SELECT internal, count(*) FROM u GROUP BY 1;   -- three groups, not two
```

If defects of this kind exist in your warehouse, an agent will answer some questions incorrectly and
will not report any problem. Standard data quality tests do not detect them. No column is null when
it should not be, and no constraint is violated.

---

## 3. What corrected the failures, ordered by effort

| intervention | effort | correct answers | wrong numbers served |
|---|---|---|---|
| none | — | 10 of 15 | 5 |
| **column comments** | one afternoon | **15 of 15** | **0** |
| a conformed star schema | days | 14 of 15 | 1 |
| star schema and comments | days plus hours | 14 of 15 | 1 |
| a semantic layer | a project | 15 of 15 | 0 |

### The cheapest intervention produced the largest improvement

`COMMENT ON` is supported by Snowflake, BigQuery, Databricks, Postgres and DuckDB. In dbt, a
`description:` field compiles to it. No new tool and no migration is required.

Comment the columns, not only the tables. The statement that corrected our largest failure is one
line:

```sql
COMMENT ON COLUMN evt.etype IS
  'Event kind: 1 = app open, 2 = COMPLETED HABIT (a value moment), 3 = reminder shown.
   Counting completed habits means etype = 2 only.';
```

A table-level description such as "one row per in-app event" would not have prevented any of the
wrong answers. The mapping from code to meaning is what the agent needs.

### Good names achieve the same result structurally

The star schema arm never saw `evt`. It saw `fct_value_moments`, which already contains only one
event kind. The defect cannot occur, because the incorrect rows are not present in the table.

This is the standard argument for conformed dimensions, with an additional reason. A table name
cannot become out of date in the way a comment can, and an agent reads names before it reads
comments.

---

## 4. Three interventions that helped less than expected

### Adding comments to a star schema that is already well named

Comments moved the raw tables from 10 of 15 to 15 of 15. On the star schema they moved 14 of 15 to
14 of 15.

The practical conclusion: where marts are already named and modelled well, documentation adds
little. Where they are not, documentation is the largest available improvement. Apply the effort
where the naming is weakest.

### The semantic layer, on this set of questions

It matched a documented star schema and required a modelling project rather than an afternoon. Two
qualifications apply in opposite directions. Our questions were simple lookups and counts, which is
where a semantic layer contributes least. It also removed the class of error where the agent selects
the wrong rows, because it does not select rows at all.

### Assuming the semantic layer will be used

The agent did not open the metric catalogue on 5 of 15 runs. It queried the tables directly instead,
although the system prompt instructed it to prefer governed metrics and the tool description
repeated that instruction.

Building a semantic layer does not guarantee that an agent will use it. Measure how often it is
consulted. Consider removing raw SQL from the agent's toolbox rather than relying on an instruction.

---

## 5. Two problems that appear before the modelling work matters

### "Last week" is not a question the warehouse can answer

With no governed period vocabulary, the agent constructed its own definition. In one run it derived
the week from `max(ts)` in the data and selected the week before the intended one. In another it
used the system clock, selected a window containing no data, and answered 0. The correct date was
stated in the first line of its prompt.

If your agent computes date windows itself, correctness depends on how it happens to compute them. A
governed `period` argument that resolves the same way every time is one of the more useful things a
semantic layer provides, and it is rarely the reason teams build one.

### Evaluation questions are often ambiguous

Three of our five questions had two defensible answers. "How many habits did people complete" means
either 3,785 completions or 1,813 distinct habits with at least one completion. The agent selected
different readings on different runs, which is difficult to distinguish from an unstable model.

Rewriting the questions so that each had one reading reduced run-to-run disagreement from 6 of 30
cells to 1 of 30.

When an AI analyst appears unstable, examine the questions before concluding that the model is at
fault. This result was the most useful one we obtained.

---

## 6. What these results cannot support

**Whether the ranking in section 3 is real.** Five questions and one run. Every intervention from
column comments upward scored 14 or 15 of 15, so the test can no longer separate them. The only
difference we would defend is between doing nothing and doing something.

**Whether it applies to harder questions.** Ours were counts and lookups. Ratios, trends,
period-over-period comparisons and diagnostic questions are where semantic layers are expected to
contribute most, and we have not tested them.

**Whether it applies to your model.** One model, one configuration. Sensitivity to documentation and
format is known to decrease as models improve.

**The cost of an incorrect answer.** We measured accuracy. We did not measure what a wrong number
costs when it reaches a decision. That cost determines how much of this work is worth doing, and
only you can estimate it.

---

## Summary

1. Add comments to columns, especially those holding a kind, a status, or a NULL that carries
   meaning.
2. Prefer good table and column names over comments where the modelling effort is affordable.
3. If a semantic layer exists, measure whether the agent uses it.
4. Do not let an agent determine what "last week" means.
5. When evaluation results look unstable, examine the questions first.
