# Experiment 06 — findings

The standing record for the third state. Every number here traces to a stored row under
`fixture/*.json`; where a claim rests on something not measured, it says so.

**Status: preliminary.** One question, one fixture. This establishes mechanisms and directions, not
rates. The noise band it would be read against does not exist yet.

---

## The fixture

One question, and deliberately the most ordinary one anyone asks an analytics system.

> How many active users did we have last week?

Two governed definitions answer it, and both are right:

| | value | owner | consumer |
|---|---:|---|---|
| excluding internal and test accounts | **886** | Product | the weekly product review, the North Star tree |
| including them | **919** | Platform | capacity planning, the support-volume forecast |

**Irreducible by construction.** The case schema requires an `owner` and a `consumer` for every
candidate, because a definition nobody owns and nothing consumes is a leftover — reducible, deletable
offline, and therefore experiment 05's finding rather than this one's. Neither of these can be
deleted without breaking a real report, so no offline repair collapses them.

**The dose, measured.** The two disagree on 11 of 12 slices, between 0.00% and 5.17%, and by 3.72%
on the week as a whole. Sign is consistent, so neither is a data error.

**Agreement with the detector, measured separately.** The candidates in `cases.yml` were written by
reading the layer. preflight 0.4.0 reads the same layer independently and reports exactly one
finding, HIGH, naming the same pair. One of one. The two passes stay separate because a detector
that writes the ground truth and then enforces it is marking its own homework.

---

## 1 · The headline

| | attempts | clarified | silent errors |
|---|---:|---:|---:|
| **everything advisory** | **217** | **16** | **201** |
| **the enforced gate** | **15** | **15** | **0** |

All 16 advisory clarifications came from one model on one layer. See §3.

This is the R3-over-R6 pattern from the reliability ladder reproduced on a new failure: the
enforced version of a check was the best value in the whole ladder, and the advisory version
(`transparency`) enforced nothing and contributed nothing.

---

## 2 · Everything advisory that failed

Each row holds the layer and the model fixed and changes one thing.

| what was tried | attempts | clarified |
|---|---:|---:|
| no clarify tool at all | 3 | 0 |
| a prose clarify tool | 13 | 0 |
| a **typed** clarify tool — coded reason, named candidates | 19 | 0 |
| the rule written into the prompt (*refuse when nothing answers, clarify when more than one does*) | included above | 0 |
| **renaming** so neither metric matches the question | 8 (gpt-5-mini) | 0 |
| **reordering** the catalogue | 8 | 0 |
| **compact catalogue** — the two descriptions on adjacent lines instead of five apart | 32 | 0 |
| **transparency** — the compiled SQL and scope line on every result | 20 | 0 |

**Transparency is the strongest of these nulls** and the one most worth recording. The result the
agent read contained, verbatim:

```sql
... FROM wh_06.fct_user_days ... ) subq_4 WHERE activity__is_internal = false
```

The discriminator was in the output it had just received, not in a catalogue it skimmed, and it
still served the number without comment. Mechanism confirmed to have fired before the null was
recorded.

---

## 3 · The one thing that moved it, and why it is not a solution

`gpt-5.6-sol`, and only where the question's own wording matches no metric name:

| layer | the metric it would pick is called | matches the question | clarified |
|---|---|---|---|
| `baseline` | `active_users` | **exactly** | **0 / 10** |
| `crossed` | `active_customers` | partially | **1 / 10** |
| `no_exact_match` | `active_customers` vs `active_accounts` | **neither** | **10 / 10** |

And it asks a good question when it asks:

> *Should "active users" exclude internal and test accounts (customer activity), or include them to
> represent total platform load?*

**But it needs both the model and the naming.** On the same `no_exact_match` layer,
`gpt-5.6-terra` clarified 0/10 and `gpt-5-mini` 0/10. This is an interaction, not a main effect.

Two conclusions follow, and they are the practitioner findings:

**Scale does not buy this.** Three models, two of them large; one of them behaves correctly, under
one condition.

**Naming does not buy it either — and good naming makes it worse.** A metric named exactly what
users call the concept is what suppresses the question. `active_users` against a question saying
"active users" produced 0/10 from the one model capable of noticing. That is precisely the naming
every governance guide prescribes.

Neither is a foundation to build on: the behaviour depends on an interaction between the model you
happen to be running and the words your user happens to type.

---

## 4 · The name selects the metric; the description is not consulted

Four presentations of the same two definitions — identical measures, filters, values, owners and
consumers. Only the labels move.

| variant | 886 is called | 919 is called | served |
|---|---|---|---|
| `baseline` | `active_users` | `active_accounts` | **886** |
| `no_exact_match` | `active_customers` | `active_accounts` | **886** |
| `reversed` | `active_users` *(declared second)* | `active_accounts` *(first)* | **886** |
| **`crossed`** | **`real_customers`** | **`active_customers`** | **919** |

The word "active" moved from one definition to the other and the answer moved with it. On the
crossed layer it served a count that **includes staff and test logins** for a question about users,
from a metric whose own description says it is about load rather than customers.

**It knows, and does not show.** Asked to *compare* the two definitions rather than to answer, the
same model on the same layer clarifies, names both candidates and states the discriminator exactly.
The knowledge is available; the answering path does not use it. This is *Knowing but Not Showing*
(arXiv 2605.25284) reproduced within-subject on a governed layer.

---

## 5 · The enforced gate

`ambiguity_check`, at position `BEFORE`. Every governed call is looked up in an index beside the
layer; a call naming a contested metric is refused before it runs.

**15 of 15, both layers, both namings, silent error 1.00 → 0.00.**

**The block hands over the decision brief rather than pointing at it** — decided by §4, since an
agent that does not read descriptions on the answering path will not go and look one up:

```text
BLOCKED — 'active_users' is not the only governed definition of what it measures:
'active_accounts' answers the same question and returns a different number for this exact
request (886 against 919, 3.72% apart). They differ by is_internal = false. Do not pick one
and do not average them. End with `clarify`, naming both in `candidates`, and ask the user
about is_internal = false in their own words.
```

**The reason code is now correct.** Both voluntary clarifications recorded before the gate filed
`underspecified_request`; every gated one files `competing_definitions`. Naming the collision fixed
the classification too.

### Sensitivity, not membership

The gate fires on whether the reader would receive a **different number for this call**, not on
whether the metric has a competitor. It executes each competitor with the same arguments.

| the call | verdict |
|---|---|
| `active_users`, last week | **BLOCKED** — 886 against 919, 3.72% apart |
| `active_users`, `platform = web` | **BLOCKED** — 277 against 289, 4.33% apart |
| `active_users`, `platform = unknown` | **allowed** — both readings return the same number |
| `value_moments`, last week | allowed — no competitor |

Membership alone would have fired on **40.3%** of the frozen suite's metric-declaring answers, most
of them diagnostics — the brief's own falsification condition, met by arithmetic.

**The threshold is zero, and the zero is argued.** The instinct is to ignore small divergences and
it is backwards: danger runs *inverse* to magnitude, because a figure a few tenths of a percent from
its sibling is the one no reader and no range check catches. "Does not matter" means *identical*,
not *close*. A non-zero threshold is the brief's "divergence threshold" lever — worth measuring, not
a default.

---

## 6 · What was built

| | where |
|---|---|
| `preflight index` — writes the ambiguity index a runtime gate looks names up in | preflight, `wt-cluster_index` |
| `clusters.py` — loads it, verifies the fingerprint, refuses on staleness | `semantic/src/semantic/` |
| `ambiguity_check` — the gate | `engine/src/agent/guardrails/before.py` |
| `clarify` / `typed_clarify` — the channel and its payload, as switchable guardrails | `engine/src/agent/` |
| `expect.type: contested` — a third pile in the shared grader and metrics | `harness/evals/` |

All additive: 413 published values recomputed from the archive and none moved; `LADDER` is still
R0–R9 and `test_surface.py` passes unchanged.

### Two design constraints discovered the hard way

**The index cannot live inside the layer.** MetricFlow's parser reads every `.yml` under its
directory *recursively* and rejects documents it does not recognise, so an index placed inside fails
the whole layer at load. Convention is `<spec>.clusters.yml`, a sibling — together for a reader,
apart for a parser.

**The staleness guard was verifying the wrong files.** It recorded absolute paths, so a copied tree
hashed the originals and reported agreement; a checked-in index would have done the same on any
other machine. Now paths are recorded relative to the index and the digest's label is separated from
the file it reads.

---

## 7 · Not measured

- **Over-clarification.** This fixture has no Pile A, so the gate has never been asked a question it
  should have left alone. The 40.3% figure is what *membership* would have cost on the frozen suite;
  what *sensitivity* costs is unknown. This is the number that decides whether the gate is shippable.
- **A rate of any kind.** One question, one fixture. The sizing work in `00_reading.md` says a usable
  pile needs four to five distinct contested concepts, and the noise band does not exist.
- **The second turn.** No user simulator, so a clarification is priced at half an episode and
  abandonment is unmeasurable.
- **Cost of the gate.** It runs each competitor once per contested call. Cheap on DuckDB, unmeasured
  on anything else.

## 8 · Candidate next arms

- **Disclose the definition's own filter in the scope line.** The MetricFlow adapter's scope line
  says "no filters — the whole population this metric defines" while the metric itself carries
  `is_internal = false`. The harness's own layer says "the metric definition already restricts: NOT
  is_internal" in the same position. The information is in the SQL either way, but the prose summary
  is what gets skimmed, and this is the cheapest untried advisory lever.
- **Answer with both, disclosed** — the fourth column of the matrix. Weakened as a hypothesis by §4:
  it rested on the model's pick being reliably sensible, and the pick follows the label.
- **A non-zero divergence threshold**, as a lever rather than a default.
