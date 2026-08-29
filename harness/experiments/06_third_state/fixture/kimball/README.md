# The corrected warehouse

The same raw data, modelled the way dimensional modelling says a balance should be modelled. It
exists beside the base warehouse, not instead of it: every number measured in this experiment was
measured against `wh_06`, and rebuilding a fixture is not a comparison.

```
build     uv run python build.py --models kimball/models --schema wh_06k
run       uv run python run.py --warehouse kimball --cases heldout.yml ...
ask       ./bench ask "..." --rung 3 --engine metricflow --layer <...>/kimball/layer --trace
```

## What was wrong, measured on the base warehouse

MRR is a **balance** — a level that exists at an instant. Dimensional modelling has one rule for a
balance: it belongs in a **periodic snapshot** and it is **semi-additive**, summable across
customers and plans on one date and never summable across dates.

The base warehouse models it as `agg: sum` over `started_date` on one row per subscription term —
a transaction fact carrying a balance. Three consequences, all measured before this directory
existed:

| | |
|---|---|
| **"MRR as at 2026-03-31" is inexpressible** | the nearest the layer answers is **322.36**, the terms that *started* that month, against a true balance of **1,061.38** |
| **A period silently swaps a stock reading for a cohort one** | a live agent asked what our monthly plans bring in returned **501.92** against **1,888.44**, and every guardrail passed it — the metric exists, the member is governed, the period is inside coverage |
| **The monthly figures sum to the balance** | because they are cohorts of it, so a reader who sums twelve months gets a number that *reconciles* and means something else |

The agent was not wrong in any of those runs. It was more correct than the model it was querying
could be, and no runtime check that trusts the layer can see that.

## What changed

**`fct_subscription_snapshot`** — one row per subscription per day it was live, 34,313 rows.
Live means started on or before the date and not yet ended, so a term later cancelled counts on
the days before it ended. That is the whole reason a snapshot exists rather than a filter on
current status.

**`dim_subscriptions`** — the term as an entity, with `mrr_amount` computed in the model. The base
warehouse leaves the yearly lump in the fact and divides by twelve inside the metric expression,
which puts business logic in the semantic layer where two metrics can spell it differently.

**`dim_date`** — the conformed date dimension. A snapshot needs a row for every date, including
dates on which nothing happened, and only a date dimension has those.

**The four balances are declared semi-additive** with `non_additive_dimension: {name: snapshot_date,
window_choice: max}`. The effect is not cosmetic:

```
naive SUM of mrr over Q2          151,678.37     what an additive measure would give
the layer returns                   2,420.56     the balance on the last day of the window
the true balance on 2026-06-30      2,420.56
```

The nonsense number is now structurally unavailable rather than merely unlikely. The harness
already reads the declaration — `metricflow_engine.additivity()` returns `semi_additive` when it is
set, which is what `output_validation` consumes — so this was machinery present, wired, and being
told MRR was additive.

## What was deliberately NOT changed

**All four contested pairs survive.** `active_users`/`active_accounts`,
`value_moments`/`total_value_moments`, `mrr`/`gross_mrr`, `marketing_spend`/`acquisition_spend`.
Two teams needing different numbers from one concept is an organisational fact, not a modelling
defect, and collapsing them would delete the subject of the experiment.

## The finding this produced

Three of the four pairs are **identical** on both warehouses — same values, same divergence. They
are genuine scope disagreements about who counts as a user and which channels count as acquisition,
and better modelling does not touch them.

The fourth changed character:

```
                             base                    corrected
mrr vs gross_mrr, now        2,685.08 / 2,754.00     2,685.08 / 2,685.08   agree
mrr vs gross_mrr, 2025-12-31          —              245.15 / 276.24       12.68% apart
                  2026-02-28          —              671.80 / 705.07        4.95% apart
                  2026-04-30          —            1,413.99 / 1,436.85      1.62% apart
                  2026-05-31 onward   —                                    agree
```

The base warehouse's `gross_mrr` sums terms in status *active or refunded*, and every refunded term
had ended by 2026-05-25. So its "gross MRR now" includes revenue from terms that stopped months
ago: not a balance, and with no clean reading. Expressed properly, the two definitions **agree
today and diverge historically**, converging as the refunded cohort ages out.

So **part of that pair's disagreement was modelling debt rather than governance**, and only good
modelling could tell which. That does not overturn the experiment's claim that some definitional
conflict is irreducible — three pairs demonstrate it unchanged — but it sharpens it, and it gives a
method: model the balances correctly first, and whatever conflict survives is the organisational
kind that a runtime mechanism has to handle.

## A second ambiguity, now expressible

A subscription term has more than one date a period filter could legitimately attach to, and
Kimball calls these **role-playing dates**. "June MRR" therefore has two correct readings:

```
balance as at 2026-06-30                2,420.56
revenue from terms that STARTED in June   750.88     222% apart
```

Both are governed, both are used, and a business will ask for both — sometimes in the same meeting.

**Carrying one date does not resolve that. It hides it.** The base warehouse carries only
`started_date`, so it can express only the cohort reading and answers every "as at" question with a
cohort. The first version of this table carried only `snapshot_date` and had the opposite blindness.
Each looks unambiguous from inside, and each silently answers a question nobody chose, in a YAML
default nobody reads.

So the snapshot carries both dates and the semantic model declares both time dimensions, with
`snapshot_date` as the default because a balance is read as at a date. The choice is now made at
query time, where it is visible, rather than in the manifest, where it is not.

**This is a different axis from the contested pairs**, and the machinery built for those is
structurally blind to it: the cluster index enumerates METRICS and asks which collide, and here
there is one metric and two time roles. There is no second name to point at. A third axis exists
too and this file created it — `window_choice: max` decides that "MRR over Q2" means the balance on
the last day rather than the average across the quarter, which is defensible and was chosen
silently.

| axis | the question | detected today? |
|---|---|---|
| which rows | whose scope? | yes — indexed, executed, compared |
| which date | what does "June" attach to? | no |
| how to collapse a period | last, first, or average? | no |

All three share the property that made the first tractable: **the alternatives are enumerable
offline from the layer.** The competing metrics come from the manifest, the time roles from the
semantic model's time dimensions, the window choices from the legal set for a semi-additive
measure. So the index generalises from "which metrics collide" to "which readings of this request
collide", and everything downstream works unchanged.

## Known gap

The case oracles in `cases.yml` and `heldout.yml` are written against base semantics for the four
subscription metrics, so those questions do not transfer. A run with `--warehouse kimball` grades
them wrongly until each declares its own expectation per warehouse. Everything not touching
subscriptions transfers unchanged.
