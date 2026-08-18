# Experiment 05 — practitioner notes

The practical lessons from building and running the two studies: what broke, what the fix was, and what
to do differently next time. Results live in `findings.md`; this file is the how-to and the gotchas.

## Measurement

### The gold is a deterministic oracle, not an LLM judge

Every answer is graded against a fixed `gold_sql` that runs against the clean star (`compute_gold`), so
the answer key cannot drift toward what the treatment changed, and no judge model sits in the grading
path. `grade_numeric` scans **all** numbers in the answer prose and passes if any is within tolerance
(default 2%) of the gold, so a multi-column or hedged answer that contains the right figure is scored
correct. This means a "wrong" numeric row genuinely missed the gold, not that a scalar extractor tripped
on formatting.

### The governed layer must state every scope rule once, and the gold must match it

This is the sharpest lesson of the two studies. Study 02's first `s2_after` governed the
internal-account rule for user and activity metrics but left it implicit for revenue, and one activity
gold (`value_moments`) did not apply its own stated rule. Both models excluded internal accounts
consistently (the reasonable reading of "staff and test accounts exist"), and were scored wrong for a
**gold inconsistency**, not a real error. The construction "errors" were systematically 4 to 6% below
gold, all traceable to one omitted `NOT is_internal`.

Fix: make the rule uniform and explicit (exclude from every metric, revenue included), state it on the
`mrr` and `net_revenue` COMMENTs, and match the gold. Re-run both models. wrong-SELECTION is recovered
from SQL substrings and is independent of the gold, so the headline did not move; only construction and
SER did.

Rule of thumb: **before believing a construction-error number, run the agent's actual SQL against the
star and diff it against the gold_sql.** If the deltas are systematic and small, suspect the gold, not
the agent.

### Recover the selection from the trace, do not infer it

Which grounding the agent used is observed, not guessed:

- Study 01: the metric name from the `query_metric` tool argument (`_queried_metrics`). `source_metric`
  is only populated at rung 7, so at rung 3 the tool argument is the mechanism.
- Study 02: substrings in the concatenated `run_sql` query text (`_sql_of`), matched against the
  per-case `wrong_grounding` markers (`billed_amount`, `is_test`, `daily_rollup`). This puts the
  column-level confusion into wrong-SELECTION rather than lumping it into SER.

### Trap design: three lessons the hard way

1. **Explicit-intent questions find no effect.** A capable agent with self-describing metric names
   navigates sprawl. The trap must be a **name-match**: the question wording matches a wrong metric that
   is present only on the sprawled layer and returns a clearly different number.
2. **Sliced traps conflate selection with filter-application.** A country/category/plan cut makes the
   agent botch the filter even on the governed layer, so those items score high everywhere and measure
   the wrong thing. They were dropped.
3. **Keep the flagged tier structural whole-population** traps, where the only free variable is which
   metric or column is picked. Add clean controls in the same families so the effect can be shown to
   concentrate on the flagged tier.

## Data modelling

### Stocks are semi-additive; model them from snapshots

`mrr`, `paying_users`, and `active_habits` are stocks (a state, not an event). Modelled over event time,
a period filter shrinks them and manufactures a fake construction error. They are modelled from monthly
snapshots instead: `fct_subscription_months` for MRR and paying users, a `fct_habit_months` view for
active habits, aggregated with `non_additive_dimension: {window_choice: max}` in MetricFlow. This makes
the residual construction harm genuine agent query-building rather than a fixture artifact. A stock
summed over time is wrong whatever the YAML says; check additivity from the aggregate, not the name.

### Event vs state vs metric

The recurring bug source in these fixtures is conflating an event (`moments` completed at a time) with a
state (a subscription is currently active) with a metric (MRR). A table that mixes them has no stateable
grain and every period aggregate over it is ambiguous. Study 02's `moments` overloaded across `activity`
and `daily_rollup` is exactly this, and it is the `value_moments` trap.

## MetricFlow (study 01 port)

Porting the bespoke semantic layer to real dbt MetricFlow surfaced several requirements a homemade YAML
never enforces:

- **Multi-document form.** The manifest and the raw YAML use singular `semantic_model:` / `metric:`
  documents; parse with `yaml.safe_load_all`. The preflight adapter was fixed to handle both.
- **Every model needs a primary entity.** Non-conformed activity facts got a synthetic primary
  (`user_id || '|' || CAST(active_date AS VARCHAR)`) so MetricFlow stops raising "No primary entity".
- **"No valid join paths"** on a filter came from `is_internal` living on two models both keyed by
  `user`. Fix: make `dim_users` the conformed dimension that holds `is_internal`, and have the activity
  fact join to it via a foreign `user` entity.
- **A non-temporal model is rejected**; MetricFlow needs a time dimension. The snapshot tables supply
  one, which is also what makes the semi-additive stock modelling correct.
- **A time-spine view** (`mf_time_spine`) is required for cumulative and time-based metrics.
- **Do not false-trap a filtered metric against its own measure.** The adapter only emits an orphan
  measure (one no metric references), so a filtered `simple` metric does not collide with the raw
  measure it wraps.

## Native dbt scan (`--dialect dbt-manifest`)

- One `dbt parse` produces `target/manifest.json` with all three layers and needs **no warehouse
  connection**. Prefer the manifest over scraping YAML: refs are resolved, it is versioned, and it is
  the artifact CI already has.
- The **project root is recovered from the manifest location** (`<root>/target/manifest.json`), so each
  finding cites the real source file. Semantic definitions cite their `original_file_path`; warehouse
  columns cite the model's `patch_path` (the schema `.yml`, prefixed `<package>://`, stripped), because
  that is where columns are documented, not the `.sql`.
- **`data_type` is null for every column** after `dbt parse` (it does not introspect the warehouse);
  real types need `dbt docs generate` and `catalog.json`. The loader tolerates the null.
- Read the manifest **defensively** (only stable fields) so it survives schema drift across manifest
  versions. Validated against manifest v12 (dbt 1.12).

## Harness operations

- **DuckDB is single-writer.** Two runs against `runs/warehouse.duckdb` collide on the file lock (the
  harness waits 10s then fails). Run models **sequentially**, not in parallel; chain the second run to
  start after the first releases the lock.
- **Model key names carry no date suffix**: `claude-haiku-4-5`, `claude-sonnet-5`, `gpt-5-mini`. Full
  names in code and docs, never short aliases.
- **Scope the agent to a warehouse variant** with `con.execute("SET search_path = '<schema>'")` before
  `build_grounding(con, rung=..., schema=...)`; an unqualified `DESCRIBE` fails without the search path.
- **preflight lives outside the uv workspace** (like `troodos/`), so its heavier closure never lands in
  the shared engine+harness environment. Scan it from its own venv (`uv pip install -e preflight`, add
  `[embeddings]` for the validated gate); harness code runs under `uv run`.
- **Persist per arm/layer.** A long agent run should write its result file after each arm so an
  interruption does not lose the completed work. `--mock` validates the whole pipeline with no API key.

## The customer scorecard

`scorecard.html` is a single self-contained page (no external requests; the artifact CSP blocks CDNs).
It uses the Decision Spine design tokens copied from the site's `globals.css` (warm paper, midnight ink,
copper/gold, the reserved `risk`/`verified` status colors) with a light default and the "desert night"
dark theme via token-flip. Two build notes:

- **Status is never carried by hue alone** (the red/green deuteranopia trap the brand tokens call out):
  before/after markers differ by glyph (cross vs tick) and border (solid vs dashed) as well as color.
- **Non-ASCII glyphs are written as HTML entities** so the page renders correctly whether or not the
  host declares a charset. The brand fonts are not committed, so the page uses the brand's own declared
  fallback stacks (Georgia, system-ui, Menlo/SF Mono).
