# The analysis ontology, and why the evidence graph needs one

Research note, 2026-07-29. Companion to `EVIDENCE-GRAPH.md` (the case) and
`EVIDENCE-GRAPH-DESIGN.md` (the architecture).

## The thesis

VeriGraph's weakest joint is `infer`. A derivation is *premises → conclusion*, licensed by a
free-text reasoning string, and checked by an LLM judge (gpt-4o-mini in their experiments). The
graph is typed; the **reasoning on its edges is not**.

In analytics that is a missed opportunity, because most derivations are not free-text inference —
they are **algebra over a governed ontology**, and the ontology already says which operations are
legal:

- `ratio = numerator / denominator` — legal, and the result's additivity is known
- `parent = child₁ × child₂ × child₃` — an identity edge; shares sum to 1, exactly
- summing a measure across a dimension — legal **iff** the measure is additive over it
- `metric A / metric B` where nothing defines that ratio — illegal; this is R7's rule

**The ontology is the warrant.** That is the whole idea: where a derivation is licensed by a
governed definition, it can be checked without a model.

## The frame: Toulmin, with the semantic layer supplying the warrant

The [Toulmin model](https://writingcommons.org/section/genre/argument-argumentation/toulmin-argument/)
decomposes an argument into claim, grounds, warrant, backing, qualifier, rebuttal. It maps onto a
governed analytics stack almost slot for slot:

| Toulmin | analytics | in this harness |
|---|---|---|
| grounds | a governed query result | `[r1]`, typed `result_values` |
| claim | a statement about a number | a bound claim |
| **warrant** | the rule licensing the step | metric type (ratio / derived), tree identity edge |
| **backing** | why the warrant holds | the semantic-layer definition; `op: multiply` |
| **qualifier** | strength and scope | additivity; identity vs influence; edge confidence |
| rebuttal | when it fails | non-additive over this dimension; outside coverage |

This is being taken seriously for LLM reasoning right now — TRACE (Kim and Yang, 2026) segments
chain-of-thought into Claim / Data / Warrant / Backing / Qualifier / Rebuttal, and
[Critical-Questions-of-Thought](https://arxiv.org/html/2412.15177v1) steers reasoning by asking
Toulmin-style critical questions. Neither has a *governed* warrant available. An analytics stack
does.

## What the industry actually specifies

### Metric ontologies

**[MetricFlow / dbt Semantic Layer](https://docs.getdbt.com/docs/build/metrics-overview)** is the
richest shipped vocabulary. Five metric types — `simple`, `ratio`, `derived`, `cumulative`,
`conversion` — plus `non_additive_dimension`, `agg_time_dimension`, and `input_metrics` on derived
metrics. That last field is a **declared lineage edge between metrics**, which is exactly a
derivation edge.

**[Cube](https://cube.dev/articles/semantic-layer-for-ai-agents-2026)** frames the semantic layer as
the agent's interface: the agent selects from a governed set by name rather than authoring SQL, over
MCP. Their reported figures for grounded vs raw text-to-SQL are large — on messy real-world data,
dbt's internal testing is cited at roughly 40% raw-schema versus 83% grounded.

**[Open Semantic Interchange (OSI)](https://open-semantic-interchange.org/)** — Snowflake, Salesforce,
dbt Labs, RelationalAI; announced September 2025, spec published on GitHub under Apache 2.0. This is
the standard forming right now, and reading
[`core-spec/spec.yaml`](https://github.com/open-semantic-interchange/OSI/blob/main/core-spec/spec.yaml)
is instructive. A v1.0 metric carries:

```
name · expression (a SQL string, per dialect) · description · datatype · ai_context
```

That is all. **No metric type, no additivity, no aggregation as structured data, no lineage between
metrics, no unit, no time grain.** The aggregation is inside an opaque SQL string. Community issues
on the repo already flag it: no distinction between additive and non-additive metrics, and limited
lineage for derived calculations.

So the emerging interchange standard is currently *thinner* than MetricFlow, and thinner than this
harness's own layer — which carries `unit`, and which `output_validation` depends on to range-check
a result.

### Does MetricFlow already have it?

For **computation**, largely yes — and more than this harness has. For **assertion**, no, and the
distinction is the point.

MetricFlow's additivity is *enforcement*, not *description*. `non_additive_dimension` tells the query
compiler not to sum a measure over a dimension, and the framework then refuses to build the wrong
SQL. It is a rule the compiler applies, not a property a consumer can reason with — because
MetricFlow's only consumer is a query.

That is exactly the gap this harness falls into. The layer can stop a wrong *query*. Nothing stops a
wrong *sentence*: an agent queries four weekly figures and writes "so roughly 3,500 monthly actives."
**MetricFlow closes the gap at query time; an evidence graph needs it at claim time.**

### What our layer has, and what it is missing

`semantic/semantic_layer.yml`, 15 metrics, fields:
`description · entity · segment · unit · synonyms · base · agg · time_column · dimensions ·
default_filters · supports_internal_filter · filterable`

**`agg` is a raw SQL string**, which is OSI's mistake one layer down:

```
value_moments      agg: "sum(moments)"                                   additive
active_users       agg: "count(distinct user_id)"                        NOT additive, over anything
moments_per_day    agg: "sum(moments) * 1.0 / nullif(count(*), 0)"       a ratio, written as a string
reminder_open_rate agg: "avg(had_reminder)"                              an average
```

You cannot ask whether a metric is additive without parsing SQL. And **`unit` cannot stand in for
additivity**: `value_moments` (`sum`) and `active_users` (`count_distinct`) both carry `unit: count`
and have opposite additivity. `unit` is a validation hint — it powers `output_validation`'s range
check — not an aggregation property.

| | MetricFlow | here today | verdict |
|---|---|---|---|
| metric type (simple/ratio/derived/cumulative/conversion) | ✅ | ❌ — implied by a SQL string | **borrow** |
| `agg` as structured data | ✅ enum | ❌ SQL string | **borrow** |
| additivity | ✅ `non_additive_dimension` | ❌ | **borrow, and expose rather than only enforce** |
| metric → metric lineage | ✅ `input_metrics`, numerator/denominator | ❌ | **borrow** |
| entity | ✅ | ✅ | aligned |
| segment | metric `filter` | ✅ | aligned |
| semantic unit (count/currency/share) | ❌ | ✅ | **keep — ours** |
| decomposition with contribution shares | ❌ | ✅ `tree.py` | **keep** |
| identity vs influence, edge confidence | ❌ | ✅ | **keep — unclaimed** |
| claim / provenance layer | ❌ | ❌ | **build** |

Two things are worth noticing in that table. This repo invented `unit` independently, because it
needed a deterministic output check — and MetricFlow has no equivalent, because validating assertions
is not its job. That is evidence the assertion layer really is separate territory.

And a derived metric is not a decomposition. `parent = a × b × c` expressed with `input_metrics`
tells you how to *compute* the parent. It does not give you log-difference contribution shares that
sum to 1, which is what attributing a *change* requires, and which `tree.py` already does.

### Decomposition ontologies

Metric trees / driver trees are an established **practice** with no standard encoding —
[Levers Labs](https://www.leverslabs.com/article/introducing-metric-trees) and
[Count](https://count.co/blog/intro-to-metric-trees) are the reference write-ups. A tree decomposes a
top-level metric into the sub-metrics that produce it. What none of them formalise is the distinction
this repo's tree already makes: **identity edges (exact arithmetic) versus influence edges
(correlational, with evidence and confidence).**

### Additivity

The Kimball classification — additive / semi-additive / non-additive — is the oldest piece of this
ontology and the most load-bearing for an evidence graph, because **additivity is a statement about
which aggregations preserve truth.**

A claim is only valid at the grain it was computed at. "Monthly active users" summed from four weekly
active-user figures is a distinct count aggregated over time: provably wrong, not a matter of
opinion. Today nothing here can catch it, because there is no derivation edge to inspect. With typed
edges plus additivity it is a static check — and the refusal vocabulary already has the code for it,
`wrong_grain`.

## The provenance side — this is already a solved formalism

**[Provenance semirings](https://web.cs.ucdavis.edu/~green/papers/pods07.pdf)** (Green, Karvounarakis,
Tannen, PODS 2007). Annotate each input tuple with a variable; the query's output carries a polynomial
recording how it was derived — `+` for alternative derivations, `×` for joint use. That polynomial
*is* the derivation edge, and the engine computes it. The framework unifies bag semantics, why-
provenance and probabilistic databases as instances of one construction.

The lesson for us: VeriGraph recovers computational provenance with a **static AST walk over Python**,
which cannot follow pandas mutation — they concede it. Over a governed semantic layer the equivalent
is not an approximation. The compiler knows.

**[PROV-O](https://www.w3.org/TR/prov-o/)** is the W3C vocabulary: `Entity`, `Activity`, `Agent`, with
`used`, `wasGeneratedBy`, `wasDerivedFrom`, `wasAttributedTo`. An evidence graph exported as PROV-O
speaks a standard rather than a homemade format — which is `TERMINOLOGY.md`'s stated goal, that a
hostile expert maps our work onto theirs on sight. `wasDerivedFrom` between claims, `wasGeneratedBy`
from a query activity, `wasAttributedTo` the model or the layer.

## The verdict taxonomy — binary is not enough

[WarrantScore](https://arxiv.org/pdf/2601.17377) (2026) evaluates whether evidence substantiates
claims in peer review, and its relation taxonomy is directly reusable:

**direct support · partial support · tangential · unsupported · contradictory**

Assessed along presence, relevance, sufficiency, and logical coherence. That is a much better
per-claim verdict than `allowed | refused`, and it names the case this harness's run 1 hit:
*contradictory* — a refusal that contradicts a claim bound to a governed result.

## Where this lands: which edges need a model, and which do not

The synthesis is a partition of derivation edges by **what licenses them**:

```
  edge type          licensed by                        checkable        example
  ─────────────────────────────────────────────────────────────────────────────────────────
  grounding          the result exists, values match    DETERMINISTIC    c1 ← r1:active_users
  identity           a tree identity edge; shares = 1   DETERMINISTIC    parent = a × b × c
  metric-algebra     a governed ratio/derived metric    DETERMINISTIC    ratio = num / den
  aggregation        additivity over that dimension     DETERMINISTIC    sum weekly → monthly
  scope comparison   same metric, two scopes (R7)       DETERMINISTIC    Δ, ratio, % change
  ─────────────────────────────────────────────────────────────────────────────────────────
  influence          a tree influence edge + confidence  TYPED, hedged   frequency ← reminders
  interpretation     nothing in the ontology             LLM JUDGE       "this is a problem"
```

Everything above the line is provable without a model. That is the payoff of pairing the evidence
graph with an analysis ontology, and it is the thing VeriGraph structurally cannot have: their
premises are natural-language claims over Python locals, so every `infer` edge goes to a judge.

Here, the judge is the **last** resort rather than the first — which is the same move this repo
already made when `governed_numbers` and `output_validation` were kept as provable checks while
wrong-metric selection went to the verifier.

## What is genuinely open

Nobody has specified the intersection:

- OSI has metrics without types, additivity, or lineage
- MetricFlow has types and additivity but no causal or decomposition edges
- metric trees are a practice with no encoding, and no notion of edge strength
- PROV-O has provenance but no analytics semantics
- Toulmin/WarrantScore have warrants but no governed source for them

**Governed metrics + typed decomposition edges + epistemic strength + claim provenance** is
unclaimed ground, and OSI's own issue tracker shows the standard heading toward the first two.
