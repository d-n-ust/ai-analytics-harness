# Experiment 05 — design (customer-first)

Status: **design, not built.** This decides what Experiment 05 should *check* and *present* before we
scaffold `experiments/05_ambiguity/`. It is written backward from the buyer's decision, not forward
from the code we happen to have. The underlying evidence mostly exists (T1–T5, the blind sales/retail
environments, the human-gold audit, the no-SL contrast); 05 is about assembling it into something a
customer finds convincing — and finding the gaps.

Design principle: **present outcomes, not apparatus.** The customer never sees "T3" or "shuffle
p=0.038". They see "does it catch the dangerous confusions on a realistic stack, without drowning me
in noise, and what does it miss." The T-tests are the evidence underneath; the presentation is in the
customer's terms.

---

## 1. The customer and the decision

Who: a founder / CTO / Head of Data at a scaling company who is about to put an AI analyst on their
data, or already has and does not trust the numbers. The decision they are making:

> **"Can I let an agent answer questions off my analytics, and trust the answer the way I trust my
> senior analyst?"**

The wedge (from the practice thesis): a number can be perfectly fine for a human and wrong for an
agent, because the human asks "gross or net?" and the agent picks silently. Experiment 05 has to make
that real and show we can catch it before it bites.

## 2. The buyer's real questions

Everything 05 measures should answer one of these. If a measurement answers none of them, it is
apparatus, not evidence.

| # | The question the buyer actually asks | Their fear |
|---|---|---|
| Q1 | Does it catch the confusions that would silently produce a wrong number? | false confidence |
| Q2 | Will it bury me in false alarms? | alert fatigue, tool ignored |
| Q3 | Does it work on **my** stack, not a toy? | demo-ware that breaks on real data |
| Q4 | How is this better than what I already have (a smart human, or "just ask GPT")? | paying for nothing |
| Q5 | Would an actual expert agree these are dangerous? | a machine crying wolf |
| Q6 | What does it **miss**? Where's the edge? | unknown blind spots |
| Q7 | What do I **do** with it — is it a report or a guardrail? | shelfware |

## 3. The claim under test (narrowed, honest)

> The dangerous, numerically-silent **ambiguities** in a governed analytics stack — the same measure
> under two scopes, one concept over two columns, one term defined two ways across layers — are
> computable **offline from the artifacts**, across domains and dialects, with high recall and
> tolerable noise, and an experienced practitioner agrees with the dangerous calls. This is the
> **selection** half of grounding safety; construction defects (grain, additivity, keys) are a
> separate family (see `PRIMITIVE-VALIDATORS.md`) and out of scope here.

State the narrowing up front. Credibility is bought with the boundary, not spent on it.

## 4. What to CHECK — measurements mapped to the questions

| Q | Measure | Metric | Presented as |
|---|---|---|---|
| Q1 | recall on **high-danger** collisions in blind realistic environments | recall % (high) | scorecard row |
| Q2 | share of findings that are real (not noise) | precision % | scorecard row |
| Q3 | generalization: 2 domains (sales, retail), 3+ dialects (dbt/MetricFlow/Cube), partial layouts (semantic-only, warehouse+docs) — **zero per-domain tuning** | pass/fail + the recall/precision holding across them | scorecard: "cross-domain, zero tuning" |
| Q4 | contrast: with vs without a semantic layer; the tool vs a lexical baseline vs a single-LLM gold | Δ recall / Δ precision | contrast table |
| Q5 | agreement with a human red-team + practitioner-adjudicated gold | expert-agreement %, honestly split by lane | the two-mode reframe (in-lane ~5/8, naïve 5/22) |
| Q6 | the boundary: Mode-1 (ambiguity) vs Mode-2 (construction); what falls outside | qualitative + the 22-collision family breakdown | boundary statement + map |
| Q7 | the guardrail actually blocks a bad change | a demo: a PR adds an ambiguous metric → CI fails | a screenshot / run link |

The **headline number** we want to be able to say in one sentence: *"On blind, realistic
environments across two domains and three dialects, with zero tuning, preflight catches ~X% of the
dangerous ambiguities at ~Y% precision, and a practitioner agrees with the in-lane calls."* Fill X/Y
from the frozen scored runs (sales 16/16 high recall, 93% precision; retail 95% recall, 87%; human
gold in-lane ~5/8).

## 5. What to PRESENT — the deliverables

One headline artifact plus supporting evidence. All customer-facing.

1. **The scorecard** (the 60-second read). A single page: the claim, the recall/precision/expert-
   agreement numbers across the environments, "cross-domain, zero tuning," and the boundary line.
   This is the thing a prospect skims and a blog post is built around.
2. **Example findings — real, visceral, from the blind envs.** The gross-vs-net revenue fork, the
   `value_moments`/`real_value_moments` scope trap, `status='settled'` matching zero rows. Concrete
   collisions a reader feels. Pulled from `env_sales`/`env_retail` findings, not invented.
3. **The contrast.** With vs without a semantic layer (governance is what makes the fork resolvable),
   and the tool vs the naive baselines. Answers Q4.
4. **The boundary — the two-mode map.** Ambiguity is one of two ways a number goes silently wrong;
   the honest human-gold reframe (23% naïve → the tool is the Mode-1 half). Answers Q5/Q6 and is the
   most trust-building beat.
5. **The guardrail demo.** A short narrative: introduce an ambiguous metric in a PR, preflight blocks
   it. Turns "a study" into "a product you run today" (the GitHub Action / pre-commit we just added).

## 6. Setup + circularity discipline

The result is only worth presenting if it cannot be gamed. Keep the discipline that already produced
the current numbers:

- **Blind generation.** Environments are generated without the detector in the loop; ground truth is
  labelled blind; the detector is frozen before scoring. (Done for sales + retail.)
- **Human gold, adjudicated.** 3 independent red-team judges + practitioner rulings, clustered on
  real entity labels. (Done for retail; consider a second-domain human pass.)
- **Report the misses.** The scorecard names what both the detector and the LLM gold missed, not just
  the hits.
- **Real-shaped inputs, not just synthetic** (candidate addition — see §8): run on a public
  semantic-layer repo (e.g. a MetricFlow / dbt example project) so Q3 is answered on something the
  buyer recognizes, not only on our own fixtures.

## 7. What exists vs what 05 must add

Reuse (already done): T1 frozen-prediction, T2 corpus, T3 SQL recovery, T4 real-warehouse divergence,
T5 dialect portability; `env_sales`, `env_retail` with blind ground truth; the human-gold scorecard;
the no-SL contrast; `SUMMARY.md`; `PRIMITIVE-VALIDATORS.md`.

Add / assemble:
- `experiments/05_ambiguity/` with `experiment.yml` (title, question, `runs: code`, `article.repo:
  decisionspine-site`, evidence pointers) + `FINDINGS.md` = the scorecard, in customer terms.
- The **scorecard artifact** itself (the one-page present), derived from the frozen scored runs.
- The **guardrail demo** (PR-blocked narrative / CI run).
- **Candidate: a public-repo run** for external credibility (decision below).
- **Candidate: a second-domain human pass** (retail is human-audited; sales is single-LLM gold).

## 8. Open decisions before we build (for Dmitry)

1. **Public-repo run?** Worth the effort to run preflight on a well-known open dbt/MetricFlow example
   and show the findings — much stronger Q3 answer — or keep to our blind synthetic envs for control?
2. **Headline metric framing.** Lead with the flattering blind-env numbers (sales/retail recall), the
   honest human-gold numbers (in-lane ~5/8), or both side by side? (Recommendation: both — the honest
   pairing is more persuasive than either alone.)
3. **Second-domain human gold?** Add a human pass on sales, or is one adjudicated domain (retail)
   enough to support the expert-agreement claim?
4. **Scope of the guardrail demo.** A real PR on a sample repo, or a scripted before/after in the doc?
5. **Where the scorecard lives** — inside `FINDINGS.md`, or a separate one-pager the article and the
   site can both reuse?

## 9. Scouting results (Aug 2026) — public repos DO have flaggable ambiguity

Three parallel scouts (GitLab dbt; the dbt directory; Cube + LookML). Verdict: the premise "public
repos are all done right" holds **only for tutorial / vendor-skeleton demos** (jaffle-shop, bq_thelook,
GA4 demo). Real hand-written business/finance semantic models are messy in exactly the ways preflight
targets. The scarce ingredient is a *machine-readable definition surface* — where it exists (Cube,
LookML), ambiguity is easy to find and directly ingestible.

Ranked by how well each demonstrates the **tool running end-to-end** (structural detection on
directly-parseable files):

1. **Cube + LookML — best live-tool demo.** Measures are structured (agg + sql-column + filters),
   mapping ~1:1 onto preflight facets, so the *structural* detection (SCOPE_TRAP / CONCEPT_FORK /
   GRAIN_MISMATCH) fires directly. Verified real files:
   - Cube `cube-js/stripe-schema`: `StripeCharges.js` (`totalGrossAmount` vs `totalFailedAmount` =
     sum(amount) filtered to a subset; gross vs `totalNetRevenue`), `StripeSaaSMetrics.js` (`mrr` vs
     `mrrChange` vs `mrr30daysAgo` — identical `sql: mrr, type: sum`, differ only by `rollingWindow`).
   - LookML `rittmananalytics/ra_data_warehouse_lookml`: P&L (`amount` vs category-subset `revenue`),
     timesheets (hours vs billable subset), forecast (raw vs probability-weighted).
   - LookML `mozilla/looker-spoke-default`: DAU (`sum(dau)` vs `sum(ma_28_dau)`; summed distinct-count
     grain hazard).
   Adapter effort: **LookML is cheapest via the `lkml` PyPI parser**; Cube-YAML is easy, Cube-JS harder
   (JS objects). Building these doubles as dialect support (Q3) and closes T5's LookML residual.

2. **GitLab `gitlab-data/analytics` — best narrative, NOT live-ingestible.** Verified from GitLab's
   public handbook (the repo itself is now Cloudflare-gated; no MetricFlow YAML): three colliding "ARR"
   fields — **Net ARR / ARR Basis / Booked ARR**, where the field literally named `ARR__c` is the
   *deal total*, not run-rate ARR — plus ARR = MRR×12, the MQL family (MQL vs first-order subset;
   FO-initial vs FO-latest as-of divergence), and "Inquiry" defined several ways. Use as the "this
   happens even at a top-tier, well-governed shop" story + screenshot, not a live scan.

3. **SOMA (`Levers-Labs/SOMA-B2B-SaaS`)** — a governed 407-metric catalog: churned-customers two ways,
   active-users three grains, bookings subset + a unit bug, "Net" meaning four operations, a dangling
   reference. RICH *problem* proof, but a prose/formula catalog (no entity/agg/base/measure) → needs a
   naming/prose adapter and exercises the naming side more than the structural.

4. **Mattermost** (real production warehouse; DAU/MAU source+window collisions; weak surface = column
   docs) and **Dagster Open Platform** (a real MetricFlow-style semantic YAML with AI synonyms; thin) —
   supporting breadth.

**Resolves open decision #1: yes — run on a public repo.** Build a LookML (via `lkml`) and/or Cube
adapter and scan the real files above; lead the narrative with GitLab's ARR family. The scored
recall/precision claim still stays on the blind synthetic envs — there is no ground truth on public
repos, so a public run is *qualitative/recognizable* evidence, not a scored number.

### 9a. dbt MetricFlow deep-scout (two more scouts) — verified

Adoption read (honest): **real open-source MetricFlow is THIN.** MetricFlow was only open-sourced
(Apache-2.0) at Coalesce Oct 2025; before that dbt Cloud gated the serving layer, so production metric
definitions are overwhelmingly *private*. GitHub topics: `metricflow` ≈25 repos (mostly tooling),
`dbt-semantic-layer` = 0, `dbt-metrics` = 2 tools. The public corpus is individual portfolio / bootcamp
/ POC repos, not enterprise. The old dbt `calculation_method` metrics spec is dead (deprecated 2023) —
skip it. So the ecosystem is heavily used, but mostly where we can't see it.

But the format is highly ingestible (consistent `semantic_models:`→`measures:`; `metrics:` with
`type:`/`type_params:`/`filter:`), and **every preflight type fires on real hand-authored files** —
several unintentionally. Verified RICH targets (clones under `scratchpad/mf_scout_{a,b}/`):

- **`eduardocornelsen/full-funnel-ai-analytics`** (20★, active) — the best. Marketing MDS + MetricFlow
  + MCP. Verified: metric `total_clicks` (label "Total Ad Clicks") → measure `total_ad_conversions`
  (name↔measure mismatch); `total_sessions` bound to two different columns; three near-synonym
  "conversions" measures with the "canonical" one orphaned; `blended_roas` **description says
  "paid-channel orders only" but the definition uses all-orders `revenue`** (stated population ≠
  actual). The author writes warnings in descriptions — a human doing preflight's job by hand.
- **`ken-nagata/dbt-olist-metrics`** — verified degenerate ratios: `conversion_rate` AND
  `late_delivery_rate` are both `order_count / order_count` ≡ **always 100%**, while their descriptions
  promise "% delivered" / "% late". Plus `gmv` silently includes canceled orders.
- **`dioz95/marketing-analytics-engineering`** (8★) — `marketing_budget_revenue_ratio` = budget
  (`fct_marketing_campaign`) / revenue (`fct_transactions`): numerator/denominator from unrelated fact
  tables at different grains. Plus count_distinct measures exposed as additive `simple` metrics.
- MODERATE: `TechPopsicles/dbt-mesh-platform` (gross vs net revenue CONCEPT_FORK, author's defensive
  "THE authoritative revenue" wording); `KushPatel29/supply-chain-analytics-dbt` (order_count at line
  grain). CLEAN-but-thematic: `ro-kannan/dbt-metricflow-pharma-analytics-governance` ("5 teams, 5 net
  revenue numbers" — the prevention side). Template (confirms the constructs, doesn't count):
  dbt-labs jaffle-shop-metricflow (the canonical filter-based SCOPE_TRAP).

**Two strong signals for the product thesis:**
1. Authors repeatedly write **descriptions that contradict their own definitions** (blended_roas, the
   olist ratios) and hand-warn against confusions — the clearest evidence the problem is real and
   currently unaddressed. Suggests a distinct high-value check: compare *stated intent* (description)
   to *actual population* (definition).
2. The **degenerate ratio** (`numerator == denominator`) fired on a real repo — a trivial, high-value
   ratio-consistency check (Mode-2, per `PRIMITIVE-VALIDATORS.md`).

**Caveats for the build:** the public corpus is small (portfolio repos, not production scale), so the
MetricFlow eval corpus is limited; and much real semantic YAML is *not* MetricFlow (SDF at Dagster,
Cube, LookML) — a MetricFlow-only adapter is a genuine but narrow band, though the ambiguity classes
generalize across formats.

**Build decision:** build the **dbt-MetricFlow adapter** (cheap, consistent YAML, our ICP's growing
standard) and demo on `full-funnel` + `olist`; the one wrinkle is parsing MetricFlow's Jinja filter
syntax (`{{ Dimension('order__status') }} = 'completed'`) into scope predicates. Cube is the natural
second dialect. LookML remains a fast follow (see §on-proprietary-formats in the LookML discussion).

### 9b. MetricFlow adapter — BUILT, and the honest live result

The MetricFlow adapter shipped (`preflight/src/preflight/metricflow.py`, `--dialect metricflow`, 62
tests). Live results on the two real repos:
- **`full-funnel-ai-analytics`** — real catch: the **`total_sessions` NAME_COLLISION** (one name bound
  to two different measures — the exact trap the author hand-warned about) + conversions/sessions
  concept forks. One lexical-gate false positive (`channel_orders ~ channel_spend`) the embedding gate
  would likely filter.
- **`olist`** — **0 findings, and that is correct.** The adapter resolves `conversion_rate` and
  `late_delivery_rate` to *identical* definitions (`order_count/order_count`), but their names are
  dissimilar (sim 0.36), so the confusability gate rightly skips them — they are not an ambiguity/
  selection problem. Their real defect (a degenerate ratio, always 100%) is a **construction** defect
  (Mode 2, ratio-consistency), outside preflight's Mode-1 scope. A clean live demonstration of the
  two-mode boundary on real public data.

### 9c. Big real *raw-dbt* (no MetricFlow) scout — Mattermost is the showcase

Honest generalization first: big public raw-dbt projects that are *both* real-company-scale *and*
metric-mart-heavy are **rare**. Most large ones are staging+intermediate+docs (preflight's weak case)
or crypto/open-data (Dune Spellbook, Flipside); curated metric repos (SOMA's `generate_metrics_cube`)
are documented and non-ambiguous by design (a useful CLEAN contrast). The standout is:

- **`mattermost/mattermost-data-warehouse`** — RICH. 489 models, real SaaS, cloneable, no semantic
  layer; genuine ambiguity across sibling `SUM(...)+WHERE` marts (verified, verbatim):
  - `arr_reporting` vs `contracted_arr_reporting`: same base (`arr_transactions`), same
    `sum(opportunity_arr)`, different date anchor (`report_mo` vs `closing_mo`) → DEFINITION_DIVERGENCE
    /SCOPE_TRAP. The maintainers' own schema.yml documents the difference.
  - `total_arr` computed two ways: `account_daily_arr` (`sum(won_arr)`) vs `account_arr_and_seats`
    (day-prorated `totalprice/term`, active-today only) — same name, account grain, won't reconcile.
  - DAU/MAU client-telemetry vs server-reported, 30- vs 31-day windows → CONCEPT_FORK.

**Ingestion cost:** these are dbt model `.sql` files (Jinja `{{ ref() }}`, CTEs), not our welded-query
`-- name:` format — so demoing on Mattermost needs a **dbt raw-SQL adapter**: de-Jinja + reuse the T3
sqlglot scope-recovery (agg/base/scope from the SELECT), filename as the metric name. More involved
than MetricFlow (CTE-aware recovery), but it's the "works even without a governed semantic layer"
story — the most common customer reality. Next build if we want the Mattermost ARR demo live.

Clones under `scratchpad/{mf_scout_a,mf_scout_b,dbt_raw_scout}/`. Cal-ITP / CalData are untested large
public projects worth a second pass if more raw-dbt RICH examples are needed.

### 9d. dbt raw-SQL adapter — BUILT, and the honest precision characteristic

Shipped `preflight/src/preflight/dbt_sql.py` (`--dialect dbt`, 5 tests). It de-templates dbt Jinja
(`ref`/`source`/`config`/macros), parses each model with sqlglot, and recovers one fact per
aggregated output column via CTE-aware `traverse_scope` — restricted to **measure aggregations
(sum/count/count_distinct)**; MIN/MAX dimension grabs are excluded (they flooded the output with
false collisions between date/dimension columns sharing a name-stem).

Recovery on the real Mattermost ARR marts is exact: `sum(opportunity_arr) as arr` on `arr_transactions`
filtered by `report_mo` (vs `carr` filtered by `closing_mo`); the two `total_arr` definitions
(`sum(won_arr)` vs a day-prorated `totalprice/term`). **`total_arr` fires as a NAME_COLLISION** — one
name, two incompatible definitions across models — the sharp, real catch.

Honest precision note: at directory scale (`finance/`, 19 models → 78 measure facts) raw dbt is
**noisier** than a governed layer — the precise catches are the *exact-name cross-model collisions*
(`total_arr`, `arr`, `won_arr`, `lost_arr` each defined in several models), but CONCEPT_FORK
over-fires on families of related ARR columns that share a base and name-stem (arr / arr_delta /
arr_renewed; the churn/contraction/expansion family). That noise is the honest cost of no governance —
and is itself the argument for a semantic layer (governed input → precise output). For a demo, lead
with the exact-name NAME_COLLISION findings (the `total_arr` two-ways case). Tightening CONCEPT_FORK
on raw dbt (e.g. cross-model only, or a stricter gate) is future tuning, not done here.

### 9e. Cube adapter — BUILT (YAML + JavaScript)

Shipped `preflight/src/preflight/cube.py` (`--dialect cube`, 6 tests). Handles both Cube formats:
YAML (`cubes:`) via pyyaml, and JavaScript (`cube(...)`) via a brace-matching scanner that respects
backtick template strings and skips nested blocks (rollingWindow/format). Cube measures map cleanly:
`type`→agg, `sql: ${col}`→measure, `filters: [{sql}]`→scope.

Live on the real `cube-js/stripe-schema` (`StripeCharges.js`) — the cleanest single-file demo yet, 2
high findings and no noise:
- **SCOPE_TRAP**: `totalFailedAmount` = `sum(amount) WHERE status='failed'` is `totalGrossAmount` =
  `sum(amount)` plus a filter — a "total revenue" answer silently includes failed charges.
- **CONCEPT_FORK**: `totalGrossAmount`(amount) vs `totalRefundedAmount`(amountRefunded).

**Four dialects now ship: `env` / `metricflow` / `dbt` / `cube`.** The core detector was never touched
— each dialect is just an adapter (the format-agnostic design paying off). LookML is the remaining
fast-follow (via `lkml`). Verified live catches on real public repos across metricflow, dbt, and cube.

Demo shortlist by cleanliness: **Cube Stripe (SCOPE_TRAP, one file)** and MetricFlow full-funnel
(name collision) are the crispest governed-layer demos; Mattermost raw-dbt `total_arr` is the
"works without governance" demo (noisier — the point being that governance buys precision).
