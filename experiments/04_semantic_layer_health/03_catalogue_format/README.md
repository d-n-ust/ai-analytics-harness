# Does it matter how you write the metric list?

An AI analyst starts every question by reading a list of the metrics available to it. Today we hand
it that list as prose. This test asks a simple thing:

> If we hand it exactly the same information written as JSON, or as a table, does it answer better?

Nothing about the data model changes. Same metrics, same descriptions, same everything. Only the
way it is written down.

## Why anyone should care

Every other test here says *"fix your data model"* — which is real work, and slow. This one, if it
works, says *"change one line of formatting code"*. Same information, better answers, an afternoon
of effort.

That would be the cheapest advice we could give anyone. It is worth knowing whether it is true.

## The three versions

**Today's version** — sentences and indented lines.

```
- value_moments: Number of value moments (completed habits) in the period.
    also called: completed habits, habit completions, activity
    group_by: region, platform, channel, country
    filter: region, platform, channel, country, is_internal
    period: supported
```

**As JSON** — the same facts as data, with the field names matching the names the AI uses when it
calls a tool.

```json
{ "name": "value_moments",
  "description": "Number of value moments (completed habits) in the period.",
  "also called": ["completed habits", "habit completions", "activity"],
  "group_by": ["region", "platform", "channel", "country"],
  "period": "supported" }
```

**As a table** — the same facts in rows and columns.

```
| metric | description | also called | group_by | filter | period |
|---|---|---|---|---|---|
| value_moments | Number of value moments… | completed habits, … | region, platform, … | … | supported |
| referrals     | Number of referrals…    | referrals, invites, … | —                 | status | supported |
```

The table exists to answer a follow-up. If JSON wins, is that because the information is
*structured*, or just because it is *lined up and easy to scan*? The table is lined up but is still
ordinary text, so it separates the two.

## The five questions

All five turn on one thing: **which dimensions a particular metric can be broken down by.** Metrics
differ, and the difference is easy to miss.

| metric | can be split by |
|---|---|
| `value_moments`, `active_users` | region, platform, channel, **country** |
| `new_signups` | region, platform, channel — **no country** |
| `marketing_spend` | channel only — **no region** |

`country` is a real dimension and Germany is a real value, so *"how many signups from Germany?"*
looks answerable and is not. The right answer is to say so.

Two of the five are unanswerable, three are answerable, and they are paired: the same country asked
of a metric that supports it and one that does not, and the same metric asked by a dimension it has
and one it does not. No single habit — always refuse, always answer, always distrust the word
"Germany" — can pass the set.

```bash
./bench study 03_catalogue_format --mock --reps 1   # checks only, costs nothing
./bench study 03_catalogue_format --reps 1          # the real thing, about 4 cents
```

## What went wrong the first time

The first run looked decisive: prose 5/5, table 4/5, JSON 1/5. It was measuring our own bugs.

The three versions were not saying the same thing. Four differences had crept in, each because
every version decided its own wording independently:

| | what happened |
|---|---|
| the opening line | Only the JSON version mentioned the `segment` option, right at the top. It then applied a segment nobody asked for and answered **227** where the truth was **283**. |
| a filter's value | Prose wrote `is_internal=false` — handing the model a ready-made value — where the other two only named the field. |
| saying "none" | A metric with no breakdowns showed an explicit `—` in the table and **nothing at all** in the other two. For a test about how breakdowns are described, that is the whole point. |
| a missing fact | One kind of filter was never printed in any version, so the system accepted a filter the list never mentioned. |

The check meant to prevent exactly this passed all four times. It verified that each version
*contained* every name, description and synonym — and containment cannot see an extra sentence, a
value the others leave out, or a fact stated as silence.

## The fix

Content is no longer each version's decision. One shared table defines every fact a metric has,
including the empty ones; a version receives labelled cells and chooses only how to lay them out.
It cannot skip a field, invent one, or word "none" its own way, because it never sees the metric.

The opening line and the section headings moved out of the versions for the same reason — a heading
is content, and a version carrying a sentence the others lack is a second change however it is
formatted.

The check is now: **all three must use exactly the same words.** Not the same order and not the
same repetitions — a table names a field once in a heading where prose names it under every metric
— but the same set of words, ignoring each format's own scaffolding. All three currently sit at 193
words. Feeding each of the original four bugs back in, the check now catches every one before any
money is spent.

Two things improved in production as a side effect: the shipped metric list now states "none"
explicitly instead of staying silent, and it now mentions a filter it had been quietly accepting
without advertising. There is also no longer a second copy of the prose renderer kept in step by a
test — there is one renderer, and what ships is one of the three versions rather than a near-copy
of one.

## What we have actually measured: nothing yet

Each version was run three times on exactly the same input. If there were no wobble, every question
would score 3/3 or 0/3.

| version | total | questions that disagreed with themselves |
|---|---|---|
| prose | 14/15 | 1 of 5 |
| JSON | 14/15 | 1 of 5 |
| table | 15/15 | 0 of 5 |

**Two of the fifteen version-question cells gave different verdicts across three identical runs,
and the gap between best and worst version is one point.** The wobble is wider than the gap, so
none of these totals means anything yet. The run now prints this line itself, so a future reader
does not have to work it out by hand.

That is the whole reason to repeat before believing a ranking. The first run of this study showed a
four-point gap and it was our own bugs; the second showed two points and it was noise. Every one of
them looked like a result.

### An earlier version of this table was worse, and the cause was ours again

Before the last fix these same three versions scored 14 / 13 / 12 with **five** unstable cells. The
difference was a missing fact: a refactor had quietly dropped the list of time buckets a metric can
be split by (`day`, `week`, `month`) from all three versions at once, while the tool still accepted
them.

Restoring it cut the wobble from five cells to two and steadied the refusal wording as well — the
table version had produced three different reasons for the same refusal across three runs, and now
gives the same one every time.

So a **more complete metric list made the analyst more consistent, not just more correct**. That is
a genuine observation and a soft one: five questions, one comparison, no repetition of the
comparison itself. It is worth testing properly rather than repeating as a finding.

### Why the check did not catch it

The guard compares the three versions against each other. A fact deleted from all three at once
leaves them in perfect agreement, so it saw nothing wrong. This is the same blind spot as the
containment check it replaced, moved up one level.

There is now a second guard that compares the metric list against the **tool definition** — an
independent source — and fails when the tool accepts an argument the list never documents. The
first attempt at it passed while the fact was still missing, because it searched the text for the
word "week" and found it inside "last_week". Checks that look for words in prose can be satisfied
by coincidence; this one now reads the structure instead.

What *is* established is structural, and does not depend on any score: the three versions provably
say the same things now, and the checks that prove it fail loudly when they stop being true.

## What has to happen next

**Write 30 to 40 questions of this kind.** Five cannot separate anything — study 01 learned this at
real cost, and this run repeats the lesson rather than escaping it. The question design works: it
produces genuine disagreements between versions. There are simply not enough of them.

**Decide what a refusal has to get right.** Every run now prints two columns — whether the analyst
refused at all, and whether it named the right reason. They can rank the versions differently.
Refusing instead of inventing a number is reliability; explaining why correctly is usability. The
open question is which one the headline number should be.

Until both are done, no number in this folder should be quoted.

## The uncomfortable part

If writing the list as JSON clearly wins, our headline advice becomes *"change how you print the
list"* — which sits awkwardly next to a practice built on data modelling, and undercuts "fix your
model" as the recommendation.

We would publish it anyway. The whole argument of this practice is that structure beats prose. A
belief you only test where it is convenient is not a belief.
