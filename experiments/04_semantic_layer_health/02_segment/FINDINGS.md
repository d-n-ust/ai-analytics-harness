# Study 02 — what the segment runs established

Findings from this study. The experiment-wide measurement results are in `../FINDINGS.md`; the
practitioner summary is in `PRACTITIONER-NOTES.md`; the same row on dbt MetricFlow is in
`../02_segment__mf/FINDINGS.md`.

Every number below is computed from `results/experiments/04_semantic_layer_health/
20260809-121926-01_segment_promoted_to_metric` — eight questions, three repetitions, `gpt-5-mini`
at `reasoning=minimal`, rung 3, R7. The run directory keeps the pre-rename arm names; the mapping
is in `study.yml`.

---

## 1. The arm totals, and why they are the least informative table here

| arm | correct | confidently wrong | abstained |
|---|---|---|---|
| A_implicit | 18/24 | 5 | 4 |
| B_documented | 21/24 | 3 | 3 |
| **D_declared** | **23/24** | **1** | 3 |
| B_prose_swapped | 19/24 | 4 | 4 |

Three of thirty-two cells disagree with themselves across identical repetitions.

The totals suggest a ladder: 18, 21, 23. The per-item table shows something different.

---

## 2. Two questions carry the entire result

| question | A_implicit | B_documented | D_declared |
|---|---|---|---|
| "how many habits did our **customers** complete last week?" | 0/3 | **0/3** | **3/3** |
| "**excluding staff and test accounts**, June 2026?" | 0/3 | **3/3** | 3/3 |
| "…across every account, including internal?" | 3/3 | 3/3 | 3/3 |
| "…in total, counting every account?" | 3/3 | 3/3 | 3/3 |
| "how many users completed 5+ habits in a single day?" | 3/3 | 3/3 | 2/3 |
| "how many users completed 3+ habits in a single day?" | 3/3 | 3/3 | 3/3 |
| "how many power users did we have?" | 3/3 | 3/3 | 3/3 |
| "how much did we spend on paid search?" | 3/3 | 3/3 | 3/3 |

Six of eight questions are flat across all arms. The gap between A and B is one question. The gap
between B and D is one different question. Everything else is a constant added to all three totals.

**A five-point spread produced by two items is not a five-point effect.** The totals in §1 should
not be quoted without this table beside them.

---

## 3. The two discriminating questions differ in one word, and that difference is the finding

| question wording | what the agent must know |
|---|---|
| "our **customers**" | that "customer" means a real user, and which metric counts those |
| "**excluding staff and test accounts**" | which dimension carries the staff flag |

The second is answerable without any metric documentation at all, because the exclusion is stated
in terms that map onto a column the agent can see. The first is not.

That is why `B_documented` splits the two: its descriptions say *"excludes internal/test accounts"*,
which matches the June question's wording and not the week question's. `D_declared` answers both,
because its segment carries `customers` as a synonym.

**The vocabulary confound is visible in this table rather than merely declared.** `D_declared`'s
single win over `B_documented` is on the one question whose wording its synonym list contains. The
confound is not a theoretical objection to the result — it is the result.

---

## 4. The merge added four questions and no discriminating power

This study was formed by merging two earlier studies: the segment hidden in a metric **name**, and
the segment hidden inside an **aggregate** (`power_users` restricting to 5+ moments in a day inside
its `agg`). The stated reason was that item count is the binding constraint.

The aggregate instance contributed nothing:

| aggregate-instance question | A | B | D |
|---|---|---|---|
| 5+ habits in a single day | 3/3 | 3/3 | 2/3 |
| 3+ habits in a single day | 3/3 | 3/3 | 3/3 |
| "power users" | 3/3 | 3/3 | 3/3 |

All three arms answer all three questions, and the declared arm loses a cell. A threshold welded
into an aggregate is a real defect, but these questions do not detect it: the agent reaches the
right number whether or not it can see the predicate.

**The merge doubled the denominator and left the numerator alone**, which moves every rate toward
the middle and makes the study look more stable than the evidence is. `../FINDINGS.md`'s note that
merging "bought" the gap over the instability is wrong on this run and is corrected there.

---

## 5. A right number graded as a silent error

On the June question, `A_implicit` returned **15,329 — the correct value** — and was graded wrong
and confidently wrong. Its trace shows why:

```
query_metric  metric=value_moments  filters={user__is_internal: False}   -> 15329
explanation:  "Queried value_moments for June 2026 with filter user__is_internal = False"
```

The agent applied the population filter itself, explained that it had done so, and reached the
governed figure. The expectation names `real_value_moments` as the metric holding the answer, so
declaring `value_moments` counts as a miss.

Two consequences:

- **The `confidently wrong` column overstates.** It is this experiment's most alarming figure — a
  wrong number served with no signal of doubt — and here it fires on a right number reached by an
  unexpected route. Three of `A_implicit`'s five confident-wrong flags are this case.
- **The item measures metric choice, not the answer.** That is a defensible thing to measure under
  R7, where a number must trace to a declared governed result. It is not the same thing as the
  headline claim that removing the fact produces wrong numbers.

The week question does produce a genuinely wrong number: `A_implicit` and `B_documented` both
answered **3,785** where the correct figure is **3,642**, with no filter applied at any point.

---

## 6. What this study can and cannot support

**Supports.** A question that uses business vocabulary for a population — "our customers" — is not
answerable from a metric name and a description that uses different words. One item, three
repetitions, no variation, on both engines.

**Does not support.** A rate. Two discriminating items cannot produce one. Nor a ranking of B
against D: their single point of difference is the item whose wording D's synonyms contain.

**The two arms that would settle it are still unbuilt**, and their absence is now the main thing
blocking this row:

| arm | what it isolates |
|---|---|
| `D_declared_neutral` | D with the bespoke synonyms removed — separates structure from wording |
| `B_documented_minus` | B with one unrelated metric deleted — equalises the candidate count |

---

## Provenance

| claim | source |
|---|---|
| all per-arm and per-item figures | `20260809-121926-01_segment_promoted_to_metric/run.json` |
| the June trace | the same run, `A_implicit`, `p_pop_customers_june`, rep 0, `steps` |
| the correct week value 3,642 | `D_declared` on `p_pop_customers_week`, all three reps |
