# Static ambiguity / collision detection — investigation summary

Scope of this document: the whole investigation, not only the five viability tests it began with.
Tests 1 and 2 were run first and validated the core, so the work pivoted to building and evaluating a
real cross-layer collision detector on two blind, realistic environments — then circled back to close
the remaining original tests. All five are now covered: **T1, T2, T4 fully; T3 closed with a proper
scope-resolving parser; T5 for MetricFlow + Cube** (LookML, proprietary, is the lone residual). Numbers
are reported as they came out, with n, including the nulls.

All artifacts and code live under `harness/scratchpad/ambiguity/`. Nothing here touched `engine/`.

---

## Verdict

**Proceed, with a narrowed claim.** The exact qualification the claim now needs:

> The dangerous, numerically-silent confusions in an analytics stack — where a bare question resolves
> to two governed definitions whose numbers land close enough to pass every check — are computable
> offline from the declared artifacts, across the whole grounding surface (warehouse + docs + semantic
> layer), and the method generalises across domains. Two conditions bound it:
>
> 1. **It needs a definition surface.** A governed semantic layer, or at least saved queries a parser
>    can read. Bare schema + docs cannot surface metric-level ambiguity, and an agent grounding on
>    schema + docs alone welds its own scope invisibly (config C below: 0 catchable).
> 2. **It detects name-and-definition collisions between grounding facts.** It does not check the
>    values/enums inside a column, single-fact correctness, or (yet) warehouse near-synonym columns.
>    Those are real and need complementary checks.

And one repositioning, from the no-semantic-layer contrast: the semantic layer's value is **governance**
— one authoritative surface on which to resolve the forks — not merely making ambiguity visible to a
parser. Welded SQL is visible to a parser too; it is the *governed answer* that a no-SL shop lacks.

---

## The three headline numbers (the reference pair)

For `value_moments` vs `real_value_moments` in the harness's own layer:

| number | value | source |
|---|---|---|
| static classification | `scope_only` / **high** (same measure, differs only in segment + `default_filters`) | `engine/src/semantic/ambiguity.py` |
| divergence when swapped | **0.6%–5.9% across 14 slices, ~4.3% overall** (measured by executing both groundings); never exactly zero, sign always the same direction | Test 4 (real warehouse execution) |
| share of observed mislabels | the four predicted-clarify cases hold **48%** of answerable mislabels (99.5th pct of a per-case shuffle null); the module claims 59% of *all* mislabels are this pair | Test 1 regrade |

The divergence is a **range, not a constant** (Test 4): the damage number moves from 0.6% (the most
dangerous slice — invisible) to 5.9% (comparatively safe — someone notices), so "costs ~4%" is a fair
headline and a false constant, and must be stated with its slices.

---

## Phase-by-phase results

| phase | question | result | verdict |
|---|---|---|---|
| **T1** frozen regrade | is the static prediction predictive, not post-hoc? | clarify wrong-rate 29.8% vs answer 5.8%, shuffle p=0.038; lexical baseline p=0.149 (n.s.) | **met**, narrowed |
| **T2** corpus | property of semantic layers, or of *this* one? | scope separable in 3 real dialects; native scope_only 0/3 projects, unit-inferred 12 | **met in principle**, code fix required |
| **Embeddings** | do embeddings beat the token gate? | reference pair #1 of 136 (MiniLM 0.904, OpenAI 0.816, cross-model ρ=0.71) | gate: **yes**; danger signal: **no** |
| **Pipeline** | does the combined design work? | 5/5 isolated examples correct; real layer: 1 scope trap (= the collision), 8 recall-win pairs all safe | **works** |
| **Sales env** | on a realistic blind 3-layer environment? | 454 facts; recall 16/16 high, 56/61 (92%); precision 61/69 (88%) | **strong** |
| **No-SL contrast** | does removing the semantic layer hide it? | welded scope recoverable (agg 41/41, base 41/41, WHERE 34/41); bare config catches 0 metric-level | governance, not detectability |
| **Retail** | does it generalise to a second domain? | 525 facts; recall 18/19 high (95%), 61/79 (77%); precision 56/67 (84%) | core **generalises** |
| **Expert review + v3** | does it survive a board critique? | 8 findings from data-modelling / semantic / analytics-engineering addressed; `GRAIN_MISMATCH` validated | **hardened** |
| **T4** divergence | is the ~4% damage number stable? | binary detection = YES; magnitude **0.6–5.9%** across 14 slices (a range, not a constant); sign consistent | **done** |
| **T3** SQL recovery | can primitives be read back from emitted SQL? | 97%+ governed calls are declared; raw SQL (rung-dependent, up to 21% at R0): entity **92%** via scope resolver, scope **81%** incl. welded, false-recovery ~0 | **closed** |
| **T5** dialects | does the meaning/scope split port? | MetricFlow + Cube: scope separable AND idiomatic → kill condition not met; LookML untested | **MetricFlow + Cube** |

(Sales/retail figures are the v3 detector; the v2 figures that first scored the environments — sales 57 findings / 93% precision, retail 61 / 87% — are in the phase notes and git history. The original five viability tests are now all covered: T1/T2/T4 fully, T3 closed with a proper scope-resolving parser, T5 for the open dialects.)

### T1 — frozen-prediction regrade
Prediction committed before any run was read (freeze at commit `94e9cac`). Regraded run
`20260726-224953-gpt-5-mini` (the doc's `20260810-181508` does not exist). The four `scope_only`-
predicted cases were wrong 29.8% of the time vs 5.8% on predicted-answer cases; the concentration
survives a 1,000× per-case label shuffle (p=0.038 on the gap, 99.5th pct on mislabel share). A
lexical name-overlap baseline does **not** reproduce it (p=0.149) — so the kill condition is **not**
met; the structural stage earns its place. Mechanism inspection of the actual answers: `t2_web` (6.0%
off) and `t2_americas` (4.7% off) are genuine scope swaps (agent applied the non-internal filter);
`t4_apac` (+13%, correct metric) is the APAC coverage-window trap, not a scope swap; `t2_referral`
(55.6% wrong) is a genuine scope swap the classifier **cannot** see, because no `real_new_signups`
metric exists to pair against — the welded-scope blind spot. Strict grader-escaped silent errors: **0**
(every wrong number was caught by the gold-based grade; the "silence" is relative to a downstream
consumer without that gold).

### T2 — corpus smoke test (n = 3 public MetricFlow/dbt projects)
Every dialect declares scope as a first-class field (`filter:` / `filters:`), so the pessimistic kill
condition (scope not separable) is **not** met. But the classifier found **0** `scope_only` pairs
natively across all projects, and **12** once `unit` was inferred — because `ambiguity.py:113` requires
all four meaning facets present, including `unit`, which no MetricFlow/dbt dialect declares. Hand-
inspection: on jaffle-shop the gate over-generated (4 of 10 order-family pairs genuine, the rest sibling
noise). Gate scaling was inconclusive (n = 4, 11, 17 — public MetricFlow projects are all small).

### Embeddings (local MiniLM, validated against OpenAI)
The reference pair is the #1 closest pair by name in both models; the two rank all 136 pairs the same
(Spearman 0.71). Embeddings out-recall the token gate (they catch `reminder_open_rate ~
reminders_shown`, which a plural defeats). But cosine ranks *similarity*, not *danger* — the safe
`different_measure` pairs cluster right below the dangerous one, and nearest-neighbour cosine does
**not** predict mislabel rate (Spearman 0.42, n.s.; −0.53 with descriptions). Conclusion: embeddings
replace the confusability **gate**; the structural test stays for **danger**; embed names, not
descriptions.

### Combined pipeline
`gate (embedding) → same-measure (declared facets, unit dropped) → scope subsumption`. On five isolated
examples each path fired correctly, including the sibling-noise case (`food_orders ~ drink_orders`
downgraded to non-danger) and the recall win (`revenue ~ net_sales`, no shared token, caught). On the
real 17-metric layer it flagged exactly one scope trap — the known collision, which carried the highest
mislabel rate — and marked all 8 embedding-recall additions safe.

### Sales environment (blind, three layers)
`Northwind Threads`, a DTC apparel + subscription company. Three generators built the warehouse (25
tables), docs (52 entries) and semantic layer (39 metrics) blind to the detector; a separate agent
labelled 61 ground-truth collisions blind; the detector was frozen before scoring. First scored (v2,
clustered): **16/16 high-danger recall, 90% total, 93% precision**, 57 findings. The false positives
exposed a real bug (same-measure passed on a single shared facet) — reported, then fixed by requiring
≥2 shared facets. Four gold misses, each an explainable gap (British/US spelling, a within-fact
filter/description mismatch, a stoplisted `email`, a threshold). After the v3 hardening below:
**16/16 high, 92% total, 88% precision**, 69 findings — the `email` rename is now caught (role-based
stoplist) and warehouse near-synonyms are added, at a small precision cost from low-danger additions.

### No-semantic-layer contrast (same company, three configs)
41 saved BI queries with scope welded into `WHERE` stood in for the governed layer. sqlglot recovered
agg 41/41, table 41/41, and WHERE-scope 34/41 — **welded scope is recoverable from real query SQL.**
Detector on three configs: bare warehouse+docs catches **0** metric-level collisions; +semantic layer
catches 43 (incl. 2 scope traps, 3 concept forks); +welded queries catches 22 (incl. 4 scope traps,
4 concept forks — the concept forks appear once v3 derives `entity` from the query's base table).
Two readings: (1) you
need *some* definition surface — schema+docs alone is blind to metric-level ambiguity; (2) welding does
not hide scope from a parser, but it hides it from the **agent**, whose seat is config C — it grounds on
schema+docs and welds its own unreviewed scope, which is the T1 finding at environment scale. The
semantic layer's contribution is a single authoritative surface, not detectability per se.

### Retail (cross-domain generalisation)
`Harborstone Market`, an omnichannel grocery + general-merchandise retailer — deliberately far from DTC
apparel. Same frozen detector, no tuning. Blind gold: 79 findings. v3 result: **high-danger recall 95%
(18/19), precision 84%**, total recall 77% (61/79). Domain-appropriate high findings (the comp/same-
store sales family, `inventory_on_hand ~ inventory_available`, margin on different costs). The lower
*total* recall is scope, not domain failure: retail's gold has more findings in categories the detector
does not cover (column value/enum issues, within-fact flaws), and the same boundary exists in sales. A
detector overfit to sales would fail unpredictably on retail; this one fails only in the categories it
does not claim, consistently — evidence it is well-defined.

### Expert review and v3 hardening
A board pass (data-modelling, semantic-modelling, analytics-engineering) put the algorithm under
domain critique. All three independently hit the same top defect — **grain was dropped** — and eight
findings were addressed in `detect.py` / `grounding.py` v3:

| fix | what changed |
|---|---|
| **grain** carried into the representation | `DUPLICATE` now requires equal grain; new `GRAIN_MISMATCH`, graded by additivity (semi-/non-additive rollup → high; additive → medium). Validated in `grain_test.py` (the DAU→MAU trap scores high). |
| **scope compared by meaning, not string** | filters parsed with sqlglot into per-column value-sets; `segment:` resolved to its filter; booleans/3-valued logic normalised (`= false` / `not x` / `is not true` / `= 0` collapse). `status ∈ {completed} ⊆ {completed,fulfilled,delivered}` now recognised. |
| **`entity` derived from base table** | concept-forks now fire on warehouse views and welded queries (no-SL config: 0 → 4). |
| **additivity derived from `agg`** | count_distinct/stock → semi, ratio/avg → non — a rule, not a per-metric flag. |
| **warehouse near-synonym columns** | embed-compared (`discount ~ total_discounts`, `is_test ~ test`, `qty_on_hand ~ qty`). |
| **stoplist by role, not name** | surrogate keys / timestamps / technical dropped by pattern; `email` re-enabled (its rename is now caught). |
| **`DUPLICATE` demoted** | a governance smell, below the fold. |
| **output states its boundary** | flags disagreement, not correctness; no value/enum, single-fact, or join-trap checks. |

The score barely moved (these are correctness fixes; the environments have no grain-only pairs to
exercise `GRAIN_MISMATCH`), but populations now compare by meaning and forks are catchable in welded
SQL — the substance the board asked for. The one issue **deferred**: fan/chasm-trap detection, which is
a join-path analysis and its own detector.

### T4 — divergence calibration (real warehouse execution)
Built the harness warehouse and executed both candidate groundings (`value_moments` = all;
`real_value_moments` = `NOT is_internal`) across 14 slices (all rows, each region / platform / channel,
a recent window). No model, no tokens. **Detection is binary** and came back **AMBIGUOUS** — the two
differ on 14/14 slices, so they are two definitions, not one. The three numbers: never exactly zero (not
an alias); sign consistent (`value ≥ real` on every slice, as subsumption requires); magnitude **0.6%–
5.9%, ~4.3% overall**. So the damage number is a range, and it runs inverse to danger — `platform=unknown`
at 0.61% is the most dangerous (invisible swap), `paid_search`/`web` at ~5.9% are comparatively loud.
This confirms the design decision: divergence is one bit for *detection*, and the ~4% is only the *price*.

### T3 — primitive recovery from the agent's actual emitted SQL
Pooled all four published runs. Raw-SQL usage is **rung-dependent**: at the raw-warehouse rungs the agent
has no governed metrics and writes SQL constantly (R0 21%, R1 16%, R2 18%, R3 9%); at governed rungs it
calls named metrics (R4–R9 ~0–2%), where the grounding is **declared** and needs no parse. On the 265
pooled raw statements (98% parse), a naive parser reads a misleading 100% entity with a **34% false-
recovery rate** (CTE aliases reported as source tables) and 80% WHERE-only scope. The **proper parser**
— entity via sqlglot's scope resolver (`sqlglot.optimizer.scope`), scope read from `WHERE` *and* from
welded `CASE` conditions inside aggregates — recovers **entity 92%** (false-recovery ~0), **scope 81%**
(incl. the 20% welded that a WHERE reader loses), measure 89%. Governed compiler SQL parses 4263/4263
clean. The methodological lesson: the naive 100%/80% hid a 34% confident mislabel and a 20% blind spot,
and measuring the false-recovery rate is what exposed both and pointed at the fix.

### T5 — dialect portability (MetricFlow + Cube; LookML skipped as proprietary)
Hand-translated the three reference metrics into MetricFlow and Cube. Scope is a first-class, separable
construct in both — MetricFlow's metric `filter:`, Cube's `segments` + measure `filters:` — and
separation is **idiomatic** (the T2 corpus uses `filter:` 7× and welds population scope into `CASE`
essentially never in the modern spec). Even `power_users` needs no `CASE`. So the kill condition —
welding idiomatic on a platform → the dangerous class downgrades — is **not met** for MetricFlow or Cube,
and the claim needs no heavy platform conditional there. The residual risk is teams welding **by choice**
(this repo's `power_users`; the no-SL team; some generated metrics) — a discipline issue the v3 detector
now handles by parsing SQL. LookML is the one untested conditional (its inline `sql:` makes welding easy).

---

## What broke, with the code path

| finding | where | action |
|---|---|---|
| `scope_only` needs all 4 meaning facets, incl. `unit` which no real dialect declares | `engine/src/semantic/ambiguity.py:113` | reported, not edited (ground rule 1); fix = compare only co-declared meaning facets |
| `unit` is redundant with `agg` (0/9 gated pairs distinguished by it; dropping it changes 0 classifications) | `_MEANING` in `ambiguity.py` | drop `unit` from the meaning set |
| same-measure passed on a single shared facet (`order_count ~ order_date` DUPLICATE) | `detect.py` v1 | fixed in v2: require ≥2 shared facets |
| cross-layer divergence asserted on any name match | `detect.py` v1 (CROSS_REF) | fixed in v2: assert only with evidence (two prose defs, or doc omits the modelled columns) |
| grain dropped; scope compared as raw SQL string; `entity` not recovered from SQL | `detect.py` / `grounding.py` v2 | fixed in v3 (see the expert-review table above) |

---

## The detector's boundary (consistent across both domains)

It does **not** handle, and these are where recall is lost:

1. **Column value / enum issues** — a magic store code, a `char` flag that should be boolean, drifting
   category strings, a status value that is used but never declared. The detector compares names and
   facets, not the values inside columns. (A complementary value-level check.)
2. **Single-fact correctness** — a metric that references a nonexistent column, a segment whose filter
   contradicts its own description, a rate capped by a data artefact. Not a pair, so not a collision.
3. **Join-path (fan / chasm) traps** — a one-to-many join upstream of an aggregate inflates a plausible
   number; the detector reads definitions, not join paths. The board's flagged category, and its own
   detector. **This is now the largest uncovered silent-error family.**
4. **Spelling / locale variance** — `recognised` vs `recognized` defeats exact-label matching.

Partly closed in v3: warehouse near-synonym columns (now embed-compared) and `entity` recovery
(derived from the base table).

---

## What the next experiment should be (chosen from what actually failed)

The original five viability tests are now covered (T4 executed, T3 closed with a scope-resolving parser,
T5 done for MetricFlow + Cube). What remains, in priority order:

1. **Fan/chasm-trap detection** — the largest uncovered silent-error family; a join-path analysis that
   pairs naturally with this detector (both catch plausible-wrong-number defects).
2. **A complementary value/enum check** — a different tool for the largest out-of-scope category,
   especially in value-heavy domains like retail.
3. **A human-audited gold** — take the retail environment and have an analytics engineer label collisions
   independently, then re-score; converts "two LLMs agreed" into "a human confirmed" (the cofounder's
   cheapest objection-killer).
4. **T5's LookML half** — grep public LookML for `filters:` vs inline `CASE WHEN`, the one dialect where
   welding might be idiomatic enough to silently downgrade the dangerous class (skipped so far as
   proprietary; the finding would only *narrow* the claim, not overturn it).

---

## Methodology and its caveats

- **Circularity discipline held throughout.** Environments were generated blind to the detector; ground
  truth was labelled by a separate agent, also blind; detectors were frozen before scoring; and the
  misses were reported, not hidden.
- **The environments and gold are LLM-generated**, so the messiness is LLM-shaped, not human-shaped. This
  is the strongest threat to the environment results and should be stated in any write-up. A human-audited
  environment, or one mined from a real (anonymised) warehouse, would strengthen them.
- **The scorer matches by name-token overlap** (pairwise/clustered detector vs grouped prose gold), which
  flatters both precision and recall somewhat. High-danger matches were spot-checked as genuine; the
  medium/low numbers are softer.
- **One collision, dressed as many.** The harness's own layer has a single dangerous collision expressed
  as ~2 pairs, so T1's per-case statistics rest on a small n and lean on the *share of mislabels* rather
  than case counts.
