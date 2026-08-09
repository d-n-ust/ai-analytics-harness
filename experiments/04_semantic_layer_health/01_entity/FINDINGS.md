# Study 05 — what building and running it actually taught us

Findings from this study specifically. The experiment-wide measurement results are in
`../FINDINGS.md`; the hypothesis argument is in `../prelim_summary_part1.md`.

Most of what follows is about the **instrument**. That is not an apology: five of the seven
findings below changed a number we had already reported, and four of them were invisible until
someone read a trace.

---

## 1. Three of the first five questions were ambiguous, and it looked like model noise

Every run of this study reported "self-disagreement" — cells giving different verdicts across
identical repetitions — and every time it was read as the agent being unstable. It was mostly the
questions.

| question | the two readings | what happened |
|---|---|---|
| "how many habits did people complete" | 3,785 completions, or 1,813 distinct habits | `C_modelled` answered the second and was marked wrong |
| "how many habits are people still tracking" | 6,357 not archived, or 1,813 / 4,417 recently used | `D_declared` answered the second twice |
| "how many referrals converted" | joined 271, activated 266, or both 537 | scored near the floor in every arm; removed |

Rewriting them to have one reading each cut self-disagreement **from 6 of 30 cells to 1 of 30**.

**The measured "noise floor" was partly our own item design.** `../FINDINGS.md` reports 13% of
cells disagreeing with themselves and attributes it to the model. Some of that is real; some of it
was ambiguity being resolved differently on different runs. That number needs revisiting rather
than quoting.

---

## 2. "Last week" is not a question an ungoverned agent can answer

Two failures that looked like arithmetic slips were time failures:

```
4,307   derived "last week" from max(ts) and landed on 2026-06-29..07-05 — one week early
    0   used current_date, which is the real wall clock, not the harness's 2026-07-16
```

**The agent was told.** The system prompt's first line states the analysis date and the data-end
date. It used the system clock anyway.

Below rung 3 there is no governed period vocabulary — no `period=last_week` that resolves
deterministically — so "last week" is something the agent constructs, and it constructs it
differently each time. That is a real observation about what a semantic layer supplies, and it
belongs in the matrix's **grain/time** row. It does not belong in an entity study, so the questions
now state their window explicitly.

**What we did not do:** add a table comment restating the analysis date. Documenting a fact
*because* we watched the agent ignore it would tune the treatment to the test.

---

## 3. The semantic layer could not answer two ordinary questions, and that was our gap

`E_enforced` scored 9/15, refusing questions where the judge found no metric matching the thing
asked. That read as "enforcement trades correctness for caution".

It was not. The layer had no metric for a reminder count or a habit count — both measures a
habit-tracking company would obviously govern. Adding `reminders_shown` and `active_habits`:

| arm | before | after |
|---|---|---|
| E_enforced | 9/15 | **14/15** |

The check was never harsh. It was correctly refusing answers to questions our own modelling had
missed, and the governed arms were being tested against a handicap built into the treatment.

**The coverage finding survives and is stronger.** A question outside the layer can now be chosen
deliberately instead of arriving through a gap nobody decided on.

---

## 4. The governed arm ignores the catalogue a third of the time

`D_declared` scores 15/15. It is not fifteen governed runs:

| question | catalogue read? |
|---|---|
| completed habits | read · **never** · **never** |
| reminders | **never** · read · read |
| habits not archived | **never** · read · **never** |
| live subscriptions | read · read · read |
| marketing spend | read · read · read |

**Five of fifteen runs never called `list_metrics` at all** — straight to `get_schema` and SQL over
the mart. On those runs `D_declared` *is* `C_modelled_documented`.

Two consequences. A correctness total that hides this is misleading, and the `C` / `D` / `E` arms
scoring alike is partly because `E` was sometimes being `D`. **Catalogue usage should be a reported
column, not something found by reading traces.** The `context_audit` already detects it.

On one run it also invented a metric — `query_metric(metric="count_habits")`, refused as unknown —
which is the catalogue shaping expectations even where the thing does not exist.

---

## 5. `A_implicit` fails exactly as designed, and fails silently

Five confidently wrong numbers in the last run, more than any other arm:

```
completed habits   6311, 6311      ← etype=1, app opens
reminders          6311, 3785, 10641  ← the neighbouring event kinds, and every kind summed
```

Every wrong answer is a *different event kind from the same table*. `evt` mixes app opens (111,056),
completed habits (67,132) and reminders (15,219) behind an unlabelled integer, and with nothing
saying which is which the agent picks one and reports it without hesitation.

This is the defect the study was built to demonstrate, working precisely as intended — and the
failure mode that matters, because a wrong number is indistinguishable from a right one downstream.

---

## 6. Documentation closes the gap; the ladder above it adds little

Final run, three reps:

| arm | correct | confidently wrong |
|---|---|---|
| A_implicit | 10/15 | **5** |
| B_documented | **15/15** | 0 |
| C_modelled | 14/15 | 1 |
| C_modelled_documented | 14/15 | 1 |
| D_declared | **15/15** | 0 |
| E_enforced | 14/15 | 0 |

An afternoon of `COMMENT ON` takes 10/15 to 15/15 and removes every silent error. Nothing above it
improves on that here.

**Do not over-read this.** Five questions, one run, 4 of 30 cells unstable, and the set now has a
ceiling — B through F are indistinguishable. The honest claim is about `A` versus everything else.

The 2×2 that motivated six arms is inconclusive: documenting the messy tables helped (10 → 15);
documenting the star did not (14 → 14). That is the direction predicted — conformed naming
substitutes for documentation — but at this sample it is not a result.

---

## 7. Bugs the guards caught, and one they did not

| what | how it surfaced |
|---|---|
| the star preset omitted `agg_*`, so `query_metric` failed on ~70% of calls in `E` and `F` | **a trace read by hand** — every guard passed |
| documentation reached the model but not the fingerprint | the fingerprint block: two arms hashed identically |
| `visible_tables` inferred "star" from `rung 1.5 > 1` | rung 1.5 silently showed the clean tables |
| `_statements` split on a semicolon inside a quoted string | `COMMENT ON ... 'Archived date; NULL while active'` |
| `check_candidate_count` fired on its own empty input | `--arms` with a single arm |

The first is the one worth remembering. For three runs the governed arms were silently falling back
to raw SQL — they were not measuring a semantic layer at all — and **nothing detected it**. The
fingerprints differed, the same-numbers invariant held, the context audit passed. It took reading a
tool trace, prompted by a question about a wrong answer.

**A guard that checks the treatment reached the model does not check that the treatment worked.**

---

## What this study still needs

**Harder questions.** B through F are at ceiling; the set can no longer separate them. More reps
will not help.

**Catalogue usage as a column**, so finding 4 is visible without reading traces.

**A deliberate out-of-coverage question**, now that the layer is complete enough for coverage to be
a choice rather than an accident.

**Re-runs of studies 01–04.** The shared layer went from 15 to 17 metrics, so their stored results
are no longer comparable with future runs of themselves.
