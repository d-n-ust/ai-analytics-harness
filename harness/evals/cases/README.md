# Evals — the declarative test set

Every case is one question with a **declared expected outcome**. Nothing is inferred
from tier strings; the grader reads `expect` and scores against it. This is the whole
contract, so it stays small and legible — a case is readable by a human and by a
machine (validated against [`schema.json`](./schema.json)).

## The reliability contract

A correct response is exactly one of two things:

1. **Answer with a single governed metric** — the served number matches the
   independent `gold_sql` (a raw-SQL oracle, *not* the semantic layer, so it can catch a
   mis-defined metric), and the declared `source_metric` matches the expected one.
2. **Refuse with the correct typed reason** — for a question no single governed metric
   answers, the refusal *is* the right answer, and its coded `reason` must match.

Anything else — a wrong number, a right number reached by a non-governed path, a
refusal with the wrong reason, an over-refusal of an answerable question — is a miss.

## Case shape

```yaml
cases:
  - id: t1_signups_june
    tier: lookup                 # grouping label, for reporting only
    question: "How many new users signed up in June 2026?"
    expect:
      type: metric_answer        # metric_answer | refuse | diagnostic | keywords | clarify
      metric: new_signups        # the governed metric the answer must come from
      gold_sql: "SELECT ..."     # independent oracle; run each eval to derive the number
      tolerance: 0.02            # tight — a governed number is exact; absorbs float/rounding only

  - id: vw_arr
    tier: valid_but_wrong
    question: "What is our ARR?"
    expect:
      type: refuse
      reason: no_governed_definition   # enum in schema.json; matched against the refusal's coded reason
      gold_sql: "SELECT ..."           # PROVENANCE only (the trap / if-it-existed value) — not graded as the answer
      tolerance: 0.02
    note: "No ARR metric (= mrr x 12). A number here is a reliability violation."
```

`diagnostic` cases carry `driver` + `cause` keyword lists; `keywords` cases carry a
`keywords` list (did the answer name the right metric).

## Layout

- `coverage/` — answerable by one governed metric (`lookup`, `filtered`, `metric`, `knowledge`).
- `reasoning/` — `diagnostic` (driver + cause).
- `reliability/` — the traps: `wrong_metric` (refuse, plus one discrimination control),
  `phantom_dimension`, `unanswerable`, `false_premise`, `adversarial`.

`gold.py` loads every `*.yml` here, validates it, and computes gold by running each
`gold_sql`. `grade.py` scores against `expect`.
