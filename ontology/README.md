# ai-analytics-ontology

The **marts ontology**: a closed-world graph of what the warehouse actually captures — entities,
their attributes and measures, the relationships between them, and (crucially) an explicit
statement of what is **NOT** captured. Its job is to make *answerability* decidable rather than
guessed: whether a question's measure is **instrumented** (a governed metric or attribute exists),
**computable** (no metric, but the ingredients to derive it exist), or **uninstrumented** (nothing
grounds it).

## The seam

This module owns the **deterministic** half. Given a measure decomposed into ingredients, it
verifies — by a closed-world traversal of the graph — that those ingredients EXIST, and returns the
three-way verdict. The **interpretive** half — turning a natural-language measure into ingredients
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
