# How answers are graded

Every run ends in one **typed outcome** — `answer`, `refuse`, or `clarify` — so grading never
phrase-matches prose. Each of the 65 cases declares in YAML what a correct response *is* (an
`expect` block); the grader reads that, and never infers the expected outcome from the tier:

- **`metric_answer`** — a number within tolerance of an independent gold SQL, from the right
  governed metric (when the model declares its `source_metric`).
- **`refuse`** — a refusal carrying the expected **coded reason**; for such a case *any* served
  number is a miss (a confident-wrong, or a right number reached off-governance = a fabrication).
- **`diagnostic`** / **`keywords`** — named the right driver / the right metric (an LLM judge for
  the diagnostic tier, scored against a gold decomposition).

Every response reduces to one bucket — **right / wrong / I-don't-know / deferred / other / error** —
reported per rung. `confident_wrong` and `fabricated` are tracked separately and reported on their
own denominators, never pooled.

The gold set is treated as **fallible** and sanity-checked. Benchmark "gold" is wrong more often
than anyone admits, and three errata in [`RELIABILITY.md`](RELIABILITY.md) are cases where it was.

## Selective prediction: three numbers, never one

An agent that may decline cannot be judged on accuracy alone, since refusing everything scores
perfectly on what it answers. `harness/evals/selective.py` is the single definition:

| | |
|---|---|
| **coverage** | of the questions that *have* an answer, the share it attempted |
| **silent error rate** | of everything asked, the share where it served a confident number that was false — a wrong answer, or an answer to a question that had none |
| **balanced accuracy** | the mean of the two families' accuracies, so the score describes the agent rather than how many of each kind of question the suite happens to contain |

A fourth number, **grounded-answer rate**, is reported beside these and never averaged into them —
see [`EVIDENCE-GRAPH.md`](EVIDENCE-GRAPH.md). "Was it right" and "can it be inspected" are different
questions, and their mean answers neither.

## The verifier is scored, not trusted

The LLM verifier is the only component whose verdict is a probability rather than a proof, so it is
measured like anything else. On the ladder run's R9 cell it made 58 decisions, stopped 12 answers,
and none of the 12 was a correct answer.

It let one bad answer through: *"how many users do we have in total?"*, answered off a signups
metric — a real number to a question nobody asked, which is the failure the whole experiment is
about.

Those four counts are columns in `results/published/2026-07-reliability-ladder/cells.csv` (`judge_ran`,
`judge_rejected`, `judge_blocked_good`, `judge_passed_bad`), so the claim is checkable rather than
asserted.

An earlier blind 3-judge panel (n=37) is **invalidated** and must not be quoted: 7 of its 37 cases
were labelled against a corrupted evidence field, and the run metadata carries `"stale": true`
saying so.

## Re-grading costs nothing

Because the claim audit is a pure lookup over the trace, `./bench regrade --run <dir>` re-derives
every verdict on a finished run **with no model calls**. The model's outputs are immutable; only
what is read from them changes.

That is how a fix to the grader or the audit reaches numbers already measured, instead of costing a
re-run — and it is why the errata above could be applied to published results rather than
invalidating them.
