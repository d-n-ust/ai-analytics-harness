# ai-analytics-ontology

The **marts ontology**: a closed-world graph of what the warehouse actually captures — entities,
their attributes and measures, the relationships between them, and (crucially) an explicit
statement of what is **NOT** captured. Its job is to make *answerability* decidable rather than
guessed: whether a question's measure is **instrumented** (a governed metric or attribute exists),
**computable** (no metric, but the ingredients to derive it exist), or **uninstrumented** (nothing
grounds it).

## The seam

This module owns the **deterministic** half. Given a measure decomposed into ingredients, it
verifies — by a closed-world traversal of the graph — that those ingredients EXIST **and that the
entities they touch can be JOINED**, and returns the three-way verdict. Existence closes the
absence gap; joinability closes the gap where every node is real but the entities do not relate. The **interpretive** half — turning a natural-language measure into ingredients
by meaning — is the model's, and lives in the agent. The graph never interprets language; the model
never invents a node. That separation is the whole design (see experiment 06, findings on the
ontology approach, and the ontology-engineering board consultation).

## Closure is a stance, not a list

There is **no enumerated absence** — no hand-maintained "no duration, no screen, no headcount". That
is the complement, which is unbounded and non-derivable. Instead the graph lists EVERYTHING the
warehouse captures (every column, every measure, every value domain) — a complete PRESENT — and
asserts the closed-world assumption once. Absence is then *derived*: a concept not in the complete
graph does not exist. Every node is generated and verified against `information_schema`, so
completeness of the present holds by construction, and a fingerprint catches schema drift.

## Design: a functional core with an imperative shell

The one side effect — reading `information_schema` — is pushed to the edge, so the logic is a pure
function of plain data and tests without a database.

| Function | Purity | Role |
|---|---|---|
| `MartsOntology.from_source(source, columns_by_table)` | pure | assemble the graph |
| `joinable(edges, entities)` | pure | can these entities be joined |
| `ontology.render()` / `verify(...)` / `fingerprint()` | pure | the model's surface, the verdict, the drift digest |
| `MartsOntology.build(cursor, schema, source)` | shell | fetch columns, then `from_source` |

The `source` is **read off the semantic-layer manifest** (`MetricFlowLayer.ontology_source()`) — each
entity's table, grain, measure columns and relationships trace to the layer, not to a hand-authored
dict, so "generated" is honest and the ontology cannot drift from the metrics it must agree with.
`fingerprint()` digests the whole rendered surface (columns, grain, measures and their semantics,
metrics, relationships), so any change the model would see forces a regenerate.
