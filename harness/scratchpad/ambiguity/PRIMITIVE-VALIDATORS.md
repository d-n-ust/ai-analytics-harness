# Primitive validators — the Mode-2 construction-check family

Companion to `SUMMARY.md`. That doc lands the conclusion (two modes; the ambiguity checker is one of a
family). This doc is the **engineering spec** for the other half: the per-primitive validators the
human-gold audit mapped out. Each is a small, LLM-free `parse → look up one fact → apply one rule →
flag` loop.

---

## The two modes, stated mechanically

A silent wrong number comes from a defect in one of the query's **primitives** — entity, population,
measure, grain, additivity, join path, value domain, existence. There are exactly two mechanisms of
failure, and they need two different mechanisms to catch:

| | Mode 1 — SELECTION (ambiguity) | Mode 2 — CONSTRUCTION (primitive) |
|---|---|---|
| what's wrong | two **valid** definitions exist; the agent picked the wrong one | **one** definition/query; a primitive is used wrong |
| example | `gross_margin` (actual cost) vs `margin_standard` (standard cost) | `inventory_on_hand` summed across 30 days |
| catch mechanism | **compare** definitions — find confusable pairs that diverge | **validate** one thing against a rule |
| needs a second thing to compare? | yes (that's the whole trigger) | no — the metric is wrong on its own terms |
| tool built | the collision detector (`detect.py`) | this family (mostly to build) |

An ambiguity checker **structurally cannot see Mode 2**: there is no second definition to collide with.
`inventory_on_hand` summed over time is one metric used illegally — you catch it only by *knowing the
rule* (a stock can't be summed over time) and checking the query against it.

## Why the human gold scored the detector 23%

The panel flagged 22 **dangerous** collisions, not 22 **ambiguity** collisions. Re-tagged by primitive,
only ~8 are Mode 1 (comparison-catchable; the detector caught 5). The other ~14 are Mode 2 — each needs
its own validator below. `23% = (Mode-1 hits) / (Mode-1 + Mode-2 set)`. You do not fix it by improving
the ambiguity checker; you add validators.

---

## The family — overview

| validator | primitive | defect it catches | input it needs | cost | status |
|---|---|---|---|---|---|
| column-existence | existence | metric references a column the table lacks | definitions + schema | build-time, trivial | to build |
| value-domain | value domain | filter uses a value not in the column's set | filter values + enum/data | static or one `DISTINCT` | **partly built** (`value_check.py`) |
| additivity | additivity | a stock/distinct-count summed over time | agg + snapshot metadata | static | partly built (agg part in detector) |
| ratio-consistency | measure/population | a ratio mixes bases / populations | one metric's expression | static | to build |
| grain | grain | measured-column grain ≠ counting grain | metric grain metadata | static-ish | to build |
| join-cardinality | join path | one-to-many join upstream of a SUM (fan/chasm) | emitted query + keys | needs the query | to build |

Four of the six (existence, value-domain, additivity, ratio-consistency) are **pure static checks on the
definitions + schema you already have** — the cheap, high-leverage cluster to build first. Grain and
join-cardinality need the emitted query.

---

## Each validator — input · rule · worked example

### 1. Column-existence  *(existence · build-time · trivial)*
- **Input:** metric definitions + schema (`table → columns`).
- **Rule:** parse every column a metric references (measure / expr / filter) with sqlglot; fail the build
  if any is not in `schema[base_table].columns`.
- **Example:** `gross_sales = sum(gross_amt)` on `pos_transactions`. That table has
  `{total, net_sales, tax_amount, discount_amount, …}` — no `gross_amt`. → **FAIL: gross_sales references
  gross_amt, absent from pos_transactions.** (The detector already extracts these columns; this is a
  set-membership check on top.)

### 2. Value-domain  *(value domain · static-or-data · partly built)*
- **Input:** filter values (parsed predicates) + the column's allowed set — from the docs' declared enum
  (static) or `SELECT DISTINCT col` (data, also catches drift).
- **Rule:** for each `col IN (v1…)`, flag any `vi` not in `allowed_values(col)`.
- **Example:** `v_net_sales` filters `status = 'settled'`; the column's values are
  `{completed, voided, suspended, training}`. `'settled' ∉` → **FLAG: matches zero rows, returns
  near-zero silently.** (`value_check.py` does the declared-enum version today; the `DISTINCT` version
  would also catch the region 5→6 drift.)

### 3. Additivity  *(additivity · static · partly built)*
- **Input:** the agg + which columns are stocks (snapshot-table metadata).
- **Rule:** derive additivity from the agg — `count_distinct`/stock → semi-additive; `avg`/ratio →
  non-additive; `sum`/`count` → additive. Then forbid summing a semi-/non-additive measure across the
  dimension it is non-additive over (usually time).
- **Example:** `inventory_on_hand = sum(on_hand_qty)` off a daily snapshot table. A query that sums
  `on_hand_qty` across a month with no single-snapshot pick counts the same stock 30× → **FLAG the
  roll-up.** (`_additivity()` already exists in the detector; it needs to gate roll-ups, not just grade
  `GRAIN_MISMATCH`.)

### 4. Ratio-consistency  *(measure/population · static · to build)*
- **Input:** a ratio/derived metric's expression.
- **Rule:** split numerator and denominator; extract each side's `{population filter, grain, basis}`;
  flag if they disagree.
- **Example:** `gross_margin_pct = (sum(ext_ring_amt) − sum(landed_cost*quantity)) / sum(net_sales_amt)`.
  Numerator is a **gross**-ring margin; denominator is **net** sales. → **FLAG: gross numerator over net
  denominator.** Same rule catches a rate whose numerator is filtered to a segment the denominator is not.

### 5. Grain  *(grain · static-ish · to build)*
- **Input:** each metric's grain (its group-by + the measured column's grain).
- **Rule:** flag when (a) a ratio divides two measures at different grains, or (b) a question about one
  grain is answered by a metric at another.
- **Example:** "how many did we sell?" — `units_sold` sums line quantities (grain = line item);
  `transactions` counts baskets (grain = basket). A 5-item basket is 5 units but 1 transaction. Answering
  "units" with `transactions` is 5× off. → **FLAG: measured-column grain (line) ≠ counting grain
  (basket).**

### 6. Join-cardinality / fan-trap  *(join path · needs the query · to build)*
- **Input:** the emitted query's join graph + table keys/grain (PK/FK).
- **Rule:** walk the joins; for each `A ⋈ B`, use keys to decide if B is many-per-A; if a one-to-many
  join sits **upstream of a `SUM`** on A's measure, the measure fans out → flag. Two independent
  one-to-many paths from one table = chasm trap.
- **Example:** `sum(o.order_total) FROM orders o JOIN order_items i ON i.order_id = o.id`. `orders` is one
  row per order; `order_items` is many-per-order, so `order_total` repeats once per line → the sum
  inflates by the item count. → **FLAG: fan trap, revenue inflated.** (Retail analog: joining sales to
  product on `upc`, where one UPC maps to several SKUs, multiplies the sales.)

---

## Build order

1. **Column-existence** — cheapest, highest-frequency (the panel's most common "should fail at build
   time"), and it turns a silent runtime lie into a loud build error.
2. **Value-domain (data version)** — extend `value_check.py` to run `SELECT DISTINCT` and to catch magic
   values / type mismatches / value-set drift.
3. **Ratio-consistency** and **additivity roll-up gate** — both static, both reuse machinery already in
   `detect.py`/`grounding.py`.
4. **Grain** — needs metric grain metadata; static-ish.
5. **Join-cardinality / fan-trap** — hardest; needs the emitted query. Its own detector.

Every one is `parse → look up one fact → apply one rule → flag`. None needs a model. Together with the
ambiguity detector (Mode 1) they are the full guard: **one comparison tool for selection, a set of
rule-based validators for construction.**

## What exists today
- **Mode 1** — the ambiguity/collision detector (`detect.py` + `grounding.py`), validated.
- **Mode 2** — `value_check.py` (value-domain, declared-enum version); `_additivity()` in the detector
  (the additivity derivation, not yet gating roll-ups). The other four are specified above, not built.
