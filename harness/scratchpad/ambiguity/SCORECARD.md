# preflight — scorecard

*Static, cross-layer ambiguity detection for AI-ready analytics. The 60-second read.*

## The claim

A number can be right for a human and wrong for an agent. A senior analyst asked "what is revenue?"
asks back — gross or net, before or after refunds. An agent picks one reading silently and returns a
figure that is off by a few percent: small enough to pass review, large enough to be wrong.

**preflight computes those dangerous confusions offline, from the governed definitions, before the
agent ever runs a query.** It compares every metric, column, and documented term across the whole
stack and reports the pairs a competent reader would confuse and that resolve to different numbers.
No model is required, no questions, no run.

This is the **selection** half of grounding safety: two valid definitions exist and the agent binds
the wrong one.

## The number

On two blind, realistically messy environments, generated and labelled without the detector in the
loop, and scored across two domains with **zero per-domain tuning**:

| environment | dangerous-collision recall | precision | tuning |
|---|---|---|---|
| Sales (3 layers: semantic + warehouse + docs) | **16 / 16 (100%)** | 88% | — |
| Retail (cross-domain, 300+ columns) | **18 / 19 (95%)** | 84% | **zero** |

The headline is the **high-danger recall**: the numerically-silent confusions that would ship a wrong
number are caught almost completely, and it generalises to a second domain untouched.

## Proven on real, public code

Not only on our fixtures. preflight ingests four real semantic-layer formats and catches genuine
ambiguity in public repositories a reader recognises:

| stack | public repo | what it caught |
|---|---|---|
| **Cube** | `cube-js/stripe-schema` | **scope trap** — `totalFailedAmount` is `totalGrossAmount` plus a `status='failed'` filter; a "total revenue" answer silently includes failed charges |
| **dbt MetricFlow** | `full-funnel-ai-analytics` | **name collision** — one name `total_sessions` bound to two different measures (the author had hand-warned about it in prose) |
| **raw dbt** (no semantic layer) | `mattermost/mattermost-data-warehouse` | **definition divergence** — `total_arr` computed two incompatible ways in two models |
| **dbt MetricFlow** | `dbt-olist-metrics` | **nothing — correctly.** Its bug (a ratio that is silently always 100%) is a construction defect, not an ambiguity. A precise boundary, shown on real data. |

Four dialects ship today: native, dbt MetricFlow, raw dbt SQL, Cube. The core detector is the same
for all of them; each format is just an adapter.

## The honest boundary

A number goes silently wrong in two ways. preflight covers the first.

| | catches | example |
|---|---|---|
| **Selection** (ambiguity) | ✅ preflight | gross vs net revenue; a metric silently scoped to active customers |
| **Construction** (a primitive used wrong) | ❌ separate validators | a stock summed over time; a ratio whose numerator and denominator mix bases; a metric on a column that does not exist |

We measured this the hard way. A practitioner and a three-person red-team panel labelled the retail
environment cold and found **22 dangerous collisions**. Re-tagged by cause, only about **8 are the
ambiguity class** preflight targets; it caught **5 of those**. The remainder — and the 8 that both
preflight and a single-LLM baseline missed — are construction defects (wrong cost base, a value that
matches zero rows, a distinct-count summed across a grain). They need a **family of per-primitive
validators**, not an ambiguity checker. Naming that boundary is what makes the tool trustworthy.

## Why a governed layer matters

The same company, three levels of governance, same underlying numbers:

| surface | metric definitions | dangerous metric-level findings |
|---|---|---|
| Governed (semantic layer) | 39 | 9 |
| Welded (saved SQL, no layer) | 41 | 8 — recoverable from the query SQL (sqlglot recovers aggregate + table on 41/41, scope on 34/41) |
| **Bare (schema + docs only)** | **0** | **0** |

The lesson: preflight needs a **definition surface**. With none, there is nothing to compare and the
agent welds its own scope invisibly. A governed semantic layer gives clean, precise input; raw dbt is
recoverable but noisier. That difference is itself the argument for governance.

## How it runs

- **Static and offline** — reads the declarations, not the query traffic. Says which confusions are
  *possible*, before any have happened.
- **No model required** — structural detection runs on the standard library; embeddings are an
  optional extra that sharpens the confusability gate (and are the path behind the scored numbers).
- **A CI guardrail** — `preflight scan --fail-on high` exits non-zero on a dangerous collision, so a
  change that introduces one fails the build. Ships as a GitHub Action and a pre-commit hook.

---

*Evidence: blind environments `env_sales` / `env_retail` with committed ground truth; the human-gold
audit (`human_scorecard.md`); the no-semantic-layer contrast; live scans of the public repos above.
Scored numbers use the embedding gate. The two-mode framing and the per-primitive validator roadmap
are in `SUMMARY.md` and `PRIMITIVE-VALIDATORS.md`.*
